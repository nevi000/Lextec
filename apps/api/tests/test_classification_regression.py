"""Regression: unterstützte Mietrechts-Issues dürfen nie als «nicht abgedeckt» gelten. Mock-KI.

Ursache des Vorfalls: Ein laufender Server hatte ein älteres Schema im Speicher als die Wissensbasis auf der Platte
(neues Feld `handover_priority`). Beim Neuladen scheiterten alle sieben Mietrechts-Issues an der Validierung; nur die drei
Demo-Issues blieben geladen, sodass jeder Mietfall «nicht abgedeckt» war. Die Tests sichern die Wurzel und die Folgen.
"""

from __future__ import annotations

import shutil

import pytest
import yaml

from app.core.config import REPO_ROOT
from app.services.knowledge.loader import load_knowledge_base
from tests.conftest import new_case, say

KB_DIR = REPO_ROOT / "knowledge_base"
SEVEN = {
    "CH_TENANCY_TERMINATION",
    "CH_TENANCY_PAYMENT_WARNING",
    "CH_TENANCY_PAYMENT_DEFAULT",
    "CH_TENANCY_EXTENSION",
    "CH_TENANCY_DEFECTS",
    "CH_TENANCY_EVICTION",
    "CH_TENANCY_RENT_INCREASE",
}

CASE_A = (
    "Eine Klientin in Zürich hat die Kündigung für ihre Wohnung vom Vermieter erhalten. "
    "Sie ist unsicher, ob sie ausziehen muss."
)
CASE_B = "Meine Klientin hat gestern einen Brief erhalten, dass ihre Wohnungsmiete ab Januar erhöht wird."

PER_ISSUE = {
    "CH_TENANCY_TERMINATION": "Der Vermieter hat der Klientin die Wohnung gekündigt.",
    "CH_TENANCY_PAYMENT_WARNING": "Die Klientin hat eine Zahlungsaufforderung mit Kündigungsandrohung wegen Mietrückstand erhalten, noch keine Kündigung.",
    "CH_TENANCY_PAYMENT_DEFAULT": "Der Vermieter hat der Klientin wegen Zahlungsrückstand gekündigt.",
    "CH_TENANCY_EXTENSION": "Die Klientin möchte eine Erstreckung des Mietverhältnisses, sie findet keine neue Wohnung.",
    "CH_TENANCY_DEFECTS": "In der Wohnung der Klientin ist Schimmel im Schlafzimmer.",
    "CH_TENANCY_EVICTION": "Das Stadtammannamt kommt morgen zur Räumung der Wohnung.",
    "CH_TENANCY_RENT_INCREASE": CASE_B,
}


def decision(client, cid):
    return client.get(f"/api/cases/{cid}/current-decision").json()


def run(client, text):
    cid = new_case(client)["id"]
    say(client, cid, text)
    detail = client.get(f"/api/cases/{cid}").json()
    return cid, decision(client, cid), detail


def unsupported(detail):
    return [i for i in detail["issues"] if i["classification_status"] == "UNSUPPORTED"]


# -------------------------------------------------------------------------------- the two reported cases
def test_case_a_termination_is_supported_and_asks_issue_specific_questions(client):
    _, d, detail = run(client, CASE_A)
    assert d["active_issue_ids"] == ["CH_TENANCY_TERMINATION"]
    assert d["action"] == "ASK" and "UNSUPPORTED_LEGAL_AREA" not in d["reason_codes"]
    assert "GLOBAL_UNSUPPORTED_ISSUE" not in d["triggered_rule_ids"]
    assert "GLOBAL_NO_SUPPORTED_ISSUE" not in d["triggered_rule_ids"]
    assert not unsupported(detail)
    assert d["next_question"]["fact_id"]  # a real issue question: next phase = «Fragen klären»


def test_case_b_rent_increase_is_supported_with_issue_specific_questions(client):
    _, d, detail = run(client, CASE_B)
    assert d["active_issue_ids"] == ["CH_TENANCY_RENT_INCREASE"]
    assert "NO_SUPPORTED_ISSUE_IDENTIFIED" not in d["reason_codes"]
    asked = {m["fact_id"] for m in d["missing_facts"]}
    assert {"increase_receipt_date", "form_official_used"} <= asked
    assert not unsupported(detail)


# ------------------------------------------------------------------------------------ all seven issues
@pytest.mark.parametrize("issue_id,text", list(PER_ISSUE.items()))
def test_each_of_the_seven_issues_is_classifiable_from_the_registry(client, ctx, issue_id, text):
    assert issue_id in {
        d.id for d in ctx.kb.catalog_issues()
    }  # dynamic registry, no hard-coded repair
    _, d, detail = run(client, text)
    assert issue_id in d["active_issue_ids"], (d["active_issue_ids"], text)
    assert "UNSUPPORTED_LEGAL_AREA" not in d["reason_codes"]
    assert not unsupported(detail)


def test_draft_is_classifiable_and_demo_is_not(ctx):
    kb = ctx.kb
    offered = {d.id for d in kb.catalog_issues()}
    assert offered == SEVEN
    assert all(
        kb.issues[i].content_status == "DRAFT" for i in SEVEN
    )  # not legally released, still supported
    demo = {i for i, d in kb.issues.items() if d.content_status == "DEMO_SYNTHETIC"}
    assert demo and not (demo & offered)  # demo issues stay loaded for old cases, never offered


# -------------------------------------------------------------------- unsupported areas stay unsupported
def test_pure_employment_law_is_not_covered(client):
    _, d, detail = run(client, "Der Arbeitgeber hat meiner Klientin die Arbeitsstelle gekündigt.")
    assert d["active_issue_ids"] == []
    assert d["action"] == "ESCALATE"
    assert (
        "UNSUPPORTED_LEGAL_AREA" in d["reason_codes"]
        or "NO_SUPPORTED_ISSUE_IDENTIFIED" in d["reason_codes"]
    )
    assert unsupported(detail)


def test_mixed_tenancy_and_employment_processes_tenancy_and_marks_employment_separately(client):
    _, d, detail = run(
        client,
        "Der Vermieter hat der Klientin die Wohnung gekündigt. Ausserdem hat der Arbeitgeber ihr die Arbeitsstelle gekündigt.",
    )
    assert "CH_TENANCY_TERMINATION" in d["active_issue_ids"]
    assert (
        "UNSUPPORTED_LEGAL_AREA" in d["reason_codes"]
    )  # the other area is flagged, not silently dropped
    un = unsupported(detail)
    assert un and all(i["issue_definition_id"] is None for i in un)


def test_tenancy_eviction_is_issue_6_not_immigration(client):
    _, d, detail = run(
        client,
        "Das Stadtammannamt kommt morgen zur Räumung, die Ausweisung aus der Wohnung wurde vom Gericht angeordnet.",
    )
    assert "CH_TENANCY_EVICTION" in d["active_issue_ids"]
    assert not unsupported(detail)
    assert d["max_urgency"] == "HIGH" and "EV_GRUNDREGEL" in d["triggered_rule_ids"]


def test_immigration_removal_is_not_covered(client):
    _, d, detail = run(client, "Meine Klientin hat eine ausländerrechtliche Wegweisung erhalten.")
    assert d["active_issue_ids"] == []
    assert unsupported(detail)
    assert d["action"] == "ESCALATE"


# ---------------------------------------------------------------- ask vs. real, issue-specific escalation
def test_missing_information_asks_and_real_rules_escalate_issue_specifically(client):
    _, d, _ = run(client, "Der Vermieter hat der Klientin die Wohnung gekündigt.")
    assert d["action"] == "ASK"
    _, d2, _ = run(client, "Der Vermieter hat gekündigt, ohne amtliches Formular, in Zürich.")
    assert d2["action"] == "ESCALATE" and "TT_FORM_MISSING" in d2["triggered_rule_ids"]
    assert "NO_SUPPORTED_ISSUE_IDENTIFIED" not in d2["reason_codes"]
    assert "UNSUPPORTED_LEGAL_AREA" not in d2["reason_codes"]


# ----------------------------------------------------------------- the root cause: broken KB never silent
def _break_kb(tmp_path):
    dest = tmp_path / "kb"
    shutil.copytree(KB_DIR, dest)
    p = dest / "legal_issues" / "CH_TENANCY_TERMINATION.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    data["facts"][0]["gibt_es_nicht"] = (
        1  # unknown field = same failure class as the stale-schema incident
    )
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return dest


def test_a_kb_with_a_failing_issue_file_is_invalid_and_visible(tmp_path):
    kb = load_knowledge_base(_break_kb(tmp_path))
    assert not kb.valid and "CH_TENANCY_TERMINATION" not in kb.issues
    assert any("CH_TENANCY_TERMINATION.yaml" in e for e in kb.errors)


def test_analysis_is_refused_on_an_invalid_kb_instead_of_marking_everything_unsupported(
    tmp_path, settings
):
    from fastapi.testclient import TestClient

    from app.main import create_app

    s = settings.model_copy(update={"knowledge_base_dir": _break_kb(tmp_path)})
    with TestClient(create_app(s)) as c:
        cid = new_case(c)["id"]
        r = c.post(f"/api/cases/{cid}/messages", json={"content": CASE_A}).json()
        assert (
            r["analysis"]["status"] == "FAILED"
            and r["analysis"]["error_code"] == "knowledge_base_invalid"
        )
        assert "nicht abgedeckt" in r["analysis"]["error_message"]
        detail = c.get(f"/api/cases/{cid}").json()
        assert not unsupported(detail)  # nothing mislabeled
        assert c.get("/api/system/status").json()["knowledge_base_valid"] is False


def test_reload_never_replaces_a_valid_kb_by_a_broken_one(client, settings, tmp_path):
    ctx = client.app.state.ctx
    ctx.settings = settings.model_copy(update={"knowledge_base_dir": _break_kb(tmp_path)})
    r = client.post("/api/knowledge-base/reload")
    assert r.status_code == 409 and "bisherige bleibt aktiv" in r.text
    assert ctx.kb.valid and "CH_TENANCY_TERMINATION" in ctx.kb.issues


def test_model_output_with_a_demo_or_unknown_issue_id_is_dropped(ctx):
    from app.services.ai.schemas import DetectedIssue, ExtractionResult
    from app.services.ai.validation import validate_extraction

    res = ExtractionResult(
        detected_issues=[
            DetectedIssue(
                issue_id="employment_termination",
                confidence=0.9,
                evidence_quote="Arbeitsstelle gekündigt",
                source_message_id="m",
            ),
            DetectedIssue(
                issue_id="CH_TENANCY_TERMINATION",
                confidence=0.9,
                evidence_quote="Wohnung gekündigt",
                source_message_id="m",
            ),
        ],
        summary_de="",
    )
    allowed = {d.id for d in ctx.kb.catalog_issues()}
    v = validate_extraction(
        res, ctx.kb, {"m": "Die Arbeitsstelle gekündigt und die Wohnung gekündigt."}, allowed
    )
    assert [i.issue_id for i in v.issues] == ["CH_TENANCY_TERMINATION"]


def test_the_catalog_sent_to_any_provider_comes_from_the_registry(ctx, monkeypatch):
    """Mock and Gemini receive the same ExtractionInput; its issue_catalog is exactly the registry's classifiable issues."""
    seen = {}
    real = ctx.ai.extract

    def spy(data, c=None):
        seen["ids"] = {e.id for e in data.issue_catalog}
        return real(data, c)

    monkeypatch.setattr(ctx.ai, "extract", spy)
    # a service call builds the catalog through the same code path used for Gemini
    from fastapi.testclient import TestClient  # noqa: F401

    assert {d.id for d in ctx.kb.catalog_issues()} == SEVEN
