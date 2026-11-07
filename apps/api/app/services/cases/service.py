"""Case workflow: persistence, AI analysis, fact merging, decision refresh, briefing."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ConflictError, NotFoundError
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
from app.domain.state import CaseSnapshot, FactState, IssueState
from app.models.tables import (
    BriefingVersion,
    Case,
    CaseFact,
    CaseIssue,
    CaseMessage,
    DecisionRecord,
    Handover,
    SafetyEvent,
)
from app.schemas.api import (
    AnalysisState,
    CaseDetail,
    CaseListItem,
    DashboardData,
    FactHistoryEntry,
    FactView,
    HandoverView,
    IssueView,
)
from app.schemas.briefing import BriefingView, CaseBriefing
from app.schemas.decision import DecisionResult
from app.services.ai.base import AIBudgetExceededError, AIProvider, AIProviderError, CallContext
from app.services.ai.deterministic import parse_simple_answer
from app.services.ai.issue_keywords import candidate_issue_ids
from app.services.ai.schemas import (
    ExtractionInput,
    FactCatalogEntry,
    InputMessage,
    IssueCatalogEntry,
)
from app.services.ai.validation import ValidatedExtraction, coerce_value, validate_extraction
from app.services.briefings.generator import build_briefing
from app.services.decisions.engine import decide
from app.services.decisions.missing import effective_required
from app.services.knowledge.loader import KnowledgeBase
from app.services.policy.guard import sanitize
from app.services.referrals.network import Location
from app.services.report.extras import build_extras
from app.services.report.view import build_view
from app.services.safety.assess import SafetyEventState, assess_safety
from app.services.safety.detector import Detector

log = logging.getLogger(__name__)

DEFAULT_TITLE = "Neuer Fall"
EARLIER_MESSAGE_LIMIT = 20
REDACTED_EVIDENCE = "[Wortlaut aus Datenschutzgründen nicht gespeichert]"
DUPLICATE_WINDOW_SECONDS = 10

# One analysis per case at a time: a double click / parallel request must not trigger the same paid
# analysis twice. (Process-local; the app runs as a single process.)
_INFLIGHT: set[str] = set()
_INFLIGHT_LOCK = threading.Lock()


@contextmanager
def _single_flight(case_id: str) -> Iterator[None]:
    with _INFLIGHT_LOCK:
        if case_id in _INFLIGHT:
            raise ConflictError("Die Analyse für diesen Fall läuft bereits. Bitte kurz warten.")
        _INFLIGHT.add(case_id)
    try:
        yield
    finally:
        with _INFLIGHT_LOCK:
            _INFLIGHT.discard(case_id)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; every stored timestamp is UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _hist(event: str, value: Any = None, by: str = "system", note: str | None = None) -> dict:
    return {"at": _now().isoformat(), "event": event, "value": value, "by": by, "note": note}


class CaseService:
    def __init__(
        self,
        session: Session,
        kb: KnowledgeBase,
        ai: AIProvider,
        *,
        rephrase_questions: bool = False,
        today: date | None = None,
        max_attempts: int = 3,
        source_provider: Any = None,
    ):
        self.s = session
        self.kb = kb
        self.ai = ai
        self.rephrase_questions = rephrase_questions
        self.today = today  # None = real today; set for reproducible demos/tests
        self.max_attempts = max_attempts
        self.source_provider = (
            source_provider  # read-only Fedlex cache provider (never the network)
        )
        self.detector = Detector(kb.safety_config) if kb.safety_config is not None else None

    # ------------------------------------------------------------------ basic access -----
    def get_case(self, case_id: str) -> Case:
        case = self.s.get(Case, case_id)
        if case is None:
            raise NotFoundError("Fall nicht gefunden.")
        return case

    def _messages(self, case_id: str) -> list[CaseMessage]:
        return list(
            self.s.scalars(
                select(CaseMessage)
                .where(CaseMessage.case_id == case_id)
                .order_by(CaseMessage.created_at, CaseMessage.id)
            )
        )

    def _issues(self, case_id: str) -> list[CaseIssue]:
        return list(
            self.s.scalars(
                select(CaseIssue).where(CaseIssue.case_id == case_id).order_by(CaseIssue.created_at)
            )
        )

    def _fact_rows(self, case_id: str) -> list[CaseFact]:
        return list(self.s.scalars(select(CaseFact).where(CaseFact.case_id == case_id)))

    def _handover(self, case_id: str) -> Handover | None:
        return self.s.scalar(select(Handover).where(Handover.case_id == case_id))

    def _latest_decision_row(self, case_id: str) -> DecisionRecord | None:
        return self.s.scalar(
            select(DecisionRecord)
            .where(DecisionRecord.case_id == case_id)
            .order_by(DecisionRecord.created_at.desc(), DecisionRecord.id.desc())
            .limit(1)
        )

    def _latest_briefing_row(self, case_id: str) -> BriefingVersion | None:
        return self.s.scalar(
            select(BriefingVersion)
            .where(BriefingVersion.case_id == case_id)
            .order_by(BriefingVersion.version.desc())
            .limit(1)
        )

    def _touch(self, case: Case) -> None:
        case.version += 1
        case.updated_at = _now()

    # ------------------------------------------------------------------ create / list ----
    def _next_display_id(self) -> str:
        last = self.s.scalar(select(func.max(Case.display_id)))
        n = int(last.split("-")[1]) + 1 if last else 1
        return f"FALL-{n:04d}"

    def create_case(self, title: str = "") -> Case:
        case = Case(
            display_id=self._next_display_id(), title=title.strip() or DEFAULT_TITLE, summary=""
        )
        self.s.add(case)
        self.s.commit()
        return case

    def patch_case(self, case_id: str, title: str | None, status: CaseStatus | None) -> Case:
        case = self.get_case(case_id)
        if title is not None:
            case.title = title.strip()
        if status is not None:
            case.status = status.value
        self._touch(case)
        self.s.commit()
        return case

    def _issue_titles(self, case_id: str) -> list[str]:
        out = []
        for i in self._issues(case_id):
            if (
                i.classification_status == IssueStatus.DETECTED
                and i.issue_definition_id in self.kb.issues
            ):
                out.append(self.kb.issues[i.issue_definition_id].title_de)
        return out

    def _pending_ids(self, case_id: str) -> list[str]:
        return [m.id for m in self._messages(case_id) if m.analysis_status != AnalysisStatus.DONE]

    def _list_item(self, c: Case) -> CaseListItem:
        h = self._handover(c.id)
        return CaseListItem(
            id=c.id,
            display_id=c.display_id,
            title=c.title,
            status=CaseStatus(c.status),
            current_action=Action(c.current_action) if c.current_action else None,
            issue_titles=self._issue_titles(c.id),
            handover_status=HandoverStatus(h.status) if h else None,
            analysis_pending=bool(self._pending_ids(c.id)),
            safety_state=self._safety_state(c.id),  # type: ignore[arg-type]
            created_at=_aware(c.created_at),  # type: ignore[arg-type]
            updated_at=_aware(c.updated_at),  # type: ignore[arg-type]
            version=c.version,
        )

    def list_cases(
        self,
        q: str | None = None,
        status: str | None = None,
        action: str | None = None,
        sort: str = "updated_desc",
    ) -> list[CaseListItem]:
        stmt = select(Case)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(or_(Case.display_id.ilike(like), Case.title.ilike(like)))
        if status:
            stmt = stmt.where(Case.status == status)
        if action:
            stmt = stmt.where(Case.current_action == action)
        order = {
            "updated_desc": Case.updated_at.desc(),
            "updated_asc": Case.updated_at.asc(),
            "created_desc": Case.created_at.desc(),
        }.get(sort, Case.updated_at.desc())
        return [self._list_item(c) for c in self.s.scalars(stmt.order_by(order))]

    def dashboard(self) -> DashboardData:
        def count(*conds: Any) -> int:
            return self.s.scalar(select(func.count()).select_from(Case).where(*conds)) or 0

        awaiting = (
            self.s.scalar(
                select(func.count())
                .select_from(Handover)
                .join(Case, Case.id == Handover.case_id)
                .where(
                    Handover.status.in_(
                        [HandoverStatus.RECOMMENDED.value, HandoverStatus.HANDOFF_REQUESTED.value]
                    ),
                    Case.status == CaseStatus.OPEN.value,
                )
            )
            or 0
        )
        recent = self.s.scalars(select(Case).order_by(Case.updated_at.desc()).limit(6))
        return DashboardData(
            total_cases=count(),
            open_cases=count(Case.status == CaseStatus.OPEN.value),
            needs_clarification=count(
                Case.status == CaseStatus.OPEN.value, Case.current_action == Action.ASK.value
            ),
            escalated=count(
                Case.status == CaseStatus.OPEN.value, Case.current_action == Action.ESCALATE.value
            ),
            awaiting_professional_review=awaiting,
            recent=[self._list_item(c) for c in recent],
        )

    # ------------------------------------------------------------------ snapshot ---------
    def snapshot(self, case_id: str) -> CaseSnapshot:
        self.s.flush()  # session has autoflush off: make pending rows visible to the queries below
        msgs = self._messages(case_id)
        has_input = any(
            m.role == MessageRole.SOCIAL_WORKER.value and m.analysis_status == AnalysisStatus.DONE
            for m in msgs
        )
        issues = [
            IssueState(
                status=IssueStatus(i.classification_status),
                issue_id=i.issue_definition_id,
                confidence=i.confidence,
                description=i.description,
            )
            for i in self._issues(case_id)
        ]
        facts = {
            f.fact_id: FactState(
                status=FactStatus(f.status), value=f.value, deferred=bool(f.deferred_reason)
            )
            for f in self._fact_rows(case_id)
        }
        return CaseSnapshot(
            has_user_input=has_input,
            issues=issues,
            facts=facts,
            today=self.today or date.today(),
            safety_events=self._safety_states(case_id),
        )

    # ------------------------------------------------------------------ safety -----------
    def _safety_states(self, case_id: str) -> list[SafetyEventState]:
        rows = self.s.scalars(
            select(SafetyEvent)
            .where(SafetyEvent.case_id == case_id)
            .order_by(SafetyEvent.detected_at, SafetyEvent.id)
        )
        return [
            SafetyEventState(
                id=r.id,
                category=r.category,
                certainty=r.certainty,
                evidence=r.evidence,
                rule_id=r.rule_id,
                message_id=r.message_id,
                modifiers=list(r.modifiers or []),
                detected_at=_aware(r.detected_at),
                acknowledged=r.acknowledged_at is not None,
                acknowledged_note=r.acknowledged_note,
                acknowledged_at=_aware(r.acknowledged_at),
            )
            for r in rows
        ]

    def _safety_state(self, case_id: str) -> str:
        return assess_safety(self.kb, self._safety_states(case_id), Location(), []).state

    def detect_safety(self, case: Case, msg: CaseMessage) -> int:
        """Deterministic detection on the raw user text. Independent of AI, issue classification and analysis
        status: it must also work when the AI call fails or the legal issue is unsupported."""
        if self.detector is None:
            return 0
        net = self.kb.referral_network
        actions = {r.category: r.action for r in net.safety_routing} if net else {}
        found = self.detector.detect(msg.content)
        for sig in found:
            self.s.add(
                SafetyEvent(
                    case_id=case.id,
                    message_id=msg.id,
                    category=sig.category,
                    certainty=sig.certainty,
                    action=actions.get(sig.category, "ESCALATE"),
                    rule_id=sig.rule_id,
                    evidence=sig.evidence,
                    modifiers=sig.modifiers,
                )
            )
        return len(found)

    def acknowledge_safety(self, case_id: str, event_id: str, note: str) -> DecisionResult:
        """A human documents that they handled/checked the signal. The warning stays visible (no all-clear)."""
        case = self.get_case(case_id)
        row = self.s.get(SafetyEvent, event_id)
        if row is None or row.case_id != case_id:
            raise NotFoundError("Sicherheitshinweis nicht gefunden.")
        row.acknowledged_at = _now()
        row.acknowledged_note = note.strip()
        self._touch(case)
        result = self.refresh_decision(case)
        self.s.commit()
        return result

    def evaluate(self, case_id: str) -> DecisionResult:
        return decide(self.kb, self.snapshot(case_id))

    # ------------------------------------------------------------------ decisions --------
    def refresh_decision(self, case: Case) -> DecisionResult:
        """Re-evaluate; persist a decision row only when the outcome changed."""
        result = self.evaluate(case.id)
        if self.rephrase_questions and result.next_question and result.next_question.fact_id:
            try:
                reworded = self.ai.rephrase_question(
                    result.next_question.question_de,
                    case.summary,
                    CallContext(case.id, "rephrase_question"),
                )
                # AI free text never bypasses the statement policy: a violation keeps the template.
                safe, hits = sanitize(self.kb, reworded, fallback=result.next_question.question_de)
                if hits:
                    log.warning("Reworded question rejected by statement policy: %s", hits)
                result.next_question.question_de = safe
            except AIProviderError:
                log.info("Question rephrasing failed; using template question.")
        sig = result.signature()
        last = self._latest_decision_row(case.id)
        if last is None or last.signature != sig:
            self.s.add(
                DecisionRecord(
                    case_id=case.id,
                    case_version=case.version,
                    action=result.action.value,
                    main_reason_code=result.main_reason_code,
                    reason_codes=result.reason_codes,
                    triggered_rule_ids=result.triggered_rule_ids,
                    knowledge_base_version=result.knowledge_base_version,
                    signature=sig,
                    payload=result.model_dump(mode="json"),
                )
            )
        case.current_action = result.action.value
        self._sync_handover(case, result)
        return result

    def _sync_handover(self, case: Case, result: DecisionResult) -> None:
        h = self._handover(case.id)
        immediate = bool(result.safety and result.safety.state == "IMMEDIATE")
        if result.action == Action.ESCALATE or immediate:
            reasons = [t.reason_de for t in result.triggered_rules]
            if immediate and result.safety and result.safety.headline_de:
                reasons = [result.safety.headline_de, *reasons]
            if h is None:
                self.s.add(
                    Handover(
                        case_id=case.id,
                        professional_types=result.recommended_professionals,
                        reasons=reasons,
                        status=HandoverStatus.RECOMMENDED.value,
                    )
                )
            else:
                h.professional_types = result.recommended_professionals
                h.reasons = reasons
        elif h is not None and h.status == HandoverStatus.RECOMMENDED.value:
            self.s.delete(h)  # recommendation no longer applies; requested/completed are kept

    def current_decision(self, case_id: str) -> DecisionResult | None:
        """Live (pure, deterministic) decision - unless analysis is pending/failed."""
        if self._pending_ids(case_id):
            row = self._latest_decision_row(case_id)
            return DecisionResult.model_validate(row.payload) if row else None
        return self.evaluate(case_id)

    def decision_history(self, case_id: str) -> list[DecisionRecord]:
        self.get_case(case_id)
        return list(
            self.s.scalars(
                select(DecisionRecord)
                .where(DecisionRecord.case_id == case_id)
                .order_by(DecisionRecord.created_at.desc(), DecisionRecord.id.desc())
            )
        )

    # ------------------------------------------------------------------ messages ---------
    def add_message(
        self,
        case_id: str,
        content: str,
        kind: MessageKind,
        answers_fact_id: str | None,
        *,
        origin: str | None = None,
        original_text: str | None = None,
        original_language: str | None = None,
    ) -> CaseMessage:
        case = self.get_case(case_id)
        if case.status == CaseStatus.CLOSED.value:
            raise ConflictError("Der Fall ist abgeschlossen. Bitte zuerst wieder öffnen.")
        if answers_fact_id is not None:
            if not any(f.id == answers_fact_id for i in self.kb.issues.values() for f in i.facts):
                raise AppError(f"Unbekannte Fakt-ID '{answers_fact_id}'.", code="unknown_fact")
            kind = MessageKind.ANSWER
        text = content.strip()
        msgs = self._messages(case_id)
        last = msgs[-1] if msgs else None
        if (
            last is not None
            and last.content == text
            and last.answers_fact_id == answers_fact_id
            and (_now() - _aware(last.created_at)).total_seconds() < DUPLICATE_WINDOW_SECONDS  # type: ignore[operator]
        ):
            return last  # double submit: never create (or pay for) the same input twice
        msg = CaseMessage(
            case_id=case_id,
            role=MessageRole.SOCIAL_WORKER.value,
            kind=kind.value,
            content=text,
            answers_fact_id=answers_fact_id,
            analysis_status=AnalysisStatus.PENDING.value,
            origin=origin,
            original_text=original_text,
            original_language=original_language,
        )
        self.s.add(msg)
        self._touch(case)
        self.s.flush()
        # Safety first: detected before and independent of any AI call; the decision (with safety overlay) is
        # refreshed right away so a danger is never hidden behind a failed or pending analysis.
        if self.detect_safety(case, msg):
            self.refresh_decision(case)
        self.s.commit()  # user input is never lost, even if the AI call fails
        return msg

    def _try_deterministic(self, case: Case, m: CaseMessage, rows: dict[str, CaseFact]) -> bool:
        """Simple direct answers ("Ja", a date, a choice) are parsed locally - no AI call, no cost."""
        if not m.answers_fact_id:
            return False
        fd = self._fact_def(m.answers_fact_id)
        if fd is None:
            return False
        parsed = parse_simple_answer(fd, m.content)
        if parsed is None:
            return False
        kind, value = parsed
        self._merge_fact(
            case.id,
            rows,
            fact_id=fd.id,
            typed=value,
            ambiguous=(kind == "ambiguous"),
            unknown=(kind == "unknown"),
            quote=m.content,
            message_id=m.id,
            is_answer=True,
            note=None,
        )
        m.analysis_status = AnalysisStatus.DONE.value
        m.analysis_error = None
        return True

    def analyze_pending(self, case_id: str) -> AnalysisState:
        case = self.get_case(case_id)
        pending = [m for m in self._messages(case_id) if m.analysis_status != AnalysisStatus.DONE]
        if not pending:
            self.refresh_decision(case)
            self.s.commit()
            return AnalysisState(status="OK")

        with _single_flight(case_id):
            exhausted = [
                m
                for m in pending
                if m.analysis_status == AnalysisStatus.FAILED.value
                and m.analysis_attempts >= self.max_attempts
            ]
            if exhausted:
                raise ConflictError(
                    f"Die Analyse wurde bereits {self.max_attempts}-mal versucht und ist fehlgeschlagen. "
                    "Bitte die Eingabe prüfen oder später erneut versuchen (keine weiteren automatischen Versuche)."
                )

            # 1) simple direct answers: parsed locally
            rows = {f.fact_id: f for f in self._fact_rows(case_id)}
            local = [m for m in pending if self._try_deterministic(case, m, rows)]
            if local:
                self._touch(case)
                self.refresh_decision(case)
                self.s.commit()
            remaining = [m for m in pending if m not in local]
            if not remaining:
                return AnalysisState(status="OK")

            # 2) everything else goes to the AI extractor
            return self._analyze_with_ai(case, remaining)

    def _fact_scope(self, case_id: str, texts: list[str], available: set[str]) -> set[str] | None:
        """Issue ids whose facts may be offered to the extractor (None = all)."""
        active = [
            i.issue_id
            for i in self.snapshot(case_id).issues
            if i.status == IssueStatus.DETECTED and i.issue_id in self.kb.issues
        ]
        guess = candidate_issue_ids(texts, available)
        base = list(dict.fromkeys([*active, *guess]))
        if not base:
            # Nothing plausible yet: classify only; offer just the most common issue's facts (cost control).
            return {"CH_TENANCY_TERMINATION"} & available
        return set(base[:3])  # at most three issues' facts per call

    def _fact_catalog(self, scope: set[str] | None) -> list[FactCatalogEntry]:
        seen: dict[str, FactCatalogEntry] = {}
        for d in self.kb.issues.values():
            if scope is not None and d.id not in scope:
                continue
            for f in d.facts:
                seen.setdefault(
                    f.id,
                    FactCatalogEntry(
                        id=f.id,
                        label_de=f.label_de,
                        data_type=f.data_type,
                        enum_values=f.enum_values,
                        enum_labels_de=f.enum_labels_de,
                        hint_de=f.extraction_hint_de,
                        question_de=f.question_de,
                    ),
                )
        return list(seen.values())

    def _second_pass(
        self,
        case_id: str,
        data: ExtractionInput,
        scope: set[str] | None,
        validated: ValidatedExtraction,
        pending,
    ) -> list[str]:
        """Stage 2: the first call detected issues whose facts were not offered -> one more small call for exactly
        those issues (same messages). Never loops; a failure keeps the stage-1 result."""
        detected = [i.issue_id for i in validated.issues if i.issue_id in self.kb.issues]
        missing = [i for i in dict.fromkeys(detected) if scope is not None and i not in scope][:3]
        if not missing:
            return []
        data2 = data.model_copy(
            update={
                "issue_catalog": [c for c in data.issue_catalog if c.id in missing],
                "fact_catalog": self._fact_catalog(set(missing)),
            }
        )
        try:
            raw2 = self.ai.extract(data2, CallContext(case_id, "extract_facts"))
        except AIProviderError as exc:
            log.warning("Second-stage fact extraction skipped: %s", exc.code)
            return [
                f"Zweite Faktenerkennung übersprungen ({exc.code}); offene Fragen werden gestellt."
            ]
        v2 = validate_extraction(raw2, self.kb, {m.id: m.content for m in pending})
        have = {ef.fact_id for ef, _ in validated.facts}
        validated.facts.extend(x for x in v2.facts if x[0].fact_id not in have)
        for k, val in v2.contradictions.items():
            validated.contradictions.setdefault(k, val)
        validated.warnings.extend(v2.warnings)
        return []

    def _analyze_with_ai(self, case: Case, pending: list[CaseMessage]) -> AnalysisState:
        case_id = case.id
        earlier = [m for m in self._messages(case_id) if m.analysis_status == AnalysisStatus.DONE][
            -EARLIER_MESSAGE_LIMIT:
        ]
        known_text: dict[str, str] = {}
        for f in self._fact_rows(case_id):
            if f.status == FactStatus.KNOWN.value:
                known_text[f.fact_id] = str(f.value)

        if not self.kb.valid:
            # Never classify against a broken knowledge base: supported issues that failed to load would otherwise be
            # reported as «nicht abgedeckt» and silently escalate.
            msg = (
                f"Die Wissensbasis ist fehlerhaft ({len(self.kb.errors)} Fehler). Es wird nicht analysiert, damit "
                "unterstützte Rechtsprobleme nicht fälschlich als «nicht abgedeckt» gelten. Bitte die Wissensbasis "
                "korrigieren und neu laden (POST /api/knowledge-base/reload) oder den Server neu starten."
            )
            for m in pending:
                m.analysis_status = AnalysisStatus.FAILED.value
                m.analysis_error = msg
            self.s.commit()
            log.error(
                "AI analysis blocked: knowledge base invalid (%d errors)", len(self.kb.errors)
            )
            return AnalysisState(
                status="FAILED",
                pending_message_ids=[m.id for m in pending],
                error_code="knowledge_base_invalid",
                error_message=msg,
            )
        catalog_issues = self.kb.catalog_issues()
        issue_catalog = [
            IssueCatalogEntry(
                id=d.id,
                title_de=d.title_de,
                description=d.classification.description or d.description,
                typical_situations=d.classification.typical_situations,
            )
            for d in catalog_issues
        ]
        # Cost control: offer the fact catalog only for plausible issues (already detected or matched by the cheap
        # keyword pre-filter; routed issues are asked via questions, not extracted from free text). Fallback: all issues.
        texts = [m.content for m in pending] + [m.content for m in earlier]
        scope = self._fact_scope(case_id, texts, {d.id for d in catalog_issues})
        fact_catalog = self._fact_catalog(scope)
        data = ExtractionInput(
            new_messages=[
                InputMessage(
                    id=m.id, kind=m.kind, content=m.content, answers_fact_id=m.answers_fact_id
                )
                for m in pending
            ],
            earlier_messages=[
                InputMessage(id=m.id, kind=m.kind, content=m.content) for m in earlier
            ],
            issue_catalog=issue_catalog,
            fact_catalog=fact_catalog,
            known_facts=known_text,
            existing_summary=case.summary,
            today=(self.today or date.today()).isoformat(),
        )

        try:
            raw = self.ai.extract(data, CallContext(case_id, "extract"))
        except AIProviderError as exc:
            counted = not isinstance(
                exc, AIBudgetExceededError
            )  # blocked-before-send is not an attempt
            for m in pending:
                m.analysis_status = AnalysisStatus.FAILED.value
                m.analysis_error = exc.message
                if counted:
                    m.analysis_attempts = (m.analysis_attempts or 0) + 1
            self.s.commit()
            log.warning("AI analysis failed for %s: %s", case.display_id, exc.code)
            return AnalysisState(
                status="FAILED",
                pending_message_ids=[m.id for m in pending],
                error_code=exc.code,
                error_message=exc.message,
            )

        validated = validate_extraction(
            raw,
            self.kb,
            {m.id: m.content for m in pending},
            {d.id for d in catalog_issues},
        )
        validated.warnings.extend(self._second_pass(case_id, data, scope, validated, pending))
        try:
            self._apply(case, pending, validated)
            for m in pending:
                m.analysis_status = AnalysisStatus.DONE.value
                m.analysis_error = None
                m.analysis_attempts = (m.analysis_attempts or 0) + 1
            self._touch(case)
            self.refresh_decision(case)
            self.s.commit()
        except Exception:
            self.s.rollback()
            raise
        return AnalysisState(status="OK", warnings=validated.warnings)

    def answer_unknown(self, case_id: str, fact_id: str) -> CaseMessage:
        """The person was asked and does not know. Recorded locally (no AI call); never re-asked."""
        case = self.get_case(case_id)
        if case.status == CaseStatus.CLOSED.value:
            raise ConflictError("Der Fall ist abgeschlossen. Bitte zuerst wieder öffnen.")
        fd = self._fact_def(fact_id)
        if fd is None:
            raise AppError(f"Unbekannte Fakt-ID '{fact_id}'.", code="unknown_fact")
        rows = {f.fact_id: f for f in self._fact_rows(case_id)}
        existing = rows.get(fact_id)
        if existing is not None and existing.status in (
            FactStatus.KNOWN.value,
            FactStatus.NOT_APPLICABLE.value,
        ):
            raise AppError(
                "Diese Angabe ist bereits bekannt. Bitte den Wert im Fallüberblick korrigieren.",
                code="invalid_state",
            )
        msg = CaseMessage(
            case_id=case_id,
            role=MessageRole.SOCIAL_WORKER.value,
            kind=MessageKind.ANSWER.value,
            content="Weiss nicht.",
            answers_fact_id=fact_id,
            analysis_status=AnalysisStatus.DONE.value,
        )
        self.s.add(msg)
        self.s.flush()
        self._merge_fact(
            case_id,
            rows,
            fact_id=fact_id,
            typed=None,
            ambiguous=False,
            unknown=True,
            quote=msg.content,
            message_id=msg.id,
            is_answer=True,
            note=None,
        )
        self._touch(case)
        self.refresh_decision(case)
        self.s.commit()
        return msg

    # ------------------------------------------------------------------ apply AI output ---
    def _apply(self, case: Case, pending: list[CaseMessage], v: ValidatedExtraction) -> None:
        answers = {m.id: m.answers_fact_id for m in pending}

        existing_issue = {
            i.issue_definition_id: i
            for i in self._issues(case.id)
            if i.classification_status == IssueStatus.DETECTED.value
        }
        for di in v.issues:
            row = existing_issue.get(di.issue_id)
            if row is None:
                self.s.add(
                    CaseIssue(
                        case_id=case.id,
                        issue_definition_id=di.issue_id,
                        classification_status=IssueStatus.DETECTED.value,
                        confidence=di.confidence,
                        evidence=di.evidence_quote,
                        source_message_id=di.source_message_id,
                    )
                )
            elif row.confidence is None or di.confidence > row.confidence:
                row.confidence = di.confidence
                row.evidence = di.evidence_quote
                row.source_message_id = di.source_message_id

        have_unsupported = {
            (i.description or "").casefold()
            for i in self._issues(case.id)
            if i.classification_status == IssueStatus.UNSUPPORTED.value
        }
        for ui in v.unsupported:
            if ui.description.casefold() in have_unsupported:
                continue
            have_unsupported.add(ui.description.casefold())
            self.s.add(
                CaseIssue(
                    case_id=case.id,
                    issue_definition_id=None,
                    classification_status=IssueStatus.UNSUPPORTED.value,
                    description=ui.description,
                    evidence=ui.evidence_quote,
                    source_message_id=ui.source_message_id,
                )
            )

        rows = {f.fact_id: f for f in self._fact_rows(case.id)}
        for ef, typed in v.facts:
            is_answer = answers.get(ef.source_message_id) == ef.fact_id
            self._merge_fact(
                case.id,
                rows,
                fact_id=ef.fact_id,
                typed=typed,
                ambiguous=ef.ambiguous,
                unknown=ef.unknown,
                quote=ef.evidence_quote,
                message_id=ef.source_message_id,
                is_answer=is_answer,
                note=ef.ambiguity_note or v.contradictions.get(ef.fact_id),
            )

        if v.summary:
            safe, hits = sanitize(self.kb, v.summary[:2000])
            if hits:
                log.warning("AI summary rejected by statement policy: %s", hits)
            case.summary = safe
        if case.title == DEFAULT_TITLE:
            self.s.flush()
            titles = self._issue_titles(case.id)
            if titles:
                case.title = " · ".join(titles)[:200]

    def _merge_fact(
        self,
        case_id: str,
        rows: dict[str, CaseFact],
        *,
        fact_id: str,
        typed: Any,
        ambiguous: bool,
        quote: str,
        message_id: str,
        is_answer: bool,
        note: str | None,
        unknown: bool = False,
    ) -> None:
        origin = FactOrigin.USER_ANSWER if is_answer else FactOrigin.AI_EXTRACTED
        by = "social_worker" if is_answer else "ai"
        fd = self._fact_def(fact_id)
        if fd is not None and not fd.store_evidence:
            quote = REDACTED_EVIDENCE  # health details: store the yes/no value, never the wording
        row = rows.get(fact_id)
        if unknown:
            new_status = FactStatus.UNKNOWN
        else:
            new_status = FactStatus.AMBIGUOUS if ambiguous else FactStatus.KNOWN

        if row is None:
            if unknown and not is_answer:
                return  # "unknown" is only valid as the answer to a question
            row = CaseFact(case_id=case_id, fact_id=fact_id, history=[], conflicting_values=[])
            self.s.add(row)
            rows[fact_id] = row
            self._write_fact(row, new_status, typed, origin, quote, message_id)
            event = (
                "unknown"
                if unknown
                else "ambiguous"
                if ambiguous
                else ("answered" if is_answer else "extracted")
            )
            row.history = [_hist(event, typed, by, note)]
            return

        history = list(row.history or [])
        protected = row.confirmed or row.origin == FactOrigin.USER_CORRECTION.value
        current_known = row.status == FactStatus.KNOWN.value

        if new_status == FactStatus.UNKNOWN:
            if not is_answer or current_known or row.status == FactStatus.NOT_APPLICABLE.value:
                history.append(
                    _hist("unknown_ignored", None, by, "Nur als Antwort auf eine Frage gültig.")
                )
            else:
                self._write_fact(row, FactStatus.UNKNOWN, None, origin, quote, message_id)
                row.conflicting_values = []
                history.append(_hist("unknown", None, by, note))
            row.history = history
            return

        if new_status == FactStatus.AMBIGUOUS:
            if current_known:
                history.append(_hist("ambiguous_ignored", None, by, note))
            elif is_answer and row.status == FactStatus.UNKNOWN.value:
                history.append(
                    _hist("ambiguous_ignored", None, by, "Bereits als unbekannt erfasst.")
                )
            elif is_answer and any(
                h.get("event") == "ambiguous" and h.get("by") == "social_worker" for h in history
            ):
                # asked twice, still unclear: stop asking and treat as unknown (no endless loops)
                self._write_fact(row, FactStatus.UNKNOWN, None, origin, quote, message_id)
                history.append(
                    _hist(
                        "ambiguity_exhausted",
                        None,
                        by,
                        "Zweimal unklar beantwortet: gilt als unbekannt.",
                    )
                )
            elif is_answer or row.status == FactStatus.MISSING.value:
                self._write_fact(row, FactStatus.AMBIGUOUS, None, origin, quote, message_id)
                history.append(_hist("ambiguous", None, by, note))
            row.history = history
            return

        # new value is KNOWN
        if row.status == FactStatus.NOT_APPLICABLE.value and row.confirmed and not is_answer:
            history.append(
                _hist(
                    "ai_conflict_suppressed",
                    typed,
                    "ai",
                    "Als nicht zutreffend markiert; nicht überschrieben.",
                )
            )
        elif current_known and row.value == typed:
            history.append(_hist("reconfirmed", typed, by))
        elif current_known and protected and not is_answer:
            history.append(
                _hist(
                    "ai_conflict_suppressed", typed, "ai", "Bestätigter Wert nicht überschrieben."
                )
            )
        elif current_known and not is_answer:
            conflicts = list(row.conflicting_values or [])
            conflicts.append(
                {"value": typed, "evidence_quote": quote, "source_message_id": message_id}
            )
            row.conflicting_values = conflicts
            row.status = FactStatus.CONTRADICTORY.value
            history.append(_hist("contradiction", typed, "ai", note))
        else:
            # missing / ambiguous / unknown / contradictory -> resolved; or a newer answer replaces the value
            history.append(_hist("answered" if is_answer else "extracted", typed, by, note))
            self._write_fact(row, FactStatus.KNOWN, typed, origin, quote, message_id)
            row.conflicting_values = []
            row.confirmed = False
            row.documented = False
            row.deferred_reason = None
        row.history = history

    @staticmethod
    def _write_fact(
        row: CaseFact,
        status: FactStatus,
        value: Any,
        origin: FactOrigin,
        quote: str,
        message_id: str,
    ) -> None:
        row.status = status.value
        row.value = value
        row.origin = origin.value
        row.evidence_quote = quote
        row.source_message_id = message_id
        row.deferred_reason = None if status == FactStatus.KNOWN else row.deferred_reason

    # ------------------------------------------------------------------ facts ------------
    def _fact_def(self, fact_id: str):
        for d in self.kb.issues.values():
            for f in d.facts:
                if f.id == fact_id:
                    return f
        return None

    def fact_views(self, case_id: str) -> list[FactView]:
        snap = self.snapshot(case_id)
        active = [
            i.issue_id
            for i in snap.issues
            if i.status == IssueStatus.DETECTED and i.issue_id in self.kb.issues
        ]
        active = list(dict.fromkeys(active))
        required = effective_required(self.kb, snap, active)  # type: ignore[arg-type]
        rows = {f.fact_id: f for f in self._fact_rows(case_id)}
        views: dict[str, FactView] = {}
        for issue_id in active:
            for fd in self.kb.issues[issue_id].facts:
                if fd.id in views:
                    views[fd.id].issue_ids.append(issue_id)
                    continue
                r = rows.get(fd.id)
                views[fd.id] = FactView(
                    fact_id=fd.id,
                    label_de=fd.label_de,
                    issue_ids=[issue_id],
                    data_type=fd.data_type,
                    enum_values=fd.enum_values,
                    enum_labels_de=fd.enum_labels_de,
                    group=fd.group,
                    documented=bool(r and r.documented),
                    required=required.get(fd.id, False),
                    priority=fd.priority,
                    question_de=fd.question_de,
                    why_needed_de=fd.why_needed_de,
                    status=FactStatus(r.status) if r else FactStatus.MISSING,
                    value=r.value if r else None,
                    origin=FactOrigin(r.origin) if r else None,
                    confirmed=bool(r and r.confirmed),
                    evidence_quote=r.evidence_quote if r else None,
                    source_message_id=r.source_message_id if r else None,
                    deferred_reason=r.deferred_reason if r else None,
                    conflicting_values=list(r.conflicting_values or []) if r else [],
                    history=[FactHistoryEntry(**h) for h in (r.history or [])] if r else [],
                    updated_at=_aware(r.updated_at) if r else None,
                )
        return list(views.values())

    def _row_for_edit(self, case: Case, fact_id: str) -> CaseFact:
        fd = self._fact_def(fact_id)
        if fd is None:
            raise NotFoundError(f"Unbekannter Fakt '{fact_id}'.")
        row = self.s.scalar(
            select(CaseFact).where(CaseFact.case_id == case.id, CaseFact.fact_id == fact_id)
        )
        if row is None:
            row = CaseFact(
                case_id=case.id,
                fact_id=fact_id,
                status=FactStatus.MISSING.value,
                history=[],
                conflicting_values=[],
            )
            self.s.add(row)
        return row

    def patch_fact(
        self,
        case_id: str,
        fact_id: str,
        *,
        has_value: bool,
        value: Any,
        status: str | None,
        confirmed: bool | None,
        note: str | None,
        documented: bool | None = None,
    ) -> None:
        case = self.get_case(case_id)
        row = self._row_for_edit(case, fact_id)
        fd = self._fact_def(fact_id)
        assert fd is not None
        history = list(row.history or [])

        if has_value and value is not None:
            raw = "ja" if value is True else "nein" if value is False else str(value)
            try:
                typed = coerce_value(fd, raw)
            except ValueError as exc:
                raise AppError(
                    f"Wert passt nicht zum Typ '{fd.data_type}': {exc}", code="invalid_value"
                ) from exc
            history.append(_hist("corrected", typed, "social_worker", note))
            row.value = typed
            row.status = FactStatus.KNOWN.value
            row.origin = FactOrigin.USER_CORRECTION.value
            row.confirmed = True
            row.conflicting_values = []
            row.deferred_reason = None
        elif status == "NOT_APPLICABLE":
            history.append(_hist("marked_not_applicable", None, "social_worker", note))
            row.status = FactStatus.NOT_APPLICABLE.value
            row.value = None
            row.origin = FactOrigin.USER_CORRECTION.value
            row.confirmed = True
            row.conflicting_values = []
        elif status == "UNKNOWN":
            history.append(_hist("unknown", None, "social_worker", note))
            row.status = FactStatus.UNKNOWN.value
            row.value = None
            row.origin = FactOrigin.USER_CORRECTION.value
            row.confirmed = True
            row.conflicting_values = []
            row.deferred_reason = None
        elif status == "MISSING":
            history.append(_hist("reset", None, "social_worker", note))
            row.status = FactStatus.MISSING.value
            row.value = None
            row.confirmed = False
            row.conflicting_values = []
        elif documented is not None:
            if row.status != FactStatus.KNOWN.value:
                raise AppError(
                    "Nur bekannte Fakten können als belegt markiert werden.", code="invalid_state"
                )
            row.documented = documented
            history.append(
                _hist(
                    "documented" if documented else "documented_removed",
                    row.value,
                    "social_worker",
                    note,
                )
            )
        elif confirmed is not None:
            if row.status != FactStatus.KNOWN.value:
                raise AppError("Nur bekannte Fakten können bestätigt werden.", code="invalid_state")
            row.confirmed = confirmed
            history.append(
                _hist(
                    "confirmed" if confirmed else "confirmation_removed",
                    row.value,
                    "social_worker",
                    note,
                )
            )
        else:
            raise AppError("Keine Änderung angegeben.", code="empty_patch")
        row.history = history
        self._touch(case)
        self.refresh_decision(case)
        self.s.commit()

    def defer_fact(self, case_id: str, fact_id: str, reason: str | None) -> None:
        case = self.get_case(case_id)
        row = self._row_for_edit(case, fact_id)
        history = list(row.history or [])
        if reason:
            if row.status == FactStatus.KNOWN.value:
                raise AppError(
                    "Ein bekannter Fakt muss nicht zurückgestellt werden.", code="invalid_state"
                )
            row.deferred_reason = reason.strip()
            history.append(_hist("deferred", None, "social_worker", reason.strip()))
        else:
            row.deferred_reason = None
            history.append(_hist("undeferred", None, "social_worker"))
        row.history = history
        self._touch(case)
        self.refresh_decision(case)
        self.s.commit()

    # ------------------------------------------------------------------ handover ---------
    def request_handover(self, case_id: str) -> Handover:
        case = self.get_case(case_id)
        h = self._handover(case_id)
        if h is None:
            raise ConflictError("Für diesen Fall liegt keine Übergabeempfehlung vor.")
        if h.status == HandoverStatus.HANDOFF_COMPLETED.value:
            raise ConflictError("Die Übergabe ist bereits bestätigt.")
        h.status = HandoverStatus.HANDOFF_REQUESTED.value
        h.requested_at = _now()
        self._touch(case)
        self.s.commit()
        return h

    def complete_handover(self, case_id: str, note: str) -> Handover:
        case = self.get_case(case_id)
        h = self._handover(case_id)
        if h is None or h.status != HandoverStatus.HANDOFF_REQUESTED.value:
            raise ConflictError("Eine Übergabe kann erst nach 'angefragt' bestätigt werden.")
        h.status = HandoverStatus.HANDOFF_COMPLETED.value
        h.completed_at = _now()
        h.completion_note = note.strip()
        self._touch(case)
        self.s.commit()
        return h

    # ------------------------------------------------------------------ detail view ------
    def detail(self, case_id: str, extra_warnings: list[str] | None = None) -> CaseDetail:
        case = self.get_case(case_id)
        pending = self._pending_ids(case_id)
        failed = [
            m for m in self._messages(case_id) if m.analysis_status == AnalysisStatus.FAILED.value
        ]
        if failed:
            analysis = AnalysisState(
                status="FAILED",
                pending_message_ids=pending,
                error_message=failed[-1].analysis_error,
                error_code="ai_error",
            )
        elif pending:
            analysis = AnalysisState(status="PENDING", pending_message_ids=pending)
        else:
            analysis = AnalysisState(status="OK", warnings=extra_warnings or [])
        issues = []
        for i in self._issues(case_id):
            d = self.kb.issues.get(i.issue_definition_id or "")
            issues.append(
                IssueView(
                    id=i.id,
                    issue_definition_id=i.issue_definition_id,
                    title_de=d.title_de if d else None,
                    legal_area=d.legal_area if d else None,
                    classification_status=IssueStatus(i.classification_status),
                    confidence=i.confidence,
                    evidence=i.evidence,
                    description=i.description,
                )
            )
        h = self._handover(case_id)
        latest = self._latest_briefing_row(case_id)
        return CaseDetail(
            id=case.id,
            display_id=case.display_id,
            title=case.title,
            summary=case.summary,
            status=CaseStatus(case.status),
            version=case.version,
            created_at=_aware(case.created_at),  # type: ignore[arg-type]
            updated_at=_aware(case.updated_at),  # type: ignore[arg-type]
            issues=issues,
            current_decision=self.current_decision(case_id),
            handover=HandoverView.model_validate(h) if h else None,
            analysis=analysis,
            briefing_stale=latest is None or latest.case_version < case.version,
            latest_briefing_id=latest.id if latest else None,
        )

    # ------------------------------------------------------------------ briefings --------
    def create_briefing(self, case_id: str, ai_external: bool) -> BriefingVersion:
        case = self.get_case(case_id)
        if self._pending_ids(case_id):
            raise ConflictError(
                "Die Analyse ist unvollständig. Bitte zuerst die Analyse erneut ausführen."
            )
        decision = self.refresh_decision(case)
        self.s.flush()
        issues = self._issues(case_id)
        rows = self._fact_rows(case_id)
        active = {i.issue_definition_id for i in issues}
        relevant = {f.id for i in self.kb.issues.values() if i.id in active for f in i.facts}
        facts = [r for r in rows if r.fact_id in relevant]
        briefing = build_briefing(
            kb=self.kb,
            case=case,
            issues=issues,
            facts=facts,
            message_count=len(self._messages(case_id)),
            decision=decision,
            handover=self._handover(case_id),
            ai_external=ai_external,
            registry=self._source_registry(decision, rows),
            bridge_message_ids=frozenset(
                m.id for m in self._messages(case_id) if m.origin == "VOICE_BRIDGE"
            ),
        )
        briefing.extras = build_extras(
            kb=self.kb,
            decision=decision,
            rows=rows,
            messages=self._messages(case_id),
            active_issue_ids=[i for i in active if i],
            facts_state=self.snapshot(case_id).facts,
            ai_name=self.ai.name,
            today=self.today or date.today(),
        )
        last = self._latest_briefing_row(case_id)
        row = BriefingVersion(
            case_id=case_id,
            version=(last.version + 1) if last else 1,
            case_version=case.version,
            payload=briefing.model_dump(mode="json"),
        )
        self.s.add(row)
        self.s.commit()
        return row

    def _source_registry(self, decision: DecisionResult, rows: list[CaseFact]):
        """Registry backed by the local Fedlex cache. The statute version is chosen for the date the facts
        point to (earliest known receipt hint), else for today; it never changes a decision."""
        from app.services.rules.derived import _parse
        from app.services.sources.registry import SourceRegistry

        provider = self.source_provider
        if provider is None:
            return SourceRegistry(self.kb)
        known = {r.fact_id: r.value for r in rows if r.status == FactStatus.KNOWN.value}
        dates = []
        for iid in decision.active_issue_ids:
            for d in self.kb.issues[iid].derived:
                if d.kind == "days_since_earliest":
                    dates += [x for f in d.facts if (x := _parse(known.get(f))) is not None]
        provider.reference_date = min(dates) if dates else (self.today or date.today())
        return SourceRegistry(self.kb, provider)

    def list_briefings(self, case_id: str) -> list[BriefingVersion]:
        self.get_case(case_id)
        return list(
            self.s.scalars(
                select(BriefingVersion)
                .where(BriefingVersion.case_id == case_id)
                .order_by(BriefingVersion.version.desc())
            )
        )

    def get_briefing(self, case_id: str, briefing_id: str) -> BriefingVersion:
        row = self.s.get(BriefingVersion, briefing_id)
        if row is None or row.case_id != case_id:
            raise NotFoundError("Briefing nicht gefunden.")
        return row

    def report_view(self, case_id: str, briefing_id: str) -> dict:
        """View model of one stored briefing version for the HTML preview / PDF. Reads only that case."""
        case = self.get_case(case_id)
        row = self.get_briefing(case_id, briefing_id)
        return build_view(
            briefing=CaseBriefing.model_validate(row.payload),
            case_display_id=case.display_id,
            version=row.version,
            created_at=_aware(row.created_at),  # type: ignore[arg-type]
            kb=self.kb,
        )

    @staticmethod
    def briefing_view(row: BriefingVersion) -> BriefingView:
        return BriefingView(
            id=row.id,
            version=row.version,
            case_version=row.case_version,
            created_at=_aware(row.created_at),  # type: ignore[arg-type]
            briefing=CaseBriefing.model_validate(row.payload),
        )
