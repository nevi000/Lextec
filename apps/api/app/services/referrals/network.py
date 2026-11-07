"""Referral network (knowledge_base/referrals/referral_network.yaml): schema, role resolution, card building.

Deterministic. The AI never picks organisations; it only contributes facts. Resolution order for a role is
"CANTON:Gemeinde" -> "CANTON" -> default (law team's role_resolution). Nothing is guessed: an unknown or
unconfirmed jurisdiction falls back to the generic national entry or to nothing.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety import ContactPhone, ReferralCard


# ----------------------------------------------------------------------------------- file schema
class Org(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    label: str
    type: str
    contact: dict[str, Any] | None = None
    verified: bool = False
    specializations: list[str] = []
    note: str | None = None
    source_url: str | None = None
    region: list[str] | None = None
    contact_source: Literal["primary", "secondary", "none"] | None = None
    last_checked: str | None = None
    availability: str | None = None
    active: bool = True
    address_protected: bool = False
    official_check: dict[str, Any] | None = None


class Conditional(BaseModel):
    model_config = ConfigDict(extra="allow")
    when: dict[str, str]
    add: list[str] = []
    urgency: str | None = None
    note: str | None = None


class IssueReferrals(BaseModel):
    model_config = ConfigDict(extra="allow")
    primary: list[str] = []
    secondary: list[str] = []
    conditional: list[Conditional] = []


class IssueRule(BaseModel):
    model_config = ConfigDict(extra="allow")
    issue_id: str
    label: str | None = None
    referrals: IssueReferrals = Field(default_factory=IssueReferrals)
    reason_for_referral: str | None = None


class SafetyRoute(BaseModel):
    model_config = ConfigDict(extra="allow")
    category: str
    action: Literal["IMMEDIATE_SAFETY_RESPONSE", "ESCALATE", "ASK", "PROCEED", "FLAG"]
    notify_caseworker: str | None = None
    show_to_user: list[str] = []
    referrals: list[str] = []
    follow_up_referrals: list[str] = []
    conditional: list[Conditional] = []
    briefing_flag: str | None = None


class SignalBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: list[str] = []
    safety_categories: list[str] = []


class ReferralNetwork(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int = 1
    version: str
    last_reviewed: str | None = None
    reviewed_by: str | None = None
    role_resolution: dict[str, dict[str, str | None]] = {}
    professionals: list[Org]
    issue_rules: list[IssueRule] = []
    safety_routing: list[SafetyRoute] = []
    cross_cutting: list[dict[str, Any]] = []
    signal_bindings: dict[str, SignalBinding] = {}
    content_status: str | None = None

    # -- lookups -----------------------------------------------------------------------------
    def org_map(self) -> dict[str, Org]:
        return {o.id: o for o in self.professionals}


# ----------------------------------------------------------------------------------- location
def _norm(s: str) -> str:
    s = (
        s.strip()
        .lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


class Location(BaseModel):
    canton: str | None = None
    municipality: str | None = None

    def describe(self) -> str | None:
        if self.canton and self.municipality:
            return f"Kanton {self.canton}, Gemeinde {self.municipality}"
        if self.canton:
            return f"Kanton {self.canton}"
        if self.municipality:
            return f"Gemeinde {self.municipality} (Kanton nicht bestätigt)"
        return None


def infer_canton(net: ReferralNetwork, municipality: str | None) -> str | None:
    """Canton from a municipality only if exactly one canton of the network knows it (never guess)."""
    if not municipality:
        return None
    m = _norm(municipality)
    cantons = {
        key.split(":", 1)[0]
        for table in net.role_resolution.values()
        for key in table
        if ":" in key and _norm(key.split(":", 1)[1]) == m
    }
    return next(iter(cantons)) if len(cantons) == 1 else None


def resolve_role(net: ReferralNetwork, role: str, loc: Location) -> tuple[str | None, str]:
    """-> (organisation id | None, how it was resolved: municipality | canton | default | direct | none)."""
    table = net.role_resolution.get(role)
    if table is None:
        return (role, "direct") if role in net.org_map() else (None, "none")
    canton = (loc.canton or "").upper() or None
    if canton and loc.municipality:
        want = _norm(loc.municipality)
        for key, org_id in table.items():
            if (
                ":" in key
                and key.split(":", 1)[0].upper() == canton
                and _norm(key.split(":", 1)[1]) == want
            ):
                return org_id, "municipality"
    if canton:
        for key, org_id in table.items():
            if key.upper() == canton:
                return org_id, "canton"
    return table.get("default"), "default"


# ----------------------------------------------------------------------------------- cards
_TEL = re.compile(r"^\s*(\+?\d[\d ]{1,18}\d)")
_MAIL = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[A-Za-z]{2,}$")
KIND_BY_TYPE = {
    "emergency": "emergency",
    "hotline": "crisis_counselling",
    "authority": "authority",
    "shelter": "shelter",
    "lawyer": "counselling",
    "ngo": "counselling",
    "ngo_cantonal_mandate": "counselling",
    "ngo_federal_mandate": "counselling",
}
PHONE_KEYS = [
    ("phone", "Telefon"),
    ("phone_24h", "Telefon (24 h)"),
    ("phone_legal_info", "Telefon Rechtsauskunft"),
    ("hotline", "Hotline"),
]


def safe_tel(display: str) -> str | None:
    m = _TEL.match(display or "")
    if not m:
        return None
    digits = re.sub(r"[^\d+]", "", m.group(1))
    return digits if 3 <= len(digits.lstrip("+")) <= 15 else None


def safe_web(url: Any) -> str | None:
    if not isinstance(url, str):
        return None
    p = urlparse(url.strip())
    return (
        url.strip()
        if p.scheme in ("http", "https") and p.netloc and " " not in url.strip()
        else None
    )


def safe_mail(addr: Any) -> str | None:
    return addr.strip() if isinstance(addr, str) and _MAIL.match(addr.strip()) else None


def _text(v: Any) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def quality_of(o: Org) -> tuple[str, str]:
    checked = f" (geprüft am {o.last_checked})" if o.last_checked else ""
    if o.official_check or (o.contact_source is None and o.type in ("emergency", "hotline")):
        note = ""
        if o.official_check:
            note = f", am {o.official_check.get('checked')} auf der offiziellen Seite geprüft"
        return "NATIONAL", f"Nationale Nummer{note}"
    if o.contact_source == "primary":
        return "OFFICIAL", f"Kontaktangaben von der offiziellen Website der Stelle{checked}"
    if o.contact_source == "secondary":
        return (
            "DIRECTORY",
            f"Kontaktangaben aus einem Fachverzeichnis{checked}; vor produktivem Einsatz auf der Website der Stelle bestätigen",
        )
    return "UNDOCUMENTED", "Kontaktquelle nicht dokumentiert: Angaben nicht als geprüft behandeln"


def build_card(o: Org, *, reason: str | None = None, rule_ref: str | None = None) -> ReferralCard:
    c = o.contact or {}
    protected = o.address_protected or o.type == "shelter"
    phones = [
        ContactPhone(label_de=label, display=str(c[key]).strip(), tel=safe_tel(str(c[key])))
        for key, label in PHONE_KEYS
        if _text(str(c[key]) if c.get(key) is not None else None)
    ]
    address = None if protected else _text(c.get("address")) or _text(c.get("postal_address"))
    quality, quality_label = quality_of(o)
    note = _text(o.note)
    return ReferralCard(
        id=o.id,
        label=o.label,
        type=o.type,
        kind=KIND_BY_TYPE.get(o.type, "other"),  # type: ignore[arg-type]
        specializations=o.specializations,
        phones=phones,
        email=safe_mail(c.get("email")),
        web=safe_web(c.get("web")),
        address=address,
        address_protected=protected,
        hours=_text(c.get("hours")),
        costs=_text(c.get("costs")),
        access=_text(c.get("access")),
        languages=_text(c.get("languages")),
        note=note,
        availability=_text(o.availability),
        quality=quality,  # type: ignore[arg-type]
        quality_label_de=quality_label,
        last_checked=o.last_checked,
        verified=o.verified,
        not_emergency_number=bool(note and "keine notrufnummer" in note.lower()),
        for_audience_de="für Kinder und Jugendliche" if "children" in o.specializations else None,
        reason_de=reason,
        rule_ref=rule_ref,
    )
