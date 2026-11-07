"""API/decision models for the safety response and for concrete referral recommendations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SafetyState = Literal["NONE", "UNCLEAR", "HUMAN_CHECK", "IMMEDIATE"]
ContactQuality = Literal["OFFICIAL", "DIRECTORY", "UNDOCUMENTED", "NATIONAL"]


class ContactPhone(BaseModel):
    label_de: str  # "Telefon", "Telefon (24 h)", ...
    display: str  # as written in the knowledge base
    tel: str | None = None  # digits only, for tel: links (None = not safely linkable)


class ReferralCard(BaseModel):
    """One organisation, sanitised for display. Everything comes from the knowledge base; nothing is invented."""

    id: str
    label: str
    type: str
    kind: Literal["emergency", "crisis_counselling", "authority", "counselling", "shelter", "other"]
    specializations: list[str] = []
    phones: list[ContactPhone] = []
    email: str | None = None
    web: str | None = None
    address: str | None = None  # never set for protected addresses (shelters)
    address_protected: bool = False
    hours: str | None = None
    costs: str | None = None
    access: str | None = None
    languages: str | None = None
    note: str | None = None
    availability: str | None = None
    quality: ContactQuality
    quality_label_de: str
    last_checked: str | None = None
    verified: bool = False
    not_emergency_number: bool = False  # e.g. 142: counselling only, never for acute danger
    for_audience_de: str | None = None  # e.g. 147: "für Kinder und Jugendliche"
    reason_de: str | None = None  # why this organisation was suggested (rule / signal)
    rule_ref: str | None = None  # audit: issue rule or safety category that led here


class SafetySignalOut(BaseModel):
    id: str | None = None
    category: str
    label_de: str
    certainty: Literal["ACUTE", "UNCLEAR"]
    action: str  # configured consequence of the category
    evidence_quote: str
    message_id: str | None = None
    rule_id: str
    modifiers: list[str] = []
    detected_at: datetime | None = None
    acknowledged: bool = False
    acknowledged_note: str | None = None
    acknowledged_at: datetime | None = None


class SafetyAssessment(BaseModel):
    state: SafetyState = "NONE"
    signals: list[SafetySignalOut] = []
    immediate_categories: list[str] = []
    headline_de: str | None = None
    explanation_de: str | None = None
    steps_de: list[str] = []
    contacts_immediate: list[ReferralCard] = []  # emergency numbers (144, 117)
    contacts_counselling: list[
        ReferralCard
    ] = []  # crisis / victim counselling (143, 147, 142), not emergencies
    contacts_further: list[
        ReferralCard
    ] = []  # regional follow-up after the acute danger (opferhilfe_kantonal, ...)
    briefing_flags: list[str] = []
    legal_secondary: bool = False  # legal handling has no priority while the emergency is open


class ReferralPlan(BaseModel):
    primary: list[ReferralCard] = []
    more: list[ReferralCard] = []
    location_de: str | None = (
        None  # "Kanton ZH, Gemeinde Zürich" or why no regional contact is shown
    )
    notes_de: list[
        str
    ] = []  # e.g. "keine Winterthurer Stelle konfiguriert, kantonale Stelle gezeigt"
    unresolved_roles: list[str] = []
