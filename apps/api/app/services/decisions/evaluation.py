"""Runs knowledge-base scenarios against the deterministic engine (no AI involved)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.domain.enums import FactStatus, IssueStatus
from app.domain.state import CaseSnapshot, FactState, IssueState
from app.services.decisions.engine import decide
from app.services.knowledge.loader import KnowledgeBase
from app.services.knowledge.schema import ScenarioDef


class ScenarioResult(BaseModel):
    scenario_id: str
    title_de: str
    validation: str
    passed: bool
    expected_action: str
    actual_action: str
    expected_rule_ids: list[str]
    actual_rule_ids: list[str]
    expected_reason_codes: list[str]
    actual_reason_codes: list[str]
    expected_missing_facts: list[str]
    actual_missing_facts: list[str]
    max_urgency: str | None = None
    route_issue_ids: list[str] = []
    mismatches: list[str]


class EvaluationSummary(BaseModel):
    knowledge_base_version: str
    total: int
    passed: int
    failed: int
    synthetic_total: int
    legally_validated_total: int
    unnecessary_escalations: int  # expected not-ESCALATE, got ESCALATE
    missed_escalations: int  # expected ESCALATE, got something else
    results: list[ScenarioResult]


DEFAULT_SCENARIO_TODAY = date(2026, 11, 7)


def snapshot_from_scenario(sc: ScenarioDef) -> CaseSnapshot:
    issues = [
        IssueState(
            status=IssueStatus.DETECTED,
            issue_id=i["id"],
            confidence=i.get("confidence", 1.0),
        )
        for i in sc.issues
    ]
    issues += [
        IssueState(status=IssueStatus.UNSUPPORTED, description=d) for d in sc.unsupported_issues
    ]
    facts = {
        fid: FactState(status=FactStatus.KNOWN, value=val)
        for fid, val in sc.facts.items()
        if val is not None
    }
    for fid in sc.unknown_facts:
        facts[fid] = FactState(status=FactStatus.UNKNOWN)
    today = date.fromisoformat(sc.today) if sc.today else DEFAULT_SCENARIO_TODAY
    return CaseSnapshot(has_user_input=sc.has_user_input, issues=issues, facts=facts, today=today)


def run_scenarios(kb: KnowledgeBase) -> EvaluationSummary:
    results: list[ScenarioResult] = []
    for sc in kb.scenarios:
        d = decide(kb, snapshot_from_scenario(sc))
        actual_missing = [m.fact_id for m in d.missing_facts]
        mismatches: list[str] = []
        if d.action.value != sc.expected_action:
            mismatches.append(f"Aktion: erwartet {sc.expected_action}, erhalten {d.action.value}.")
        for rid in sc.expected_rule_ids:
            if rid not in d.triggered_rule_ids:
                mismatches.append(f"Regel {rid} wurde nicht ausgelöst.")
        for code in sc.expected_reason_codes:
            if code not in d.reason_codes:
                mismatches.append(f"Reason Code {code} fehlt.")
        for rid in sc.expected_not_rule_ids:
            if rid in d.triggered_rule_ids:
                mismatches.append(f"Regel {rid} wurde ausgelöst, sollte aber nicht.")
        if sc.expected_urgency and d.max_urgency != sc.expected_urgency:
            mismatches.append(
                f"Dringlichkeit: erwartet {sc.expected_urgency}, erhalten {d.max_urgency}."
            )
        routes = [r.issue_id for r in d.related_routes]
        for iid in sc.expected_route_issue_ids:
            if iid not in routes:
                mismatches.append(f"Weiterleitung auf {iid} fehlt.")
        if sc.expected_missing_facts and set(sc.expected_missing_facts) != set(actual_missing):
            mismatches.append(
                f"Fehlende Fakten: erwartet {sorted(sc.expected_missing_facts)}, "
                f"erhalten {sorted(actual_missing)}."
            )
        results.append(
            ScenarioResult(
                scenario_id=sc.id,
                title_de=sc.title_de,
                validation=sc.validation,
                passed=not mismatches,
                expected_action=sc.expected_action,
                actual_action=d.action.value,
                expected_rule_ids=sc.expected_rule_ids,
                actual_rule_ids=d.triggered_rule_ids,
                expected_reason_codes=sc.expected_reason_codes,
                actual_reason_codes=d.reason_codes,
                expected_missing_facts=sc.expected_missing_facts,
                actual_missing_facts=actual_missing,
                max_urgency=d.max_urgency,
                route_issue_ids=routes,
                mismatches=mismatches,
            )
        )
    return EvaluationSummary(
        knowledge_base_version=kb.version,
        total=len(results),
        passed=sum(r.passed for r in results),
        failed=sum(not r.passed for r in results),
        synthetic_total=sum(r.validation == "SYNTHETIC_TECHNICAL" for r in results),
        legally_validated_total=sum(r.validation == "LEGALLY_VALIDATED" for r in results),
        unnecessary_escalations=sum(
            r.expected_action != "ESCALATE" and r.actual_action == "ESCALATE" for r in results
        ),
        missed_escalations=sum(
            r.expected_action == "ESCALATE" and r.actual_action != "ESCALATE" for r in results
        ),
        results=results,
    )
