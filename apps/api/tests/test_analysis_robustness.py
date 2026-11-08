"""Long, realistic case descriptions: truncated / invalid Gemini answers are classified, retried at most once and never lose data.

Root cause of the field failure (Fall «Demir», Schimmel): the structured answer for a long description needed ~2.5k output
tokens; the cap was 2500, so Gemini stopped with finish_reason MAX_TOKENS and the cut-off JSON failed the Pydantic schema
(«entsprach nicht dem erwarteten Schema»). Both logged calls show 2486 output tokens."""

from __future__ import annotations

import json

import pytest

from app.services.ai.base import AIInvalidResponseError, AIOutputTruncatedError, AIUnavailableError
from app.services.ai.schemas import ExtractedFact, ExtractionResult
from app.services.ai.validation import validate_extraction
from tests.conftest import new_case, say
from tests.test_ai_layer import _input, api_error, make_gemini

GOOD = ExtractionResult(summary_de="ok").model_dump_json()
TRUNCATED_JSON = '{"detected_issues": [{"issue_id": "CH_TENANCY_DEFECTS", "confidence": 0.9, "evidence_quote": "Schimm'


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)


def caps(models) -> list:
    return [k["config"].max_output_tokens for k in models.kwargs]


def test_truncated_answer_is_detected_and_retried_once_with_a_higher_cap():
    p, m = make_gemini([(TRUNCATED_JSON, "MAX_TOKENS"), GOOD])
    assert p.extract(_input()).summary_de == "ok"
    assert m.calls == 2
    first, second = caps(m)
    assert second > first  # the retry may produce a longer answer
    assert "abgeschnitten" in m.kwargs[1]["contents"]  # compact-answer instruction in the retry


def test_truncated_twice_fails_clearly_without_a_third_call():
    p, m = make_gemini([(TRUNCATED_JSON, "MAX_TOKENS"), (TRUNCATED_JSON, "MAX_TOKENS"), GOOD])
    with pytest.raises(AIOutputTruncatedError) as e:
        p.extract(_input())
    assert e.value.code == "ai_output_truncated" and m.calls == 2


def test_truncated_json_is_never_repaired_or_partially_used():
    p, m = make_gemini(
        [(TRUNCATED_JSON, "STOP"), (TRUNCATED_JSON, "STOP")]
    )  # cut-off JSON although finish says STOP
    with pytest.raises(AIInvalidResponseError) as e:
        p.extract(_input())
    assert e.value.code == "ai_schema_mismatch" and m.calls == 2


def test_missing_required_field_gets_one_retry_with_the_field_path_but_no_values():
    bad = json.dumps(
        {"facts": [{"fact_id": "defect_type", "value": "schimmel", "source_message_id": "m1"}]}
    )  # no evidence_quote
    p, m = make_gemini([bad, GOOD])
    assert p.extract(_input()).summary_de == "ok" and m.calls == 2
    hint = json.loads(m.kwargs[1]["contents"])["retry_hinweis"]
    assert (
        "facts.0.evidence_quote" in hint and "schimmel" not in hint
    )  # paths only, never case content


def test_invalid_enum_value_is_dropped_by_validation_not_stored(client):
    """The JSON schema allows any string as value; the knowledge-base validation drops an enum value that is not allowed."""
    kb = client.app.state.ctx.kb
    res = ExtractionResult(
        facts=[
            ExtractedFact(
                fact_id="defect_type",
                value="wasserschaden_phantasie",
                evidence_quote="Schimmel",
                source_message_id="m1",
            )
        ]
    )
    v = validate_extraction(res, kb, {"m1": "Es gibt Schimmel im Kinderzimmer."}, None)
    for (
        fact,
        typed,
    ) in v.facts:  # never stored as a concrete value: at most «unklar» without a value
        assert fact.fact_id == "defect_type" and typed is None and fact.ambiguous
    assert v.warnings  # and the drop is visible


def test_timeout_is_transient_one_retry_then_clear_error():
    p, m = make_gemini([TimeoutError("t"), TimeoutError("t"), GOOD])
    with pytest.raises(AIUnavailableError):
        p.extract(_input())
    assert m.calls == 2  # ai_max_retries=1: bounded, not a loop


def test_timeout_then_success():
    p, m = make_gemini([TimeoutError("t"), GOOD])
    assert p.extract(_input()).summary_de == "ok" and m.calls == 2


def test_normal_answer_costs_exactly_one_call():
    p, m = make_gemini([(GOOD, "STOP")])
    p.extract(_input())
    assert m.calls == 1


def test_503_is_retried_by_the_transport_layer_not_by_the_schema_retry():
    p, m = make_gemini([api_error(503), GOOD])
    p.extract(_input())
    assert m.calls == 2


# ---- service level: no data loss, retry possible -------------------------------------------------------------------------------
LONG = (
    "Frau Elif Demir (34) wohnt mit ihrem Partner und ihrem Sohn Luca (4) in einer 3½-Zimmer-Wohnung in Winterthur. Sie ist die "
    "Hauptmieterin, der Vermieter ist eine Privatperson. Die Wohnung ist keine Gemeindewohnung. Seit Ende August 2026 bildet sich im "
    "Kinderzimmer Schimmel. Er wächst an der Aussenwand hinter Lucas Bett und dem Kleiderschrank und ist inzwischen etwa einen Quadratmeter "
    "gross. Das Zimmer riecht muffig. Beim Einzug im Jahr 2023 war kein Schimmel da. Am 15. September 2026 hat sie den Vermieter per "
    "eingeschriebenem Brief informiert. Der Vermieter hat bis heute nicht reagiert. Luca hustet seit einigen Wochen vor allem nachts. "
    "Seit zwei Wochen schläft Luca im Elternschlafzimmer. Frau Demir zahlt die Miete weiterhin voll. Eine Mahnung oder Kündigung hat sie "
    "nicht erhalten."
)


def test_failed_analysis_keeps_the_description_and_can_be_retried(client, monkeypatch):
    ctx = client.app.state.ctx
    real = ctx.ai.extract
    state = {"fail": True, "calls": 0}

    def flaky(data, c=None):
        state["calls"] += 1
        if state["fail"]:
            raise AIOutputTruncatedError("abgeschnitten")
        return real(data, c)

    monkeypatch.setattr(ctx.ai, "extract", flaky)
    cid = new_case(client)["id"]
    r = say(client, cid, LONG)
    assert (
        r["analysis"]["status"] == "FAILED" and r["analysis"]["error_code"] == "ai_output_truncated"
    )
    msgs = client.get(f"/api/cases/{cid}/messages").json()
    assert msgs[0]["content"] == LONG and msgs[0]["analysis_status"] == "FAILED"  # nothing lost
    assert state["calls"] == 1  # no hidden repeat in the service
    state["fail"] = False
    d = client.post(f"/api/cases/{cid}/analyze").json()
    assert d["analysis"]["status"] == "OK"
    assert "CH_TENANCY_DEFECTS" in {i["issue_definition_id"] for i in d["issues"]}


def test_long_mould_case_is_classified_as_defects_without_invented_facts(client):
    cid = new_case(client)["id"]
    say(client, cid, LONG)
    d = client.get(f"/api/cases/{cid}").json()
    assert "CH_TENANCY_DEFECTS" in {i["issue_definition_id"] for i in d["issues"]}
    known = {
        f["fact_id"]: f["value"]
        for f in client.get(f"/api/cases/{cid}/facts").json()
        if f["status"] == "KNOWN"
    }
    assert known.get("rent_withheld_for_defects") in (
        None,
        False,
    )  # she pays in full: never invented as true
    assert known.get("payment_warning_received") in (None, False)
