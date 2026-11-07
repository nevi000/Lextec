from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import Action, FactStatus
from app.schemas.safety import ReferralPlan, SafetyAssessment

Urgency = Literal["HIGH", "MEDIUM", "LOW"]

# Dossier wording: HIGH = "sofort", MEDIUM = "bald", LOW = "normal"
URGENCY_LABEL_DE = {"HIGH": "sofort", "MEDIUM": "bald", "LOW": "normal"}


class MissingFact(BaseModel):
    fact_id: str
    issue_ids: list[str]
    label_de: str
    status: FactStatus
    priority: Literal["high", "medium", "low"]
    question_de: str
    why_needed_de: str
    deferred: bool = False
    data_type: str = "string"
    enum_values: list[str] = []
    enum_labels_de: dict[str, str] = {}
    handover_priority: Literal["high", "normal"] = "normal"


class IntakeState(BaseModel):
    """How complete the case information is. Independent of the decision (ESCALATE never closes the intake)."""

    important_open: int = 0  # required / conditionally required facts still to ask (not deferred)
    optional_open: int = 0  # helpful optional facts not yet asked or skipped
    deferred: int = 0  # postponed or skipped by the social worker
    unknown: int = 0  # asked, answered "weiss nicht" (documented, never re-asked)
    known: int = 0  # known facts of the active issues
    complete: bool = False  # no important question left open


class NextQuestion(BaseModel):
    fact_id: str | None  # None => generic prompt (e.g. no input yet)
    question_de: str
    why_needed_de: str = ""
    data_type: str = "string"
    enum_values: list[str] = []
    enum_labels_de: dict[str, str] = {}
    deferred: bool = False
    optional: bool = False  # not required for the decision; asked to give the expert more context


class TriggeredRule(BaseModel):
    rule_id: str
    scope: Literal["GLOBAL", "ISSUE", "SYSTEM"]
    issue_id: str | None = None
    description: str
    reason_code: str
    reason_de: str
    urgency: Urgency = "MEDIUM"
    urgency_label_de: str = "bald"
    routes_to_issue: str | None = None


class EvaluatedRule(BaseModel):
    rule_id: str
    kind: Literal["GLOBAL_ESCALATION", "ISSUE_ESCALATION", "LEGAL_RULE", "SYSTEM"]
    issue_id: str | None = None
    description: str
    outcome: Literal["FIRED", "NOT_FIRED", "UNKNOWN"]


class LegalFinding(BaseModel):
    """A fired REVIEW_POINT rule: a pointer for the human expert, not a legal conclusion."""

    rule_id: str
    issue_id: str
    result_code: str
    result_de: str
    legal_source_ids: list[str] = []


class ApprovedStatement(BaseModel):
    """A controlled, source-bound general statement (kind HINT) that applies to this case."""

    rule_id: str
    issue_id: str
    text_de: str
    source_ids: list[str]


class RelatedRoute(BaseModel):
    """Hand-over to another issue. `available` if that issue is loaded in the KB (its status is stated in the note)."""

    issue_id: str
    title_de: str
    available: bool
    note_de: str
    from_rule_id: str


class DecisionResult(BaseModel):
    action: Action
    main_reason_code: str
    reason_codes: list[str]
    triggered_rule_ids: list[str]
    triggered_rules: list[TriggeredRule] = []
    evaluated_rules: list[EvaluatedRule] = []
    legal_findings: list[LegalFinding] = []
    approved_statements: list[ApprovedStatement] = []
    statements_suppressed: bool = False
    related_routes: list[RelatedRoute] = []
    explanation_de: str
    missing_facts: list[MissingFact] = []
    unknown_required_facts: list[MissingFact] = []  # asked, person does not know (never re-asked)
    optional_open_facts: list[MissingFact] = []
    intake: IntakeState = IntakeState()
    next_question: NextQuestion | None = None
    recommended_professionals: list[str] = []
    active_issue_ids: list[str] = []
    max_urgency: Urgency | None = None
    derived_values: dict[str, int | None] = {}  # system-derived (internal urgency only)
    # Safety layer (independent of the legal issue): may override the DISPLAYED main action, never the legal result.
    effective_action: Literal["IMMEDIATE_SAFETY_RESPONSE", "ESCALATE", "ASK", "PROCEED"] | None = (
        None
    )
    safety: SafetyAssessment | None = None
    referrals: ReferralPlan | None = None
    knowledge_base_version: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)

    def signature(self) -> str:
        """Stable hash of everything except the timestamp - used to avoid duplicate history rows."""
        parts: list[Any] = [
            self.action.value,
            self.reason_codes,
            self.triggered_rule_ids,
            [(m.fact_id, m.status.value, m.deferred) for m in self.missing_facts],
            [m.fact_id for m in self.unknown_required_facts],
            self.next_question.fact_id if self.next_question else None,
            self.recommended_professionals,
            [r.issue_id for r in self.related_routes],
            self.effective_action,
            self.safety.state if self.safety else None,
            [(s.category, s.certainty, s.acknowledged) for s in self.safety.signals]
            if self.safety
            else [],
            [c.id for c in self.referrals.primary + self.referrals.more] if self.referrals else [],
            self.knowledge_base_version,
        ]
        return hashlib.sha256(repr(parts).encode()).hexdigest()[:16]
