"""AI cost control: limits are enforced BEFORE a request, usage is logged from real usage metadata,
no endless retries, no duplicate paid analysis. The Gemini SDK client is always faked here."""

from __future__ import annotations

import threading
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.base import Base
from app.db.session import make_engine, make_session_factory
from app.models.tables import AIUsage
from app.services.ai.base import (
    AIBudgetExceededError,
    AIProviderError,
    AIRateLimitError,
    CallContext,
    build_provider,
)
from app.services.ai.gemini import GeminiProvider
from app.services.ai.mock import MockAIProvider
from app.services.ai.schemas import ExtractionInput, ExtractionResult
from app.services.ai.usage import UsageGate, pricing_for
from tests.conftest import new_case, say


def make_gate(tmp_path, **limits) -> tuple[UsageGate, object, Settings]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'u.db').as_posix()}")
    Base.metadata.create_all(engine)
    sf = make_session_factory(engine)
    s = Settings(gemini_api_key="k", ai_provider="gemini", _env_file=None, **limits)
    return UsageGate(sf, s), sf, s


def usage(inp=100, out=50, think=0):
    return SimpleNamespace(
        prompt_token_count=inp,
        candidates_token_count=out,
        thoughts_token_count=think,
        total_token_count=inp + out + think,
    )


def count(sf, status=None):
    with sf() as s:
        stmt = select(func.count()).select_from(AIUsage)
        if status:
            stmt = stmt.where(AIUsage.status == status)
        return s.scalar(stmt)


# ---- pricing ---------------------------------------------------------------------------------------------
def test_official_price_schedule_and_unknown_models_are_not_guessed():
    s = Settings(_env_file=None)
    p = pricing_for("gemini-3.8-flash", s, date(2026, 11, 7))
    assert (p.input_per_mtok, p.output_per_mtok) == (0.75, 3.75)
    p27 = pricing_for("gemini-3.8-flash", s, date(2027, 1, 2))
    assert (p27.input_per_mtok, p27.output_per_mtok) == (1.50, 7.50)
    assert pricing_for("some-unknown-model", s) is None  # never invented
    override = Settings(ai_price_input_per_mtok=1.0, ai_price_output_per_mtok=2.0, _env_file=None)
    assert pricing_for("anything", override).cost(1_000_000, 1_000_000) == 3.0


# ---- limits enforced before the call ---------------------------------------------------------------------
def test_usage_is_logged_with_real_token_counts_and_cost(tmp_path):
    gate, sf, _ = make_gate(tmp_path)
    uid = gate.reserve(
        case_id="c1", function="extract", model="gemini-3.8-flash", est_input_tokens=500
    )
    gate.complete(uid, usage_metadata=usage(1000, 200, 300), status="OK")
    with sf() as s:
        row = s.get(AIUsage, uid)
        assert (row.input_tokens, row.output_tokens, row.thinking_tokens, row.total_tokens) == (
            1000,
            200,
            300,
            1500,
        )
        assert row.status == "OK" and row.cost_known
        assert row.cost_usd == pytest.approx(
            (1000 * 0.75 + 500 * 3.75) / 1e6
        )  # thinking billed as output
    summ = gate.summary()
    assert (
        summ["calls_today"] == 1
        and summ["input_tokens_today"] == 1000
        and summ["output_tokens_today"] == 500
    )
    assert summ["estimated_cost_today_usd"] == pytest.approx(0.002625)


def test_daily_request_limit_blocks_before_sending(tmp_path):
    gate, sf, _ = make_gate(tmp_path, ai_daily_request_limit=2)
    for _ in range(2):
        gate.complete(
            gate.reserve(case_id=None, function="x", model="gemini-3.8-flash", est_input_tokens=10),
            usage_metadata=usage(),
            status="OK",
        )
    with pytest.raises(AIBudgetExceededError) as e:
        gate.reserve(case_id=None, function="x", model="gemini-3.8-flash", est_input_tokens=10)
    assert e.value.reason == "daily_requests" and "tägliche Limit" in e.value.message
    assert (
        count(sf, "BLOCKED") == 1 and count(sf, "OK") == 2
    )  # blocked attempts are recorded, not counted


def test_per_case_call_limit_and_input_token_limit(tmp_path):
    gate, _, _ = make_gate(tmp_path, ai_max_calls_per_case=2, ai_max_input_tokens_per_call=1000)
    with pytest.raises(AIBudgetExceededError) as e:
        gate.reserve(case_id="c", function="x", model="gemini-3.8-flash", est_input_tokens=1001)
    assert e.value.reason == "input_tokens_per_call"
    for _ in range(2):
        gate.complete(
            gate.reserve(case_id="c", function="x", model="gemini-3.8-flash", est_input_tokens=10),
            usage_metadata=usage(),
            status="OK",
        )
    with pytest.raises(AIBudgetExceededError) as e2:
        gate.reserve(case_id="c", function="x", model="gemini-3.8-flash", est_input_tokens=10)
    assert e2.value.reason == "case_calls"
    gate.reserve(
        case_id="other-case", function="x", model="gemini-3.8-flash", est_input_tokens=10
    )  # unaffected


def test_budgets_use_worst_case_reservation(tmp_path):
    # worst case of one call: 7_000 in * 0.75 + 1500 out * 3.75 = 0.010875 USD
    gate, _, _ = make_gate(tmp_path, ai_case_budget_usd=0.015, ai_daily_budget_usd=0.5)
    gate.reserve(case_id="c", function="x", model="gemini-3.8-flash", est_input_tokens=7000)
    with pytest.raises(
        AIBudgetExceededError
    ) as e:  # a second reservation would exceed the case budget
        gate.reserve(case_id="c", function="x", model="gemini-3.8-flash", est_input_tokens=7000)
    assert e.value.reason == "case_budget"
    gate2, _, _ = make_gate(
        tmp_path / "b" if (tmp_path / "b").mkdir() is None else tmp_path, ai_daily_budget_usd=0.02
    )
    gate2.reserve(case_id=None, function="x", model="gemini-3.8-flash", est_input_tokens=7000)
    with pytest.raises(AIBudgetExceededError) as e2:
        gate2.reserve(case_id=None, function="x", model="gemini-3.8-flash", est_input_tokens=7000)
    assert e2.value.reason == "daily_budget"


def test_unknown_price_is_reported_unknown_and_token_cap_still_applies(tmp_path):
    gate, _, _ = make_gate(tmp_path, ai_daily_token_limit=3000, ai_max_output_tokens_per_call=1000)
    uid = gate.reserve(case_id=None, function="x", model="mystery-model", est_input_tokens=100)
    gate.complete(uid, usage_metadata=usage(), status="OK")
    summ = gate.summary()
    assert summ["cost_known"] is False and summ["estimated_cost_today_usd"] is None  # not invented
    with pytest.raises(AIBudgetExceededError) as e:  # 150 used + 3000 est -> over the token cap
        gate.reserve(case_id=None, function="x", model="mystery-model", est_input_tokens=3000)
    assert e.value.reason == "daily_tokens"


def test_parallel_requests_cannot_bypass_the_limit(tmp_path):
    gate, sf, _ = make_gate(tmp_path, ai_daily_request_limit=3)
    ok, blocked = [], []
    barrier = threading.Barrier(10)

    def worker():
        barrier.wait()
        try:
            ok.append(
                gate.reserve(
                    case_id=None, function="x", model="gemini-3.8-flash", est_input_tokens=10
                )
            )
        except AIBudgetExceededError:
            blocked.append(1)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(ok) == 3 and len(blocked) == 7
    assert count(sf, "RESERVED") == 3  # reservations count immediately, before any call finishes


# ---- Gemini provider with a faked SDK client ---------------------------------------------------------------
class FakeModels:
    def __init__(self, behaviour):
        self.behaviour, self.calls = list(behaviour), 0

    def generate_content(self, **kw):
        self.calls += 1
        item = self.behaviour.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(text=item, usage_metadata=usage(321, 45, 7))


def gemini(tmp_path, behaviour, **limits):
    gate, sf, s = make_gate(tmp_path, **limits)
    p = GeminiProvider(s, gate)
    models = FakeModels(behaviour)
    p._client = SimpleNamespace(models=models)
    return p, models, sf


def api_error(code):
    from google.genai import errors

    return errors.APIError(code, {"error": {"message": "x", "status": "X"}})


def empty_input():
    return ExtractionInput(new_messages=[], issue_catalog=[], fact_catalog=[])


def test_blocked_call_never_reaches_the_client(tmp_path):
    p, models, sf = gemini(
        tmp_path, [ExtractionResult().model_dump_json()], ai_daily_request_limit=0
    )
    with pytest.raises(AIBudgetExceededError):
        p.extract(empty_input(), CallContext("c", "extract"))
    assert models.calls == 0, "a blocked request must not be sent to Google"
    assert count(sf, "BLOCKED") == 1


def test_gemini_call_logs_usage_metadata_from_the_response(tmp_path):
    p, models, sf = gemini(tmp_path, [ExtractionResult(summary_de="ok").model_dump_json()])
    assert p.extract(empty_input(), CallContext("case-1", "extract")).summary_de == "ok"
    with sf() as s:
        row = s.scalars(select(AIUsage)).one()
        assert row.case_id == "case-1" and row.function == "extract" and row.model == p.model
        assert (row.input_tokens, row.output_tokens, row.thinking_tokens, row.status) == (
            321,
            45,
            7,
            "OK",
        )


def test_retries_are_bounded_and_every_attempt_is_counted(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    p, models, sf = gemini(tmp_path, [api_error(503)] * 5, ai_max_retries=1)
    with pytest.raises(AIProviderError):
        p.extract(empty_input(), CallContext("c", "extract"))
    assert models.calls == 2, "1 call + 1 retry, never an endless loop"
    assert count(sf, "ERROR") == 2


def test_rate_limit_is_not_retried_into_the_budget(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    p, models, _ = gemini(tmp_path, [api_error(429), api_error(429)], ai_max_retries=0)
    with pytest.raises(AIRateLimitError):
        p.extract(empty_input(), CallContext("c", "extract"))
    assert models.calls == 1


def test_request_config_caps_output_and_thinking(tmp_path):
    p, _, _ = gemini(tmp_path, [], ai_max_output_tokens_per_call=777)
    cfg = p._config("sys", {"type": "object"})
    assert cfg.max_output_tokens == 777
    assert cfg.thinking_config is not None  # kept minimal so reasoning tokens do not inflate cost


# ---- no accidental AI use ----------------------------------------------------------------------------------
def test_tests_never_use_the_real_provider(settings):
    assert settings.ai_provider == "mock" and settings.gemini_api_key is None
    assert isinstance(build_provider(settings), MockAIProvider)


def test_loading_pages_and_usage_endpoints_never_call_the_ai(client, ctx):
    calls = {"n": 0}

    class Boom:
        name, model = "gemini", "boom"

        def extract(self, *a, **k):
            calls["n"] += 1
            raise AssertionError("AI must not be called")

        rephrase_question = extract

    ctx.ai = Boom()
    cid = new_case(client)["id"]
    for url in (
        "/api/dashboard",
        "/api/cases",
        f"/api/cases/{cid}",
        f"/api/cases/{cid}/facts",
        f"/api/cases/{cid}/decisions",
        f"/api/cases/{cid}/current-decision",
        "/api/system/status",
        "/api/ai/usage",
        "/api/knowledge-base/status",
        "/api/evaluation/scenarios",
    ):
        assert client.get(url).status_code == 200, url
    client.post("/api/evaluation/run")
    assert calls["n"] == 0


def test_double_submit_creates_one_message_and_one_analysis(client, ctx):
    calls = {"n": 0}
    real = ctx.ai

    class Counting:
        name, model = real.name, real.model

        def extract(self, data, c=None):
            calls["n"] += 1
            return real.extract(data, c)

        def rephrase_question(self, q, c, x=None):
            return q

    ctx.ai = Counting()
    cid = new_case(client)["id"]
    a = say(client, cid, "Mein Vermieter hat mir gekündigt.")
    b = say(client, cid, "Mein Vermieter hat mir gekündigt.")  # accidental second click
    assert a["message"]["id"] == b["message"]["id"]
    assert len(client.get(f"/api/cases/{cid}/messages").json()) == 1 and calls["n"] == 1
    client.post(f"/api/cases/{cid}/analyze")  # nothing pending -> no call
    assert calls["n"] == 1


def test_concurrent_analysis_of_one_case_is_rejected(client, ctx):
    from app.core.errors import ConflictError
    from app.services.cases.service import _single_flight

    cid = new_case(client)["id"]
    with _single_flight(cid), pytest.raises(ConflictError):
        with _single_flight(cid):
            pass
    with _single_flight(cid):  # released afterwards
        pass


class AlwaysFails:
    name, model = "gemini", "fake"

    def __init__(self, exc):
        self.exc, self.calls = exc, 0

    def extract(self, data, c=None):
        self.calls += 1
        raise self.exc

    def rephrase_question(self, q, c, x=None):
        return q


def test_failed_analysis_stops_after_max_attempts(client, ctx):
    from app.services.ai.base import AIUnavailableError

    prov = AlwaysFails(AIUnavailableError("down", retryable=True))
    ctx.ai = prov
    cid = new_case(client)["id"]
    r = say(client, cid, "Mein Vermieter hat mir gekündigt.")
    assert r["analysis"]["status"] == "FAILED"
    for _ in range(2):
        assert client.post(f"/api/cases/{cid}/analyze").status_code == 200
    assert prov.calls == 3
    r = client.post(f"/api/cases/{cid}/analyze")  # 4th attempt: refused, no AI call
    assert (
        r.status_code == 409
        and "keine weiteren automatischen Versuche" in r.json()["error"]["message"]
    )
    assert prov.calls == 3


def test_limit_block_is_not_counted_as_an_attempt_and_is_explained(client, ctx):
    prov = AlwaysFails(AIBudgetExceededError("Tageslimit erreicht.", reason="daily_requests"))
    ctx.ai = prov
    cid = new_case(client)["id"]
    r = say(client, cid, "Mein Vermieter hat mir gekündigt.")
    assert r["analysis"]["status"] == "FAILED" and r["analysis"]["error_code"] == "ai_limit_reached"
    assert "Tageslimit" in r["analysis"]["error_message"]
    for _ in range(5):  # blocked-before-send never exhausts the attempts
        assert client.post(f"/api/cases/{cid}/analyze").status_code == 200


def test_usage_report_for_gemini_mode(client, ctx, tmp_path):
    gate, _, _ = make_gate(tmp_path)
    gate.complete(
        gate.reserve(
            case_id="c", function="extract", model="gemini-3.8-flash", est_input_tokens=100
        ),
        usage_metadata=usage(10, 5),
        status="OK",
    )
    ctx.gate = gate
    ctx.ai = SimpleNamespace(name="gemini", model="gemini-3.8-flash")
    st = client.get("/api/system/status").json()
    assert st["ai_is_external"] and st["ai_usage"]["calls_today"] == 1
    rep = client.get("/api/ai/usage").json()
    assert rep["summary"]["calls_today"] == 1 and rep["recent"][0]["input_tokens"] == 10
    assert "message" not in str(rep).lower().replace(
        "error_message", ""
    )  # no message content is stored
