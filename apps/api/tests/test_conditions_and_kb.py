from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.core.config import REPO_ROOT
from app.services.knowledge.loader import load_knowledge_base
from app.services.rules.conditions import Condition, EvalContext, evaluate, fires

KB = REPO_ROOT / "knowledge_base"


def cond(d: dict) -> Condition:
    return Condition.model_validate(d)


def env(facts=None, ctx=None, issues=()):
    return EvalContext(facts=facts or {}, ctx=ctx or {}, active_issues=frozenset(issues))


# ---- condition language -----------------------------------------------------------------
def test_equals_and_missing_is_unknown():
    c = cond({"ref": "fact.a", "op": "equals", "value": True})
    assert evaluate(c, env({"a": True})) is True
    assert evaluate(c, env({"a": False})) is False
    assert evaluate(c, env({})) is None
    assert fires(c, env({})) is False


def test_not_of_unknown_stays_unknown_and_never_fires():
    c = cond({"not": {"ref": "fact.a", "op": "equals", "value": True}})
    assert evaluate(c, env({})) is None
    assert fires(c, env({})) is False
    assert fires(c, env({"a": False})) is True


def test_all_any_three_valued():
    t = {"ref": "fact.t", "op": "equals", "value": 1}
    u = {"ref": "fact.u", "op": "equals", "value": 1}
    e = env({"t": 1})
    assert evaluate(cond({"all": [t, u]}), e) is None
    assert evaluate(cond({"any": [t, u]}), e) is True
    assert evaluate(cond({"all": [t, {"ref": "fact.t", "op": "equals", "value": 2}]}), e) is False


def test_exists_is_missing_are_definite():
    assert evaluate(cond({"ref": "fact.a", "op": "exists"}), env({})) is False
    assert evaluate(cond({"ref": "fact.a", "op": "is_missing"}), env({})) is True
    assert evaluate(cond({"ref": "fact.a", "op": "is_known"}), env({"a": 0})) is True


def test_in_and_ordering_and_case_insensitive_strings():
    assert (
        evaluate(cond({"ref": "fact.a", "op": "in", "value": ["x", "Y"]}), env({"a": "y"})) is True
    )
    assert (
        evaluate(
            cond({"ref": "fact.d", "op": "greater_than", "value": "2025-01-01"}),
            env({"d": "2026-02-01"}),
        )
        is True
    )
    assert evaluate(cond({"ref": "fact.n", "op": "less_than", "value": 10}), env({"n": 3})) is True
    # ordering a boolean is not meaningful -> unknown
    assert (
        evaluate(cond({"ref": "fact.b", "op": "greater_than", "value": 1}), env({"b": True}))
        is None
    )


def test_ctx_and_issue_refs():
    c = cond({"ref": "ctx.active_issue_count", "op": "greater_than", "value": 1})
    assert fires(c, env(ctx={"active_issue_count": 2}))
    assert (
        evaluate(c, env(ctx={"min_classification_confidence": None, "active_issue_count": None}))
        is None
    )
    assert fires(
        cond({"ref": "issue.tenancy_defects", "op": "exists"}), env(issues=["tenancy_defects"])
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"ref": "fact.a", "op": "regex_match", "value": "x"},  # unknown operator
        {"ref": "fact.a", "op": "equals"},  # missing value
        {"ref": "fact.a", "op": "exists", "value": 1},  # value not allowed
        {"ref": "fact.a", "op": "in", "value": "notalist"},
        {"ref": "bogus.a", "op": "exists"},
        {"ref": "ctx.unknown_key", "op": "exists"},
        {"all": []},
        {"all": [{"ref": "fact.a", "op": "exists"}], "any": [{"ref": "fact.a", "op": "exists"}]},
        {"ref": "fact.a"},
        {"eval": "__import__('os')"},
    ],
)
def test_invalid_conditions_fail_validation(bad):
    with pytest.raises(ValidationError):
        cond(bad)


# ---- knowledge base loading ----------------------------------------------------------------
def test_shipped_kb_is_valid_and_has_four_issues():
    kb = load_knowledge_base(KB)
    assert kb.valid, kb.errors
    assert set(kb.issues) == {
        "CH_TENANCY_TERMINATION",
        "tenancy_defects",
        "employment_termination",
        "unpaid_salary",
    }
    assert kb.global_rules_loaded
    assert kb.version.startswith("kb-")


def test_kb_version_is_deterministic_and_content_sensitive(tmp_path):
    a = tmp_path / "a"
    shutil.copytree(KB, a)
    assert load_knowledge_base(a).version == load_knowledge_base(KB).version
    p = a / "referrals" / "professionals.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "\n# edit\n", encoding="utf-8")
    assert load_knowledge_base(a).version != load_knowledge_base(KB).version


def _mutated(tmp_path, rel: str, fn):
    dest = tempfile.mkdtemp(dir=tmp_path)
    shutil.rmtree(dest)
    shutil.copytree(KB, dest)
    dest = Path(dest)
    p = dest / rel
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    fn(data)
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return load_knowledge_base(dest)


def test_invalid_operator_in_yaml_reported_with_path(tmp_path):
    def mutate(d):
        d["escalation_rules"][0]["when"] = {
            "ref": "fact.deadline_pending",
            "op": "matches",
            "value": 1,
        }

    kb = _mutated(tmp_path, "legal_issues/CH_TENANCY_TERMINATION.yaml", mutate)
    assert not kb.valid
    assert any("CH_TENANCY_TERMINATION.yaml" in e and "escalation_rules" in e for e in kb.errors)
    assert (
        "CH_TENANCY_TERMINATION" not in kb.issues
    )  # broken file is not loaded, never half-trusted


def test_duplicate_rule_ids_detected(tmp_path):
    def mutate(d):
        d["escalation_rules"][0]["id"] = "EMP_DEMO_DEADLINE_PENDING"

    kb = _mutated(tmp_path, "legal_issues/unpaid_salary.yaml", mutate)
    assert any("Doppelte Regel-ID" in e for e in kb.errors)


def test_invalid_fact_reference_and_source_and_professional(tmp_path):
    def mutate(d):
        d["escalation_rules"][0]["when"] = {"ref": "fact.does_not_exist", "op": "exists"}
        d["escalation_rules"][0]["professionals"] = ["nobody"]
        d["legal_source_ids"] = ["CH_NOPE"]
        d["briefing_template"] = "missing_template"

    kb = _mutated(tmp_path, "legal_issues/tenancy_defects.yaml", mutate)
    text = "\n".join(kb.errors)
    assert "unbekannter Fakt 'does_not_exist'" in text
    assert "unbekannte Fachperson 'nobody'" in text
    assert "unbekannte Quelle 'CH_NOPE'" in text
    assert "Briefing-Vorlage 'missing_template'" in text


def test_invalid_action_and_schema_version_and_bad_yaml(tmp_path):
    def mutate(d):
        d["escalation_rules"][0]["action"] = "PROCEED"  # a rule may never grant PROCEED

    kb = _mutated(tmp_path, "legal_issues/tenancy_defects.yaml", mutate)
    assert not kb.valid

    kb2 = _mutated(
        tmp_path, "legal_issues/unpaid_salary.yaml", lambda d: d.update(schema_version=99)
    )
    assert any("schema_version" in e for e in kb2.errors)

    dest = tmp_path / "kb3"
    shutil.copytree(KB, dest)
    (dest / "legal_issues" / "unpaid_salary.yaml").write_text("id: [unclosed", encoding="utf-8")
    kb3 = load_knowledge_base(dest)
    assert any("Ungültiges YAML" in e for e in kb3.errors)


def test_conditional_fact_required_if_must_not_combine_with_required(tmp_path):
    def mutate(d):
        next(f for f in d["facts"] if f.get("required_if"))["required"] = (
            True  # already has required_if
        )

    kb = _mutated(tmp_path, "legal_issues/CH_TENANCY_TERMINATION.yaml", mutate)
    assert not kb.valid
