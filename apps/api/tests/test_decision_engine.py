from __future__ import annotations

import shutil

import pytest

from app.core.config import REPO_ROOT
from app.domain.enums import Action, FactStatus, IssueStatus
from app.domain.state import CaseSnapshot, FactState, IssueState
from app.services.decisions.engine import decide
from app.services.decisions.evaluation import run_scenarios
from app.services.knowledge.loader import load_knowledge_base

KB_DIR = REPO_ROOT / "knowledge_base"


@pytest.fixture(scope="module")
def kb():
    k = load_knowledge_base(KB_DIR)
    assert k.valid, k.errors
    return k


def snap(issues=(), facts=None, unsupported=(), has_input=True) -> CaseSnapshot:
    return CaseSnapshot(
        has_user_input=has_input,
        issues=[IssueState(IssueStatus.DETECTED, i, c) for i, c in issues]
        + [IssueState(IssueStatus.UNSUPPORTED, description=d) for d in unsupported],
        facts={k: FactState(FactStatus.KNOWN, v) for k, v in (facts or {}).items()},
    )


EMP_COMPLETE = {
    "employer_termination_received": True,
    "employer_termination_received_date": "2026-01-15",
    "employer_termination_in_writing": True,
    "employment_start_date": "2020-03-01",
    "incapacity_for_work": False,
    "deadline_pending": False,
}


def test_all_shipped_scenarios_pass(kb):
    summary = run_scenarios(kb)
    failed = [r for r in summary.results if not r.passed]
    assert not failed, [(r.scenario_id, r.mismatches) for r in failed]
    assert summary.total >= 10
    assert summary.legally_validated_total == 0  # nothing is legally validated yet


def test_empty_case_asks_for_description(kb):
    d = decide(kb, snap(has_input=False))
    assert d.action == Action.ASK and d.main_reason_code == "NO_INPUT"
    assert d.next_question and d.next_question.fact_id is None


def test_ask_picks_highest_priority_question_first(kb):
    d = decide(kb, snap([("employment_termination", 0.9)]))
    assert d.action == Action.ASK
    assert d.next_question.fact_id == "employer_termination_received"  # high, first in file
    assert [m.priority for m in d.missing_facts] == sorted(
        [m.priority for m in d.missing_facts], key=["high", "medium", "low"].index
    )


def test_proceed_only_when_everything_present(kb):
    d = decide(kb, snap([("employment_termination", 0.9)], EMP_COMPLETE))
    assert d.action == Action.PROCEED
    assert d.reason_codes == ["ALL_REQUIRED_FACTS_PRESENT"]
    assert d.missing_facts == []


def test_escalate_beats_ask_and_keeps_missing_facts(kb):
    d = decide(kb, snap([("employment_termination", 0.9)], {"deadline_pending": True}))
    assert d.action == Action.ESCALATE
    assert "EMP_DEMO_DEADLINE_PENDING" in d.triggered_rule_ids
    assert "MISSING_REQUIRED_FACTS" in d.reason_codes
    assert d.missing_facts, "missing facts must not be discarded on escalation"
    assert "employment_law_counsel" in d.recommended_professionals


def test_unsupported_or_unrecognised_never_proceeds(kb):
    assert decide(kb, snap(unsupported=["Erbrecht"])).action == Action.ESCALATE
    d = decide(kb, snap())  # input exists but nothing recognised
    assert d.action == Action.ESCALATE and "GLOBAL_NO_SUPPORTED_ISSUE" in d.triggered_rule_ids
    # a DETECTED issue id the KB does not know is treated as unsupported
    d2 = decide(kb, snap([("made_up_issue", 0.99)]))
    assert d2.action == Action.ESCALATE and "GLOBAL_UNSUPPORTED_ISSUE" in d2.triggered_rule_ids


def test_low_confidence_escalates(kb):
    d = decide(kb, snap([("tenancy_defects", 0.2)], {}))
    assert d.action == Action.ESCALATE and "LOW_CLASSIFICATION_CONFIDENCE" in d.reason_codes


def test_conditional_facts_appear_only_when_condition_true(kb):
    base = {
        "landlord_informed": False,
        "defect_description": "Schimmel",
        "defect_since": "2025-11-01",
        "deadline_pending": False,
    }
    d = decide(kb, snap([("tenancy_defects", 0.9)], base))
    assert d.action == Action.PROCEED
    d = decide(kb, snap([("tenancy_defects", 0.9)], {**base, "landlord_informed": True}))
    assert d.action == Action.ASK
    assert {m.fact_id for m in d.missing_facts} == {"landlord_informed_date"}


def test_ambiguous_and_contradictory_required_facts_block_proceed(kb):
    s = snap([("employment_termination", 0.9)], EMP_COMPLETE)
    s.facts["incapacity_for_work"] = FactState(FactStatus.AMBIGUOUS, None)
    d = decide(kb, s)
    assert d.action == Action.ASK and "AMBIGUOUS_FACTS" in d.reason_codes
    s.facts["incapacity_for_work"] = FactState(FactStatus.CONTRADICTORY, False)
    d = decide(kb, s)
    assert d.action == Action.ASK and "CONTRADICTORY_FACTS" in d.reason_codes


def test_unknown_value_does_not_trigger_escalation_rule(kb):
    s = snap([("employment_termination", 0.9)], EMP_COMPLETE)
    s.facts["deadline_pending"] = FactState(FactStatus.AMBIGUOUS, True)  # not KNOWN
    d = decide(kb, s)
    assert "EMP_DEMO_DEADLINE_PENDING" not in d.triggered_rule_ids
    assert d.action == Action.ASK  # asked again, never silently PROCEED


def test_deferred_question_is_not_asked_first_but_still_blocks_proceed(kb):
    s = snap([("employment_termination", 0.9)], {"employer_termination_received": True})
    s.facts["employer_termination_received_date"] = FactState(
        FactStatus.MISSING, None, deferred=True
    )
    d = decide(kb, s)
    assert d.action == Action.ASK
    assert d.next_question.fact_id != "employer_termination_received_date"
    only_deferred = snap(
        [("employment_termination", 0.9)],
        {k: v for k, v in EMP_COMPLETE.items() if k != "employer_termination_received_date"},
    )
    only_deferred.facts["employer_termination_received_date"] = FactState(
        FactStatus.MISSING, None, True
    )
    d2 = decide(kb, only_deferred)
    assert d2.action == Action.ASK and d2.next_question.deferred


def test_multiple_issues_merge_shared_facts(kb):
    d = decide(kb, snap([("employment_termination", 0.9), ("unpaid_salary", 0.9)]))
    ids = [m.fact_id for m in d.missing_facts]
    assert ids.count("deadline_pending") == 1 and ids.count("employment_start_date") == 1
    shared = next(m for m in d.missing_facts if m.fact_id == "deadline_pending")
    assert set(shared.issue_ids) == {"employment_termination", "unpaid_salary"}


def test_decision_is_deterministic(kb):
    s = snap(
        [("employment_termination", 0.9), ("tenancy_termination", 0.6)], {"deadline_pending": True}
    )
    a, b = decide(kb, s), decide(kb, s)
    assert a.signature() == b.signature()
    assert a.model_dump(exclude={"evaluated_at"}) == b.model_dump(exclude={"evaluated_at"})


def test_legal_findings_and_evaluated_rules_listed(kb):
    s = snap(
        [("employment_termination", 0.9)],
        {**EMP_COMPLETE, "employer_termination_in_writing": False},
    )
    d = decide(kb, s)
    assert [f.rule_id for f in d.legal_findings] == ["EMP_DEMO_TERMINATION_FORM_CHECK"]
    assert any(
        r.rule_id == "GLOBAL_UNSUPPORTED_ISSUE" and r.outcome == "NOT_FIRED"
        for r in d.evaluated_rules
    )


def test_missing_global_rules_never_allow_proceed(kb, tmp_path):
    dest = tmp_path / "kb"
    shutil.copytree(KB_DIR, dest)
    (dest / "routing" / "global_escalation.yaml").write_text(
        "rules: [{id: broken}]", encoding="utf-8"
    )
    broken = load_knowledge_base(dest)
    assert not broken.global_rules_loaded
    d = decide(broken, snap([("employment_termination", 0.9)], EMP_COMPLETE))
    assert d.action == Action.ESCALATE and "KB_GLOBAL_RULES_UNAVAILABLE" in d.reason_codes


def test_broken_issue_file_means_issue_unsupported_not_proceed(kb, tmp_path):
    dest = tmp_path / "kb"
    shutil.copytree(KB_DIR, dest)
    (dest / "legal_issues" / "employment_termination.yaml").write_text("id: [", encoding="utf-8")
    broken = load_knowledge_base(dest)
    d = decide(broken, snap([("employment_termination", 0.9)], EMP_COMPLETE))
    assert d.action == Action.ESCALATE
