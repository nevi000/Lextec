from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    Action,
    AnalysisStatus,
    CaseStatus,
    FactOrigin,
    FactStatus,
    HandoverStatus,
    IssueStatus,
    MessageKind,
    MessageRole,
)
from app.schemas.decision import DecisionResult


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- cases -------------------------------------------------------------------------------
class CaseCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    description: str | None = Field(default=None, max_length=20000)


class CasePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: CaseStatus | None = None


class IssueView(ORM):
    id: str
    issue_definition_id: str | None
    title_de: str | None = None
    legal_area: str | None = None
    classification_status: IssueStatus
    confidence: float | None
    evidence: str | None
    description: str | None


class HandoverView(ORM):
    status: HandoverStatus
    professional_types: list[str]
    reasons: list[str]
    requested_at: datetime | None
    completed_at: datetime | None
    completion_note: str | None


class CaseListItem(BaseModel):
    id: str
    display_id: str
    title: str
    status: CaseStatus
    current_action: Action | None
    issue_titles: list[str]
    handover_status: HandoverStatus | None
    analysis_pending: bool
    safety_state: Literal["NONE", "UNCLEAR", "HUMAN_CHECK", "IMMEDIATE"] = "NONE"
    created_at: datetime
    updated_at: datetime
    version: int


class AnalysisState(BaseModel):
    status: Literal["OK", "PENDING", "FAILED"]
    pending_message_ids: list[str] = []
    error_code: str | None = None
    error_message: str | None = None
    warnings: list[str] = []


class CaseDetail(BaseModel):
    id: str
    display_id: str
    title: str
    summary: str
    status: CaseStatus
    version: int
    created_at: datetime
    updated_at: datetime
    issues: list[IssueView]
    current_decision: DecisionResult | None
    handover: HandoverView | None
    analysis: AnalysisState
    briefing_stale: bool
    latest_briefing_id: str | None


# ---- messages ----------------------------------------------------------------------------
class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    kind: MessageKind = MessageKind.DESCRIPTION
    answers_fact_id: str | None = Field(default=None, max_length=100)
    unknown: bool = (
        False  # "weiss nicht" as answer to answers_fact_id (recorded locally, no AI call)
    )


class MessageView(ORM):
    id: str
    role: MessageRole
    kind: MessageKind
    content: str
    answers_fact_id: str | None
    analysis_status: AnalysisStatus
    analysis_error: str | None
    origin: str | None = None
    original_language: str | None = None
    created_at: datetime


class MessageResult(BaseModel):
    message: MessageView
    analysis: AnalysisState
    case: CaseDetail


# ---- facts -------------------------------------------------------------------------------
class FactHistoryEntry(BaseModel):
    at: datetime
    event: str
    value: Any = None
    by: Literal["ai", "social_worker", "system"] = "system"
    note: str | None = None


class FactView(BaseModel):
    fact_id: str
    label_de: str
    issue_ids: list[str]
    data_type: str
    enum_values: list[str] = []
    enum_labels_de: dict[str, str] = {}
    group: str = ""
    documented: bool = False  # backed by a document (e.g. photo of the envelope)
    required: bool
    priority: Literal["high", "medium", "low"]
    question_de: str
    why_needed_de: str
    status: FactStatus
    value: Any = None
    origin: FactOrigin | None = None
    confirmed: bool = False
    evidence_quote: str | None = None
    source_message_id: str | None = None
    deferred_reason: str | None = None
    conflicting_values: list[dict] = []
    history: list[FactHistoryEntry] = []
    updated_at: datetime | None = None


class FactPatch(BaseModel):
    value: Any = None
    status: Literal["MISSING", "NOT_APPLICABLE", "UNKNOWN"] | None = None
    confirmed: bool | None = None
    documented: bool | None = None
    note: str | None = Field(default=None, max_length=1000)


class FactDefer(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


# ---- decisions / handover / briefing ----------------------------------------------------
class DecisionView(BaseModel):
    id: str
    case_version: int
    created_at: datetime
    decision: DecisionResult


class HandoverComplete(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


class BriefingListItem(BaseModel):
    id: str
    version: int
    case_version: int
    created_at: datetime
    action: Action


# ---- system / kb / evaluation -------------------------------------------------------------
class SystemStatus(BaseModel):
    app_env: str
    ai_provider: str
    ai_model: str
    ai_is_external: bool
    knowledge_base_version: str
    knowledge_base_valid: bool
    auth_mode: str = "LOCAL_DEMO_NO_AUTH"
    notice: str
    ai_usage: AIUsageSummary | None = None


class DashboardRecent(CaseListItem):
    pass


class DashboardData(BaseModel):
    total_cases: int
    open_cases: int
    needs_clarification: int
    escalated: int
    awaiting_professional_review: int
    recent: list[CaseListItem]


class AIUsageSummary(BaseModel):
    """Application-level accounting of real AI calls (not a guaranteed Google billing cap)."""

    calls_today: int
    blocked_today: int
    input_tokens_today: int
    output_tokens_today: int
    estimated_cost_today_usd: float | None
    cost_known: bool
    daily_request_limit: int
    daily_budget_usd: float
    case_budget_usd: float
    max_calls_per_case: int


class AIUsageRow(BaseModel):
    created_at: datetime
    case_id: str | None
    function: str
    model: str
    status: str
    error_code: str | None
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    total_tokens: int
    cost_usd: float | None
    cost_known: bool


class AIUsageReport(BaseModel):
    provider: str
    model: str
    summary: AIUsageSummary
    recent: list[AIUsageRow]


SystemStatus.model_rebuild()
