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


SOCIAL_STATUS = ("verified", "traeger_verified_contact_open", "to_verify")
MUNICIPAL_ROLE_FIELDS = (
    "schlichtungsbehoerde_miete",
    "unentgeltliche_rechtsauskunft",
    "sozialdienst_gemeinde",
    "notunterkunft",
    "kesb",
    "kjz",
    "mieterverband",
    "opferhilfe_kantonal",
    "frauenhaus",
    "frauenzentrale_kantonal",
    "ombudsstelle",
)


class MunicipalityEntry(BaseModel):
    """One Zürich municipality (v1.2 «municipalities»): district plus the responsible body per role.

    A role value is one organisation id or a LIST of ids (first = default, the others are further options).
    """

    model_config = ConfigDict(extra="allow")
    bfs: int
    bezirk: str
    region: str | None = None
    sozialdienst_status: (
        Literal["verified", "traeger_verified_contact_open", "to_verify"] | None
    ) = None


class AliasEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    municipality: str  # "ZH:Opfikon"
    status: Literal["law_team", "quartier"] = "quartier"


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
    role_resolution: dict[str, dict[str, str | list[str] | None]] = {}
    municipalities: dict[str, MunicipalityEntry] = {}
    municipality_aliases: dict[str, AliasEntry] = {}
    role_location_basis: dict[str, Literal["property", "residence"]] = {}
    professionals: list[Org]
    issue_rules: list[IssueRule] = []
    safety_routing: list[SafetyRoute] = []
    cross_cutting: list[dict[str, Any]] = []
    signal_bindings: dict[str, SignalBinding] = {}
    content_status: str | None = None

    # -- lookups -----------------------------------------------------------------------------
    def org_map(self) -> dict[str, Org]:
        return {o.id: o for o in self.professionals}

    def municipality_roles(self) -> set[str]:
        """Roles that have a per-municipality entry (so a missing municipality means «not locally determinable»)."""
        return {k for e in self.municipalities.values() for k in (e.model_extra or {})} | set(
            MUNICIPAL_ROLE_FIELDS
        )

    def municipality_index(self) -> dict[tuple[str, str], str]:
        """(canton, normalised name) -> municipality key; also without a «(ZH)» suffix; aliases only if unambiguous."""
        idx = self.__dict__.get("_muni_idx")
        if idx is None:
            idx = {}
            for key in self.municipalities:
                canton, name = key.split(":", 1)
                idx[(canton.upper(), _norm(name))] = key
                bare = re.sub(r"\s*\(.*?\)\s*$", "", name)
                idx.setdefault((canton.upper(), _norm(bare)), key)
            for alias, a in self.municipality_aliases.items():
                canton = a.municipality.split(":", 1)[0].upper()
                idx.setdefault((canton, _norm(alias)), a.municipality)
            self.__dict__["_muni_idx"] = idx
        return idx


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
    municipality: str | None = None  # municipality of the rented property (as stated or canonical)
    residence_municipality: str | None = (
        None  # only if the client lives elsewhere (explicitly stated)
    )
    alias_note: str | None = None  # e.g. «Glattbrugg gehört zu Opfikon»

    def describe(self) -> str | None:
        if self.canton and self.municipality:
            return f"Kanton {self.canton}, Gemeinde {self.municipality}"
        if self.canton:
            return f"Kanton {self.canton}"
        if self.municipality:
            return f"Gemeinde {self.municipality} (Kanton nicht bestätigt)"
        return None


def find_municipality(
    net: ReferralNetwork, name: str | None, canton: str | None
) -> tuple[str | None, str | None]:
    """-> (municipality key «ZH:Opfikon» | None, how: exact | alias | None). Deterministic table lookup only."""
    if not name or not canton:
        return None, None
    idx = net.municipality_index()
    key = idx.get((canton.upper(), _norm(name)))
    if key is None:
        return None, None
    return key, (
        "exact" if key.split(":", 1)[1] and _norm(key.split(":", 1)[1]) == _norm(name) else "alias"
    )


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
    } | {c for (c, n) in net.municipality_index() if n == m}
    return next(iter(cantons)) if len(cantons) == 1 else None


class ResolvedOption(BaseModel):
    org_id: str
    how: str  # municipality_data | municipality | canton | default | direct
    municipality_key: str | None = None
    municipality_how: str | None = None  # exact | alias
    social_status: str | None = None  # sozialdienst_status of that municipality (social roles only)
    basis: str = "property"  # which location was used (property | residence)
    basis_fallback: bool = False  # residence wanted, property municipality used


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [x for x in v if isinstance(x, str)]


def resolve_role_options(net: ReferralNetwork, role: str, loc: Location) -> list[ResolvedOption]:
    """All organisations for a role, best first. Order (law team v1.2):
    municipalities[<key>].<role> -> role_resolution["<CANTON>:<Gemeinde>"] -> role_resolution["<CANTON>"] -> default.
    List values keep every option (first = standard). Never invents a local body: without a known municipality the
    cantonal or national entry is returned (how = canton / default)."""
    table = net.role_resolution.get(role)
    if table is None:
        return [ResolvedOption(org_id=role, how="direct")] if role in net.org_map() else []
    canton = (loc.canton or "").upper() or None
    basis = net.role_location_basis.get(role, "property")
    name = loc.municipality
    fallback = False
    if basis == "residence":
        if loc.residence_municipality:
            name = loc.residence_municipality
        else:
            fallback = bool(name)
    mkey, mhow = find_municipality(net, name, canton)
    if mkey is not None:
        entry = net.municipalities.get(mkey)
        status = None
        if entry is not None:
            if role in ("sozialdienst_gemeinde", "notunterkunft"):
                status = entry.sozialdienst_status
            ids = _as_list((entry.model_extra or {}).get(role))
            if ids:
                return [
                    ResolvedOption(
                        org_id=i,
                        how="municipality_data",
                        municipality_key=mkey,
                        municipality_how=mhow,
                        social_status=status,
                        basis=basis,
                        basis_fallback=fallback,
                    )
                    for i in ids
                ]
        for k, v in table.items():
            if k.upper() == mkey.upper() and _as_list(v):
                return [
                    ResolvedOption(
                        org_id=i,
                        how="municipality",
                        municipality_key=mkey,
                        municipality_how=mhow,
                        social_status=status,
                        basis=basis,
                        basis_fallback=fallback,
                    )
                    for i in _as_list(v)
                ]
    if canton:
        for k, v in table.items():
            if k.upper() == canton and _as_list(v):
                return [
                    ResolvedOption(org_id=i, how="canton", basis=basis, basis_fallback=fallback)
                    for i in _as_list(v)
                ]
    return [
        ResolvedOption(org_id=i, how="default", basis=basis, basis_fallback=fallback)
        for i in _as_list(table.get("default"))
    ]


def resolve_role(net: ReferralNetwork, role: str, loc: Location) -> tuple[str | None, str]:
    """First option only -> (organisation id | None, how). Kept for callers that need one organisation."""
    opts = resolve_role_options(net, role, loc)
    if not opts:
        return None, "none"
    how = opts[0].how
    return opts[0].org_id, "municipality" if how == "municipality_data" else how


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


_PHONE_NOTE = re.compile(r"\(([^)]*)\)")


def split_phones(raw: str) -> list[tuple[str, str | None]]:
    """«044 763 17 00 (Telefonzentrale) / 044 763 17 01» -> [("044 763 17 00","Telefonzentrale"), ("044 763 17 01",None)].

    Technical remarks are moved out of the number (not lost); text that is not a number stays untouched as display."""
    out: list[tuple[str, str | None]] = []
    for part in re.split(r"\s*(?:/|;|\boder\b)\s*", raw.strip()):
        part = part.strip()
        if not part:
            continue
        notes = [n.strip() for n in _PHONE_NOTE.findall(part) if n.strip()]
        bare = _PHONE_NOTE.sub("", part).strip(" ,;")
        if safe_tel(bare) is None and out:  # trailing words belong to the previous number
            prev, pnote = out[-1]
            out[-1] = (prev, "; ".join(x for x in [pnote, part] if x))
            continue
        out.append((bare or part, "; ".join(notes) or None))
    return out


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


def _clean_access(v: str | None) -> str | None:
    """Drops internal remarks about the data model («Feld web im Abschnitt municipalities, sobald geprüft»)."""
    if not v:
        return v
    cleaned = re.sub(r"\s*\((?:[^()]*(?:Feld|Abschnitt|municipalities)[^()]*)\)", "", v).strip()
    return cleaned or None


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
    # Protected: Frauenhäuser / domestic-violence shelters. A public emergency housing (Durchgangsheim) may show its address.
    protected = o.address_protected or (
        o.type == "shelter" and "emergency_housing" not in o.specializations
    )
    phones = [
        ContactPhone(label_de=label, display=disp, tel=safe_tel(disp), note_de=pnote)
        for key, label in PHONE_KEYS
        if _text(str(c[key]) if c.get(key) is not None else None)
        for disp, pnote in split_phones(str(c[key]))
    ]
    address = None if protected else _text(c.get("address")) or _text(c.get("postal_address"))
    quality, quality_label = quality_of(o)
    note = _clean_access(_text(o.note))
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
        access=_clean_access(_text(c.get("access"))),
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
