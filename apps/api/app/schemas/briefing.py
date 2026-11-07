from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.domain.enums import Action, FactOrigin, FactStatus, HandoverStatus
from app.schemas.decision import ApprovedStatement, MissingFact, RelatedRoute, TriggeredRule
from app.schemas.safety import ReferralPlan, SafetyAssessment
from app.services.sources.registry import SourceRef

Provenance = Literal["REPORTED_BY_AI_EXTRACTION", "ANSWER_RECORDED", "CORRECTED_BY_USER"]

# How well a fact is backed. Kept as separate levels so the expert sees at a glance what is what.
EvidenceLevel = Literal[
    "DOCUMENTED",  # backed by a document (marked by the social worker)
    "CONFIRMED",  # confirmed or corrected by the social worker
    "STATED",  # stated by the user (answer recorded by the social worker)
    "AI_EXTRACTED",  # extracted by the AI from the narrative, not yet confirmed
    "SYSTEM_DERIVED",  # computed by the system from other facts (internal urgency only)
    "UNKNOWN",  # asked, the person does not know
    "UNCLEAR",  # ambiguous or contradictory
    "NOT_ASKED",  # not yet asked / unresolved
]


class BriefingOverview(BaseModel):
    case_display_id: str
    title: str
    summary: str
    message_count: int
    action: Action
    created_at: datetime


class BriefingIssue(BaseModel):
    issue_id: str
    title_de: str
    legal_area: str
    confidence: float | None
    evidence: str | None
    content_status: str


class BriefingUnsupportedIssue(BaseModel):
    description: str | None
    evidence: str | None


class BriefingFact(BaseModel):
    fact_id: str
    label_de: str
    value: Any
    value_display: str
    origin: FactOrigin | None
    provenance: Provenance
    evidence_level: EvidenceLevel = "AI_EXTRACTED"
    confirmed: bool
    documented: bool = False
    evidence_quote: str | None


class BriefingUncertainty(BaseModel):
    fact_id: str
    label_de: str
    status: FactStatus
    values: list[str]
    note: str | None = None


class BriefingSource(BaseModel):
    source: SourceRef
    referenced_by: list[str]


class BriefingRisk(BaseModel):
    rule_id: str
    issue_id: str
    result_code: str
    result_de: str
    source_ids: list[str]


class BriefingDecision(BaseModel):
    action: Action
    main_reason_code: str
    reason_codes: list[str]
    explanation_de: str
    rules_evaluated: int
    rules_triggered: list[str]
    max_urgency: str | None = None
    max_urgency_label_de: str | None = None


class BriefingProfessional(BaseModel):
    id: str
    label_de: str
    description_de: str


class BriefingHandover(BaseModel):
    status: HandoverStatus
    note: str


# ---- issue-specific view (profile from the knowledge base) -----------------------------------
class IssueRow(BaseModel):
    fact_id: str
    label_de: str
    value_display: str
    status: FactStatus
    evidence_level: EvidenceLevel
    evidence_label_de: str
    evidence_quote: str | None = None


class IssueGroup(BaseModel):
    id: str
    title_de: str
    rows: list[IssueRow]


class DerivedRow(BaseModel):
    id: str
    label_de: str
    value: int | None
    evidence_level: EvidenceLevel = "SYSTEM_DERIVED"
    note_de: str


class ReviewPointOut(BaseModel):
    text_de: str
    source_ids: list[str]
    triggered: bool = False  # True if a fired rule produced it


class AuthorityOut(BaseModel):
    id: str
    name_de: str
    purpose_de: str
    cost_de: str
    scope_de: str
    source_note_de: str
    url_hint: str | None
    contact_verified: bool
    verified_at: str | None
    verification_note_de: str


class IssueBriefing(BaseModel):
    issue_id: str
    title_de: str
    intro_de: str
    canton: str | None
    concern_de: str
    groups: list[IssueGroup]
    derived: list[DerivedRow]
    triggered_rules: list[TriggeredRule]
    max_urgency: str | None
    max_urgency_label_de: str | None
    urgency_note_de: str
    open_questions: list[str]
    unknown_facts: list[str]
    documents_to_request: list[str]
    review_points: list[ReviewPointOut]
    authorities: list[AuthorityOut]
    statements_suppressed: bool


class ChronologyEvent(BaseModel):
    date: str | None  # ISO date; None = no date known (kept in order of capture)
    label_de: str
    source_de: str
    future: bool = False  # a date after the report date (e.g. stated termination date)


class ConversationItem(BaseModel):
    kind: Literal["DESCRIPTION", "ANSWER", "NOTE"]
    at: str  # "dd.mm.yyyy HH:MM"
    question_de: str | None = None
    text: str
    status_de: str | None = None  # e.g. "gefragt, unbekannt"


class ReportExtras(BaseModel):
    """Everything the case report needs beyond the structured briefing. Captured at creation time so that every
    stored version renders exactly as it was. Documents: LexTec Bridge has no upload yet, so the list stays empty."""

    location_canton: str | None = None
    location_municipality: str | None = None
    safety: SafetyAssessment | None = None
    referrals: ReferralPlan | None = None
    chronology: list[ChronologyEvent] = []
    conversation: list[ConversationItem] = []
    documents: list[dict[str, Any]] = []
    extraction_model: str = ""
    kb_status: str | None = None
    inputs_count: int = 0
    effective_action: str | None = None
    created_by_note: str = "eine Sozialarbeiterin"


class CaseBriefing(BaseModel):
    schema_version: int = 2
    template_id: str
    section_order: list[str]
    case_version: int
    knowledge_base_version: str
    knowledge_base_notice: str | None
    ai_mode_notice: str
    overview: BriefingOverview
    legal_areas: list[BriefingIssue]
    unsupported_issues: list[BriefingUnsupportedIssue]
    known_facts: list[BriefingFact]
    missing_information: list[MissingFact]
    uncertainties: list[BriefingUncertainty]
    legal_sources: list[BriefingSource]
    legal_risks: list[BriefingRisk]
    approved_statements: list[ApprovedStatement] = []
    related_routes: list[RelatedRoute] = []
    decision: BriefingDecision
    escalation_reasons: list[TriggeredRule]
    recommended_professionals: list[BriefingProfessional]
    handover: BriefingHandover | None
    next_steps: list[str]
    issue_briefings: list[IssueBriefing] = []
    # Data connection only (not rendered yet; the law team defines the briefing layout): safety signals and referrals
    safety_state: str = "NONE"
    safety_flags: list[str] = []
    safety_signal_categories: list[str] = []
    recommended_referral_ids: list[str] = []
    extras: ReportExtras | None = (
        None  # report-only data (chronology, conversation, safety, referrals)
    )


class BriefingView(BaseModel):
    id: str
    version: int
    case_version: int
    created_at: datetime
    briefing: CaseBriefing
