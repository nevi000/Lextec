"""Deterministic decision engine: ESCALATE > ASK > PROCEED.

Pure function of (knowledge base, case snapshot). No AI, no database, no clock in the logic
(``snapshot.today`` is the reference date for derived values; ``now`` is only stamped on the result).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.enums import Action, FactStatus, IssueStatus
from app.domain.state import CaseSnapshot
from app.schemas.decision import (
    URGENCY_LABEL_DE,
    ApprovedStatement,
    DecisionResult,
    EvaluatedRule,
    LegalFinding,
    NextQuestion,
    RelatedRoute,
    TriggeredRule,
)
from app.services.decisions.missing import (
    analyze_facts,
    known_values,
    pick_next_question,
    unknown_ids,
)
from app.services.knowledge.loader import KnowledgeBase
from app.services.knowledge.schema import EscalationRule
from app.services.rules.conditions import EvalContext, evaluate
from app.services.rules.derived import compute_derived
from app.services.safety.assess import assess_safety, location_from_facts, plan_referrals

URGENCY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

NO_INPUT_QUESTION = NextQuestion(
    fact_id=None,
    question_de="Bitte schildern Sie die Situation der ratsuchenden Person in eigenen Worten.",
    why_needed_de="Ohne Schilderung kann der Fall nicht eingeordnet werden.",
)


def _outcome(value: bool | None) -> str:
    return {True: "FIRED", False: "NOT_FIRED", None: "UNKNOWN"}[value]


def _route(kb: KnowledgeBase, rule_id: str, issue_id: str) -> RelatedRoute:
    issue = kb.issues.get(issue_id)
    related = kb.related_issues.get(issue_id)
    title = issue.title_de if issue else (related.title_de if related else issue_id)
    available = bool(issue and issue.content_status == "LEGALLY_REVIEWED")
    note = (
        f"«{title}» ist umgesetzt und juristisch freigegeben; seine Regeln werden zusätzlich angewendet."
        if available
        else f"«{title}» ist noch nicht juristisch freigegeben umgesetzt. Es werden keine Spezialregeln "
        "angewendet; menschliche Prüfung empfohlen."
    )
    return RelatedRoute(
        issue_id=issue_id, title_de=title, available=available, note_de=note, from_rule_id=rule_id
    )


def decide(
    kb: KnowledgeBase,
    snapshot: CaseSnapshot,
    now: datetime | None = None,
    _extra_active: tuple[str, ...] = (),
) -> DecisionResult:
    now = now or datetime.now(UTC)

    active_ids: list[str] = []
    unsupported = 0
    confidences: list[float] = []
    for iss in snapshot.issues:
        if iss.status == IssueStatus.DETECTED and iss.issue_id in kb.issues:
            if iss.issue_id not in active_ids:
                active_ids.append(iss.issue_id)
                if iss.confidence is not None:
                    confidences.append(iss.confidence)
        else:
            unsupported += 1  # explicit UNSUPPORTED, or a DETECTED id the KB does not know
    for extra in _extra_active:  # reviewed related issues reached via a route
        if extra in kb.issues and extra not in active_ids:
            active_ids.append(extra)

    relevant_fact_ids = {f.id for i in active_ids for f in kb.issues[i].facts}
    contradictory = sum(
        1
        for fid, fs in snapshot.facts.items()
        if fid in relevant_fact_ids and fs.status == FactStatus.CONTRADICTORY
    )

    analysis = analyze_facts(kb, snapshot, active_ids)
    missing = analysis.missing
    known = known_values(snapshot)
    derived = compute_derived(
        [d for i in active_ids for d in kb.issues[i].derived], known, snapshot.today
    )
    ctx = {
        "has_user_input": snapshot.has_user_input,
        "active_issue_count": len(active_ids),
        "unsupported_issue_count": unsupported,
        "min_classification_confidence": min(confidences) if confidences else None,
        "contradictory_fact_count": contradictory,
        "missing_required_count": len(missing),
    }
    env = EvalContext(
        facts=known,
        ctx=ctx,
        active_issues=frozenset(active_ids),
        unknown=unknown_ids(snapshot),
        derived=derived,
    )

    evaluated: list[EvaluatedRule] = []
    triggered: list[TriggeredRule] = []
    suppress_ids: set[str] = set()
    route_of: dict[str, str] = {}  # rule id -> routed issue id

    def run_rule(rule: EscalationRule, scope: str, issue_id: str | None) -> None:
        result = evaluate(rule.when, env)
        kind = "GLOBAL_ESCALATION" if scope == "GLOBAL" else "ISSUE_ESCALATION"
        evaluated.append(
            EvaluatedRule(
                rule_id=rule.id,
                kind=kind,
                issue_id=issue_id,
                description=rule.description,
                outcome=_outcome(result),  # type: ignore[arg-type]
            )
        )
        if result is True:
            triggered.append(
                TriggeredRule(
                    rule_id=rule.id,
                    scope=scope,  # type: ignore[arg-type]
                    issue_id=issue_id,
                    description=rule.description,
                    reason_code=rule.reason_code,
                    reason_de=rule.reason_de,
                    urgency=rule.urgency,
                    urgency_label_de=URGENCY_LABEL_DE[rule.urgency],
                    routes_to_issue=rule.routes_to_issue,
                )
            )
            if rule.suppress_standard_statements:
                suppress_ids.add(rule.id)
            if rule.routes_to_issue:
                route_of[rule.id] = rule.routes_to_issue

    for rule in kb.global_rules:
        run_rule(rule, "GLOBAL", None)

    legal_rules_fired: list[tuple[str, object]] = []
    for issue_id in active_ids:
        issue = kb.issues[issue_id]
        for rule in issue.escalation_rules:
            run_rule(rule, "ISSUE", issue_id)
        for lr in issue.legal_rules:
            result = evaluate(lr.when, env)
            evaluated.append(
                EvaluatedRule(
                    rule_id=lr.id,
                    kind="LEGAL_RULE",
                    issue_id=issue_id,
                    description=lr.description,
                    outcome=_outcome(result),  # type: ignore[arg-type]
                )
            )
            if result is True:
                legal_rules_fired.append((issue_id, lr))

    # Built-in: a REQUIRED fact that was asked but is unknown never allows PROCEED.
    if analysis.unknown_required:
        labels = ", ".join(m.label_de for m in analysis.unknown_required[:4])
        evaluated.append(
            EvaluatedRule(
                rule_id="SYSTEM_REQUIRED_FACT_UNKNOWN",
                kind="SYSTEM",
                description="Eine erforderliche Angabe wurde erfragt, ist der Person aber unbekannt.",
                outcome="FIRED",
            )
        )
        triggered.append(
            TriggeredRule(
                rule_id="SYSTEM_REQUIRED_FACT_UNKNOWN",
                scope="SYSTEM",
                description="Erforderliche Angabe erfragt, aber unbekannt.",
                reason_code="REQUIRED_FACT_UNKNOWN",
                reason_de=f"Erforderliche Angabe(n) sind der Person unbekannt ({labels}). "
                "Das System nimmt nichts an; eine Fachperson muss das klären.",
                urgency="MEDIUM",
                urgency_label_de=URGENCY_LABEL_DE["MEDIUM"],
            )
        )

    # Fail-safe: a knowledge base without usable global rules must never allow PROCEED.
    if not kb.global_rules_loaded:
        triggered.append(
            TriggeredRule(
                rule_id="SYSTEM_GLOBAL_RULES_UNAVAILABLE",
                scope="SYSTEM",
                description="Die globalen Eskalationsregeln konnten nicht geladen werden.",
                reason_code="KB_GLOBAL_RULES_UNAVAILABLE",
                reason_de="Die globalen Eskalationsregeln sind nicht verfügbar. "
                "Eine automatische Weiterbearbeitung ist deshalb nicht zulässig.",
                urgency="HIGH",
                urgency_label_de=URGENCY_LABEL_DE["HIGH"],
            )
        )

    triggered.sort(key=lambda t: URGENCY_RANK[t.urgency])  # stable: file order within a level

    # --- related-issue routing --------------------------------------------------------------
    routes: list[RelatedRoute] = []
    seen_routes: set[str] = set()
    for t in triggered:
        target = route_of.get(t.rule_id)
        if target and target not in seen_routes:
            seen_routes.add(target)
            routes.append(_route(kb, t.rule_id, target))
    newly = tuple(r.issue_id for r in routes if r.available and r.issue_id not in active_ids)
    if newly and not _extra_active:
        return decide(kb, snapshot, now, newly)

    # --- statements (suppressed for cases outside the module) -------------------------------
    suppressed = bool(suppress_ids)
    findings: list[LegalFinding] = []
    statements: list[ApprovedStatement] = []
    if not suppressed:
        for issue_id, lr in legal_rules_fired:
            if lr.kind == "HINT":  # type: ignore[attr-defined]
                statements.append(
                    ApprovedStatement(
                        rule_id=lr.id,  # type: ignore[attr-defined]
                        issue_id=issue_id,
                        text_de=lr.result_de,  # type: ignore[attr-defined]
                        source_ids=list(lr.legal_source_ids),  # type: ignore[attr-defined]
                    )
                )
            else:
                findings.append(
                    LegalFinding(
                        rule_id=lr.id,  # type: ignore[attr-defined]
                        issue_id=issue_id,
                        result_code=lr.result_code,  # type: ignore[attr-defined]
                        result_de=lr.result_de,  # type: ignore[attr-defined]
                        legal_source_ids=list(lr.legal_source_ids),  # type: ignore[attr-defined]
                    )
                )

    # --- professionals ----------------------------------------------------------------------
    rule_pros: dict[str, list[str]] = {r.id: r.professionals for r in kb.global_rules}
    for issue_id in active_ids:
        for rule in kb.issues[issue_id].escalation_rules:
            rule_pros[rule.id] = rule.professionals
    professionals: list[str] = []
    for t in triggered:
        for p in rule_pros.get(t.rule_id, []):
            if p not in professionals:
                professionals.append(p)
    if not professionals:
        for issue_id in active_ids:
            for p in kb.issues[issue_id].default_professionals:
                if p not in professionals:
                    professionals.append(p)

    # --- decision ---------------------------------------------------------------------------
    reason_codes: list[str] = []
    for t in triggered:
        if t.reason_code not in reason_codes:
            reason_codes.append(t.reason_code)

    next_question: NextQuestion | None = None
    max_urgency = triggered[0].urgency if triggered else None
    if triggered:
        action = Action.ESCALATE
        if missing:
            reason_codes.append("MISSING_REQUIRED_FACTS")
        next_question = pick_next_question(missing, analysis.optional_open)
        main = reason_codes[0]
        explanation = (
            f"Eskalation empfohlen (Dringlichkeit: {URGENCY_LABEL_DE[triggered[0].urgency]}). "
            + " ".join(t.reason_de for t in triggered[:3])
        )
        if len(triggered) > 3:
            explanation += f" (+{len(triggered) - 3} weitere Gründe)"
        if missing:
            explanation += (
                f" Zusätzlich fehlen noch {len(missing)} Pflichtangaben, die für die Fachperson "
                "hilfreich wären."
            )
    elif not snapshot.has_user_input:
        action = Action.ASK
        main = "NO_INPUT"
        reason_codes = ["NO_INPUT"]
        next_question = NO_INPUT_QUESTION
        explanation = "Es liegt noch keine Schilderung vor."
    elif missing:
        action = Action.ASK
        main = "MISSING_REQUIRED_FACTS"
        reason_codes = ["MISSING_REQUIRED_FACTS"]
        if any(m.status == FactStatus.CONTRADICTORY for m in missing):
            reason_codes.append("CONTRADICTORY_FACTS")
        if any(m.status == FactStatus.AMBIGUOUS for m in missing):
            reason_codes.append("AMBIGUOUS_FACTS")
        next_question = pick_next_question(missing, None)
        explanation = (
            f"{len(missing)} Pflichtangabe(n) fehlen oder sind unklar. "
            "Die nächste Rückfrage klärt die wichtigste offene Angabe."
        )
    else:
        action = Action.PROCEED
        main = "ALL_REQUIRED_FACTS_PRESENT"
        reason_codes = ["ALL_REQUIRED_FACTS_PRESENT"]
        next_question = pick_next_question([], analysis.optional_open)
        explanation = (
            "Alle erforderlichen Angaben liegen vor und keine Eskalationsregel greift. "
            "Der Fall kann strukturiert weiterbearbeitet und als Briefing übergeben werden. "
            "Dies ist keine verbindliche Rechtsauskunft."
        )

    result = DecisionResult(
        action=action,
        main_reason_code=main,
        reason_codes=reason_codes,
        triggered_rule_ids=[t.rule_id for t in triggered],
        triggered_rules=triggered,
        evaluated_rules=evaluated,
        legal_findings=findings,
        approved_statements=statements,
        statements_suppressed=suppressed,
        related_routes=routes,
        explanation_de=explanation,
        missing_facts=missing,
        unknown_required_facts=analysis.unknown_required,
        optional_open_facts=analysis.optional_open,
        next_question=next_question,
        recommended_professionals=professionals,
        active_issue_ids=active_ids,
        max_urgency=max_urgency,
        derived_values=derived,
        knowledge_base_version=kb.version,
        evaluated_at=now,
    )

    # --- safety layer: independent of the legal issue and of its classification --------------------
    loc = location_from_facts(kb, active_ids, snapshot.facts)
    rule_ids = [t.rule_id for t in triggered]
    safety = assess_safety(kb, list(snapshot.safety_events), loc, rule_ids)
    result.safety = safety
    result.referrals = plan_referrals(kb, active_ids, loc, rule_ids, safety)
    result.effective_action = action.value  # type: ignore[assignment]
    if safety.state == "IMMEDIATE":
        result.effective_action = "IMMEDIATE_SAFETY_RESPONSE"
        result.reason_codes = [
            "SAFETY_IMMEDIATE_RESPONSE",
            *[c for c in result.reason_codes if c != "SAFETY_IMMEDIATE_RESPONSE"],
        ]
        result.main_reason_code = "SAFETY_IMMEDIATE_RESPONSE"
        result.max_urgency = "HIGH"
        result.explanation_de = (
            "Sicherheitsreaktion hat Vorrang: "
            + (safety.explanation_de or "")
            + " Juristische Einschätzung (nachrangig): "
            + result.explanation_de
        )
    return result
