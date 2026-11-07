from __future__ import annotations

import pytest

from app.core.config import REPO_ROOT, Settings
from app.services.ai.base import (
    AIConfigurationError,
    AIInvalidResponseError,
    AIProviderError,
    AIRateLimitError,
    AIUnavailableError,
    build_provider,
)
from app.services.ai.gemini import GeminiProvider
from app.services.ai.schemas import (
    DetectedIssue,
    ExtractedFact,
    ExtractionInput,
    ExtractionResult,
    UnrecognizedIssue,
)
from app.services.ai.validation import coerce_value, quote_in_message, validate_extraction
from app.services.knowledge.loader import load_knowledge_base
from tests.conftest import new_case, say

KB = load_knowledge_base(REPO_ROOT / "knowledge_base")
MSG = {"m1": "Mein Arbeitgeber hat mir am 15.01.2026 gekündigt."}


def run(result: ExtractionResult):
    return validate_extraction(result, KB, MSG)


def test_fabricated_evidence_is_rejected():
    res = ExtractionResult(
        detected_issues=[
            DetectedIssue(
                issue_id="employment_termination",
                confidence=0.9,
                evidence_quote="Der Chef hat mich gefeuert",
                source_message_id="m1",
            )
        ],
        facts=[
            ExtractedFact(
                fact_id="incapacity_for_work",
                value="ja",
                evidence_quote="ich bin krank",
                source_message_id="m1",
            )
        ],
    )
    v = run(res)
    assert v.issues == [] and v.facts == []
    assert len(v.warnings) == 2


def test_unknown_ids_and_unknown_message_rejected():
    res = ExtractionResult(
        detected_issues=[
            DetectedIssue(
                issue_id="patent_law",
                confidence=1,
                evidence_quote="gekündigt",
                source_message_id="m1",
            )
        ],
        facts=[
            ExtractedFact(
                fact_id="made_up", value="x", evidence_quote="gekündigt", source_message_id="m1"
            ),
            ExtractedFact(
                fact_id="employer_termination_received",
                value="ja",
                evidence_quote="gekündigt",
                source_message_id="zzz",
            ),
        ],
    )
    v = run(res)
    assert not v.issues and not v.facts and len(v.warnings) == 3


def test_valid_extraction_is_typed_and_bad_values_become_ambiguous():
    res = ExtractionResult(
        detected_issues=[
            DetectedIssue(
                issue_id="employment_termination",
                confidence=0.8,
                evidence_quote="hat mir am 15.01.2026 gekündigt",
                source_message_id="m1",
            )
        ],
        facts=[
            ExtractedFact(
                fact_id="employer_termination_received_date",
                value="15.01.2026",
                evidence_quote="15.01.2026",
                source_message_id="m1",
            ),
            ExtractedFact(
                fact_id="employer_termination_received",
                value="vielleicht",
                evidence_quote="gekündigt",
                source_message_id="m1",
            ),
        ],
        unrecognized_issues=[
            UnrecognizedIssue(
                description="Erbrecht", evidence_quote="Arbeitgeber", source_message_id="m1"
            )
        ],
    )
    v = run(res)
    typed = {f.fact_id: t for f, t in v.facts}
    assert typed["employer_termination_received_date"] == "2026-01-15"
    assert typed["employer_termination_received"] is None  # unusable -> ambiguous
    assert any("unbrauchbar" in w for w in v.warnings)
    assert len(v.unsupported) == 1 and len(v.issues) == 1


def test_quote_matching_is_whitespace_and_case_insensitive():
    assert quote_in_message("  ARBEITGEBER   hat\nmir ", MSG["m1"])
    assert not quote_in_message("", MSG["m1"])


def test_coerce_value_types():
    fd = lambda t, **k: next(f for i in KB.issues.values() for f in i.facts if f.data_type == t)  # noqa: E731
    boolean, date_, integer = fd("boolean"), fd("date"), fd("integer")
    assert coerce_value(boolean, "Ja") is True and coerce_value(boolean, "nein.") is False
    assert coerce_value(date_, "5.3.2024") == "2024-03-05"
    assert coerce_value(integer, "CHF 8'400") == 8400
    for f, bad in [(boolean, "eventuell"), (date_, "31.02.2024"), (integer, "viel")]:
        with pytest.raises(ValueError):
            coerce_value(f, bad)


# ---- failure handling in the pipeline -----------------------------------------------------
class FailingProvider:
    name = "gemini"
    model = "fake"

    def __init__(self, exc: AIProviderError):
        self.exc = exc

    def extract(self, data, ctx=None):
        raise self.exc

    def rephrase_question(self, q, c, ctx=None):
        return q


def test_ai_failure_keeps_message_and_exposes_failed_state_then_retry_succeeds(client, ctx):
    mock = ctx.ai
    ctx.ai = FailingProvider(AIRateLimitError("Kontingent erreicht", retryable=True))
    case = new_case(client)
    cid = case["id"]
    r = say(client, cid, "Mein Vermieter hat der Klientin die Wohnung gekündigt.")
    assert r["analysis"]["status"] == "FAILED" and r["analysis"]["error_code"] == "ai_rate_limited"
    assert r["message"]["analysis_status"] == "FAILED"
    msgs = client.get(f"/api/cases/{cid}/messages").json()
    assert len(msgs) == 1 and msgs[0]["content"].startswith("Mein Vermieter")
    detail = client.get(f"/api/cases/{cid}").json()
    assert detail["analysis"]["status"] == "FAILED"
    assert detail["issues"] == [], "no fabricated analysis"
    assert detail["current_decision"] is None
    assert client.post(f"/api/cases/{cid}/briefings").status_code == 409

    ctx.ai = mock  # provider recovers -> explicit retry
    ok = client.post(f"/api/cases/{cid}/analyze").json()
    assert ok["analysis"]["status"] == "OK" and ok["current_decision"]["action"] == "ASK"
    assert client.get(f"/api/cases/{cid}/messages").json()[0]["analysis_status"] == "DONE"


# ---- Gemini provider (SDK mocked - no network) -----------------------------------------------
def gemini_settings(**kw) -> Settings:
    return Settings(
        ai_provider="gemini", gemini_api_key="test-key", ai_max_retries=1, _env_file=None, **kw
    )


def test_gemini_requires_api_key_no_silent_fallback():
    with pytest.raises(AIConfigurationError):
        build_provider(Settings(ai_provider="gemini", gemini_api_key=None, _env_file=None))
    with pytest.raises(AIConfigurationError):
        GeminiProvider(Settings(ai_provider="gemini", gemini_api_key="", _env_file=None))


class _Resp:
    def __init__(self, text, finish=None):
        self.text = text
        if finish:  # mirrors resp.candidates[0].finish_reason.name
            self.candidates = [
                type("Cand", (), {"finish_reason": type("FR", (), {"name": finish})()})()
            ]


class _Models:
    def __init__(self, behaviour):
        self.behaviour = list(behaviour)
        self.calls = 0
        self.kwargs: list[dict] = []

    def generate_content(self, **kw):
        self.calls += 1
        self.kwargs.append(kw)
        item = self.behaviour.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):  # (text, finish_reason)
            return _Resp(*item)
        return _Resp(item)


def make_gemini(behaviour) -> tuple[GeminiProvider, _Models]:
    p = GeminiProvider(gemini_settings())
    models = _Models(behaviour)
    p._client = type("C", (), {"models": models})()
    return p, models


def api_error(code: int):
    from google.genai import errors

    return errors.APIError(code, {"error": {"message": "x", "status": "X"}})


def _input() -> ExtractionInput:
    return ExtractionInput(new_messages=[], issue_catalog=[], fact_catalog=[])


def test_gemini_valid_json_parsed(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    payload = ExtractionResult(summary_de="ok").model_dump_json()
    p, m = make_gemini([payload])
    assert p.extract(_input()).summary_de == "ok" and m.calls == 1


def test_gemini_retries_transient_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    p, m = make_gemini([api_error(503), ExtractionResult().model_dump_json()])
    p.extract(_input())
    assert m.calls == 2


@pytest.mark.parametrize(
    ("code", "exc"),
    [
        (429, AIRateLimitError),
        (503, AIUnavailableError),
        (401, AIConfigurationError),
        (404, AIConfigurationError),
    ],
)
def test_gemini_error_mapping(monkeypatch, code, exc):
    monkeypatch.setattr("time.sleep", lambda s: None)
    p, _ = make_gemini([api_error(code)] * 3)
    with pytest.raises(exc):
        p.extract(_input())


def test_gemini_invalid_json_and_schema_violation_rejected(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    for bad in ["not json at all", '{"detected_issues": [{"issue_id": 5}]}']:
        p, m = make_gemini([bad, bad])  # one targeted retry, then a clear error
        with pytest.raises(AIInvalidResponseError):
            p.extract(_input())
        assert m.calls == 2


def test_api_key_is_never_in_status_or_repr(client):
    body = client.get("/api/system/status").text
    assert "api_key" not in body.lower() and "test-key" not in body
    assert "test-key" not in repr(gemini_settings())
