from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.api.deps import AppContext, get_ctx, get_service
from app.core.errors import AppError, ErrorResponse
from app.schemas.api import (
    AIUsageReport,
    AIUsageRow,
    AIUsageSummary,
    AnalysisState,
    BriefingListItem,
    CaseCreate,
    CaseDetail,
    CaseListItem,
    CasePatch,
    DashboardData,
    DecisionView,
    FactDefer,
    FactPatch,
    FactView,
    HandoverComplete,
    MessageCreate,
    MessageResult,
    MessageView,
    SystemStatus,
)
from app.schemas.briefing import BriefingView
from app.schemas.decision import DecisionResult
from app.services.cases.service import CaseService
from app.services.decisions.evaluation import EvaluationSummary, run_scenarios
from app.services.knowledge.loader import load_knowledge_base
from app.services.report.pdf import html_to_pdf
from app.services.report.render import render_report_html
from app.services.sources.fedlex.models import FedlexInfo
from app.services.sources.fedlex.provider import CachedFedlexProvider
from app.services.sources.registry import SourceRef, SourceRegistry

ERR = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
router = APIRouter(prefix="/api", responses=ERR)


# ---- system ------------------------------------------------------------------------------
@router.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}


@router.get("/system/status", response_model=SystemStatus, tags=["system"])
def system_status(ctx: AppContext = Depends(get_ctx)) -> SystemStatus:
    external = ctx.ai.name == "gemini"
    return SystemStatus(
        app_env=ctx.settings.app_env,
        ai_provider=ctx.ai.name,
        ai_model=ctx.ai.model,
        ai_is_external=external,
        knowledge_base_version=ctx.kb.version,
        knowledge_base_valid=ctx.kb.valid,
        notice=(
            "Lokaler Entwicklungsmodus ohne Authentifizierung. Nur synthetische Daten verwenden."
            + (" Texte werden an die Gemini-API (extern) übermittelt." if external else "")
        ),
        ai_usage=AIUsageSummary(**ctx.gate.summary()) if external and ctx.gate else None,
    )


@router.get("/ai/usage", response_model=AIUsageReport, tags=["system"])
def ai_usage(ctx: AppContext = Depends(get_ctx)) -> AIUsageReport:
    """Usage of real AI calls (tokens, estimated cost, limits). Reading it never calls the AI."""
    summary = AIUsageSummary(**ctx.gate.summary()) if ctx.gate else None
    rows = ctx.gate.recent() if ctx.gate else []
    return AIUsageReport(
        provider=ctx.ai.name,
        model=ctx.ai.model,
        summary=summary,  # type: ignore[arg-type]
        recent=[
            AIUsageRow(
                created_at=r.created_at,
                case_id=r.case_id,
                function=r.function,
                model=r.model,
                status=r.status,
                error_code=r.error_code,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                thinking_tokens=r.thinking_tokens,
                total_tokens=r.total_tokens,
                cost_usd=r.cost_usd,
                cost_known=r.cost_known,
            )
            for r in rows
        ],
    )


@router.get("/dashboard", response_model=DashboardData, tags=["system"])
def dashboard(svc: CaseService = Depends(get_service)) -> DashboardData:
    return svc.dashboard()


# ---- cases -------------------------------------------------------------------------------
@router.get("/cases", response_model=list[CaseListItem], tags=["cases"])
def list_cases(
    q: str | None = None,
    status: Literal["OPEN", "CLOSED"] | None = None,
    action: Literal["ASK", "PROCEED", "ESCALATE"] | None = None,
    sort: Literal["updated_desc", "updated_asc", "created_desc"] = "updated_desc",
    svc: CaseService = Depends(get_service),
) -> list[CaseListItem]:
    return svc.list_cases(q, status, action, sort)


@router.post("/cases", response_model=CaseDetail, status_code=201, tags=["cases"])
def create_case(body: CaseCreate, svc: CaseService = Depends(get_service)) -> CaseDetail:
    case = svc.create_case(body.title)
    if body.description and body.description.strip():
        from app.domain.enums import MessageKind

        svc.add_message(case.id, body.description, MessageKind.DESCRIPTION, None)
        svc.analyze_pending(case.id)
    return svc.detail(case.id)


@router.get("/cases/{case_id}", response_model=CaseDetail, tags=["cases"])
def get_case(case_id: str, svc: CaseService = Depends(get_service)) -> CaseDetail:
    return svc.detail(case_id)


@router.patch("/cases/{case_id}", response_model=CaseDetail, tags=["cases"])
def patch_case(
    case_id: str, body: CasePatch, svc: CaseService = Depends(get_service)
) -> CaseDetail:
    svc.patch_case(case_id, body.title, body.status)
    return svc.detail(case_id)


# ---- consultation ------------------------------------------------------------------------
@router.get("/cases/{case_id}/messages", response_model=list[MessageView], tags=["consultation"])
def list_messages(case_id: str, svc: CaseService = Depends(get_service)) -> list[MessageView]:
    svc.get_case(case_id)
    return [MessageView.model_validate(m) for m in svc._messages(case_id)]


@router.post(
    "/cases/{case_id}/messages",
    response_model=MessageResult,
    status_code=201,
    tags=["consultation"],
)
def post_message(
    case_id: str, body: MessageCreate, svc: CaseService = Depends(get_service)
) -> MessageResult:
    if body.unknown:
        if not body.answers_fact_id:
            raise AppError("'unknown' braucht answers_fact_id.", code="invalid_value")
        msg = svc.answer_unknown(case_id, body.answers_fact_id)
        analysis = AnalysisState(status="OK")
        return MessageResult(
            message=MessageView.model_validate(msg), analysis=analysis, case=svc.detail(case_id)
        )
    msg = svc.add_message(case_id, body.content, body.kind, body.answers_fact_id)
    analysis = svc.analyze_pending(case_id)
    svc.s.refresh(msg)
    return MessageResult(
        message=MessageView.model_validate(msg),
        analysis=analysis,
        case=svc.detail(case_id, analysis.warnings),
    )


@router.post("/cases/{case_id}/analyze", response_model=CaseDetail, tags=["consultation"])
def analyze(case_id: str, svc: CaseService = Depends(get_service)) -> CaseDetail:
    """Retry analysis of messages whose AI analysis is pending or failed."""
    analysis = svc.analyze_pending(case_id)
    return svc.detail(case_id, analysis.warnings)


# ---- facts -------------------------------------------------------------------------------
@router.get("/cases/{case_id}/facts", response_model=list[FactView], tags=["facts"])
def list_facts(case_id: str, svc: CaseService = Depends(get_service)) -> list[FactView]:
    svc.get_case(case_id)
    return svc.fact_views(case_id)


@router.patch("/cases/{case_id}/facts/{fact_id}", response_model=list[FactView], tags=["facts"])
def patch_fact(
    case_id: str, fact_id: str, body: FactPatch, svc: CaseService = Depends(get_service)
) -> list[FactView]:
    svc.patch_fact(
        case_id,
        fact_id,
        has_value="value" in body.model_fields_set,
        value=body.value,
        status=body.status,
        confirmed=body.confirmed,
        note=body.note,
        documented=body.documented,
    )
    return svc.fact_views(case_id)


class SafetyAcknowledge(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


@router.post(
    "/cases/{case_id}/safety-events/{event_id}/acknowledge",
    response_model=DecisionResult,
    tags=["safety"],
)
def acknowledge_safety(
    case_id: str, event_id: str, body: SafetyAcknowledge, svc: CaseService = Depends(get_service)
) -> DecisionResult:
    """Document that a human handled the signal. The warning stays visible; this is never an all-clear."""
    return svc.acknowledge_safety(case_id, event_id, body.note)


@router.post(
    "/cases/{case_id}/facts/{fact_id}/defer", response_model=list[FactView], tags=["facts"]
)
def defer_fact(
    case_id: str, fact_id: str, body: FactDefer, svc: CaseService = Depends(get_service)
) -> list[FactView]:
    svc.defer_fact(case_id, fact_id, body.reason)
    return svc.fact_views(case_id)


@router.post(
    "/cases/{case_id}/facts/{fact_id}/undefer", response_model=list[FactView], tags=["facts"]
)
def undefer_fact(
    case_id: str, fact_id: str, svc: CaseService = Depends(get_service)
) -> list[FactView]:
    svc.defer_fact(case_id, fact_id, None)
    return svc.fact_views(case_id)


# ---- decisions ---------------------------------------------------------------------------
@router.get("/cases/{case_id}/decisions", response_model=list[DecisionView], tags=["decisions"])
def decisions(case_id: str, svc: CaseService = Depends(get_service)) -> list[DecisionView]:
    return [
        DecisionView(
            id=r.id,
            case_version=r.case_version,
            created_at=r.created_at,
            decision=DecisionResult.model_validate(r.payload),
        )
        for r in svc.decision_history(case_id)
    ]


@router.get(
    "/cases/{case_id}/current-decision", response_model=DecisionResult | None, tags=["decisions"]
)
def current_decision(
    case_id: str, svc: CaseService = Depends(get_service)
) -> DecisionResult | None:
    svc.get_case(case_id)
    return svc.current_decision(case_id)


# ---- handover ----------------------------------------------------------------------------
@router.post("/cases/{case_id}/handover/request", response_model=CaseDetail, tags=["handover"])
def request_handover(case_id: str, svc: CaseService = Depends(get_service)) -> CaseDetail:
    svc.request_handover(case_id)
    return svc.detail(case_id)


@router.post("/cases/{case_id}/handover/complete", response_model=CaseDetail, tags=["handover"])
def complete_handover(
    case_id: str, body: HandoverComplete, svc: CaseService = Depends(get_service)
) -> CaseDetail:
    svc.complete_handover(case_id, body.note)
    return svc.detail(case_id)


# ---- briefings ---------------------------------------------------------------------------
@router.get("/cases/{case_id}/briefings", response_model=list[BriefingListItem], tags=["briefings"])
def list_briefings(case_id: str, svc: CaseService = Depends(get_service)) -> list[BriefingListItem]:
    return [
        BriefingListItem(
            id=r.id,
            version=r.version,
            case_version=r.case_version,
            created_at=r.created_at,
            action=r.payload["decision"]["action"],
        )
        for r in svc.list_briefings(case_id)
    ]


@router.post(
    "/cases/{case_id}/briefings", response_model=BriefingView, status_code=201, tags=["briefings"]
)
def create_briefing(
    case_id: str, svc: CaseService = Depends(get_service), ctx: AppContext = Depends(get_ctx)
) -> BriefingView:
    row = svc.create_briefing(case_id, ctx.ai.name == "gemini")
    return CaseService.briefing_view(row)


@router.get(
    "/cases/{case_id}/briefings/{briefing_id}", response_model=BriefingView, tags=["briefings"]
)
def get_briefing(
    case_id: str, briefing_id: str, svc: CaseService = Depends(get_service)
) -> BriefingView:
    return CaseService.briefing_view(svc.get_briefing(case_id, briefing_id))


class BriefingOverviewItem(BaseModel):
    case: CaseListItem
    latest_briefing_id: str | None
    latest_version: int | None
    latest_created_at: datetime | None
    briefing_count: int


REPORT_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; base-uri 'none'; form-action 'none'",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}


@router.get(
    "/cases/{case_id}/briefings/{briefing_id}/preview",
    response_class=HTMLResponse,
    tags=["briefings"],
)
def briefing_preview(
    case_id: str, briefing_id: str, svc: CaseService = Depends(get_service)
) -> HTMLResponse:
    """A4 preview of a stored report version (HTML, self-contained, no scripts, no external resources)."""
    html = render_report_html(svc.report_view(case_id, briefing_id))
    return HTMLResponse(html, headers=REPORT_HEADERS)


@router.get("/cases/{case_id}/briefings/{briefing_id}/pdf", tags=["briefings"])
def briefing_pdf(
    case_id: str, briefing_id: str, svc: CaseService = Depends(get_service)
) -> Response:
    """Real PDF of a stored report version. No AI call; built from the stored version only."""
    view = svc.report_view(case_id, briefing_id)
    pdf = html_to_pdf(render_report_html(view), view["case_id"])
    name = f"Fallbericht_{view['case_id']}_v{view['version']}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/briefings", response_model=list[BriefingOverviewItem], tags=["briefings"])
def all_latest_briefings(svc: CaseService = Depends(get_service)) -> list[BriefingOverviewItem]:
    """Latest briefing per case (for the 'Expert Briefings' overview)."""
    out = []
    for c in svc.list_cases():
        rows = svc.list_briefings(c.id)
        out.append(
            BriefingOverviewItem(
                case=c,
                latest_briefing_id=rows[0].id if rows else None,
                latest_version=rows[0].version if rows else None,
                latest_created_at=rows[0].created_at if rows else None,
                briefing_count=len(rows),
            )
        )
    return out


# ---- knowledge base ----------------------------------------------------------------------
class KbFileOut(BaseModel):
    path: str
    kind: str
    ok: bool
    version: str | None
    content_status: str | None
    rule_count: int
    errors: list[str]


class ProfessionalOut(BaseModel):
    id: str
    label_de: str
    description_de: str


class KbStatus(BaseModel):
    version: str
    valid: bool
    errors: list[str]
    files: list[KbFileOut]
    issue_count: int
    escalation_rule_count: int
    legal_rule_count: int
    global_rule_count: int
    source_count: int
    unverified_source_count: int
    scenario_count: int
    sources: list[SourceRef]
    professionals: list[ProfessionalOut]


class KbIssueOut(BaseModel):
    id: str
    version: str
    content_status: str
    legal_area: str
    title_de: str
    description: str
    fact_count: int
    required_fact_count: int
    legal_rule_count: int
    escalation_rule_count: int
    source_ids: list[str]
    default_professionals: list[str]


@router.get("/knowledge-base/status", response_model=KbStatus, tags=["knowledge-base"])
def kb_status(ctx: AppContext = Depends(get_ctx)) -> KbStatus:
    kb = ctx.kb
    sources = SourceRegistry(kb, CachedFedlexProvider(ctx.session_factory, ctx.settings, kb)).all()
    return KbStatus(
        version=kb.version,
        valid=kb.valid,
        errors=kb.errors,
        files=[KbFileOut(**f.__dict__) for f in kb.files],
        issue_count=len(kb.issues),
        escalation_rule_count=sum(len(i.escalation_rules) for i in kb.issues.values()),
        legal_rule_count=sum(len(i.legal_rules) for i in kb.issues.values()),
        global_rule_count=len(kb.global_rules),
        source_count=len(sources),
        unverified_source_count=sum(s.verification_status != "VERIFIED" for s in sources),
        scenario_count=len(kb.scenarios),
        sources=sources,
        professionals=[
            ProfessionalOut(id=p.id, label_de=p.label_de, description_de=p.description_de)
            for p in kb.professionals.values()
        ],
    )


@router.get("/knowledge-base/issues", response_model=list[KbIssueOut], tags=["knowledge-base"])
def kb_issues(ctx: AppContext = Depends(get_ctx)) -> list[KbIssueOut]:
    return [
        KbIssueOut(
            id=i.id,
            version=i.version,
            content_status=i.content_status,
            legal_area=i.legal_area,
            title_de=i.title_de,
            description=i.description,
            fact_count=len(i.facts),
            required_fact_count=sum(1 for f in i.facts if f.required or f.required_if),
            legal_rule_count=len(i.legal_rules),
            escalation_rule_count=len(i.escalation_rules),
            source_ids=i.legal_source_ids,
            default_professionals=i.default_professionals,
        )
        for i in ctx.kb.issues.values()
    ]


@router.post("/knowledge-base/reload", response_model=KbStatus, tags=["knowledge-base"])
def kb_reload(ctx: AppContext = Depends(get_ctx)) -> KbStatus:
    """Developer convenience: re-read the YAML files without restarting the server."""
    ctx.kb = load_knowledge_base(ctx.settings.knowledge_base_dir)
    return kb_status(ctx)


# ---- evaluation --------------------------------------------------------------------------
class ScenarioListItem(BaseModel):
    id: str
    title_de: str
    validation: str
    expected_action: str


@router.get("/evaluation/scenarios", response_model=list[ScenarioListItem], tags=["evaluation"])
def eval_scenarios(ctx: AppContext = Depends(get_ctx)) -> list[ScenarioListItem]:
    return [
        ScenarioListItem(
            id=s.id,
            title_de=s.title_de,
            validation=s.validation,
            expected_action=s.expected_action,
        )
        for s in ctx.kb.scenarios
    ]


@router.post("/evaluation/run", response_model=EvaluationSummary, tags=["evaluation"])
def eval_run(ctx: AppContext = Depends(get_ctx)) -> EvaluationSummary:
    return run_scenarios(ctx.kb)


# ---- sources (Fedlex) --------------------------------------------------------------------------------
class FedlexSyncRequest(BaseModel):
    issue_id: str | None = None
    source_ids: list[str] = []
    force: bool = False
    offline: bool = False
    reference_date: date | None = None


class FedlexSyncResultOut(BaseModel):
    source_id: str
    status: str
    message: str
    label: str
    version_identifier: str | None
    wording_status: str | None
    newer_version: str | None


class FedlexSyncReportOut(BaseModel):
    reference_date: str
    referenced: int
    retrieved: int
    cached: int
    failed: int
    skipped: int
    requests: int
    offline: bool
    results: list[FedlexSyncResultOut]


class FedlexStatusRow(BaseModel):
    source_id: str
    title_de: str
    info: FedlexInfo


def _fedlex(ctx: AppContext):
    from app.services.sources.fedlex.service import FedlexService

    return FedlexService(ctx.session_factory, ctx.settings, ctx.kb)


@router.get("/sources/fedlex/status", response_model=list[FedlexStatusRow], tags=["sources"])
def fedlex_status(
    issue_id: str | None = None, ctx: AppContext = Depends(get_ctx)
) -> list[FedlexStatusRow]:
    """Cache status of every Fedlex-backed source. Reads the local cache only; never contacts Fedlex."""
    from app.services.sources.fedlex.service import is_fedlex_statute

    svc = _fedlex(ctx)
    ids = svc.collect_issue_sources(issue_id) if issue_id else list(ctx.kb.sources)
    provider = CachedFedlexProvider(ctx.session_factory, ctx.settings, ctx.kb)
    return [
        FedlexStatusRow(source_id=i, title_de=ctx.kb.sources[i].title_de, info=provider.info(i))
        for i in ids
        if is_fedlex_statute(ctx.kb.sources[i])
    ]


@router.post("/sources/fedlex/sync", response_model=FedlexSyncReportOut, tags=["sources"])
def fedlex_sync(body: FedlexSyncRequest, ctx: AppContext = Depends(get_ctx)) -> FedlexSyncReportOut:
    """Explicit, deterministic sync of referenced statutes (the ONLY route that may contact Fedlex)."""
    svc = _fedlex(ctx)
    if body.issue_id:
        if body.issue_id not in ctx.kb.issues:
            raise AppError("Unbekanntes Issue.", code="unknown_issue")
        ids = svc.collect_issue_sources(body.issue_id)
    elif body.source_ids:
        ids = body.source_ids
    else:
        ids = svc.all_referenced_sources()
    ref = body.reference_date or ctx.settings.app_today or date.today()
    rep = svc.sync(ids, ref, force=body.force, offline=body.offline)
    return FedlexSyncReportOut(
        reference_date=rep.reference_date,
        referenced=len(rep.results),
        retrieved=rep.count("RETRIEVED"),
        cached=rep.count("CACHED"),
        failed=len(rep.failed),
        skipped=rep.count("SKIPPED"),
        requests=rep.requests,
        offline=rep.offline,
        results=[FedlexSyncResultOut(**vars(r)) for r in rep.results],
    )


FedlexStatusRow.model_rebuild()
