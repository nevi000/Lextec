"""Sprachbrücke stability: concurrency, background translation, classified translation errors, rate limits, headers.

Root causes found in the logs of the live demo and covered here:
* desktop + phone polled at the same time and both translated/stored the same new question → IntegrityError →
  PendingRollbackError → HTTP 500 on the phone («Connection lost»)
* the translation ran inside the poll request
* the Gemini daily request limit made translations fail (and the failures were not classified)"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import REPO_ROOT, Settings
from app.main import create_app
from app.models.tables import TranslationCache, VoiceBridgeSession
from app.services.ai.base import AIBudgetExceededError, AIRateLimitError
from tests.conftest import new_case, say
from tests.test_voice_bridge import BASE, answer_value, connect, hdr, mstate, send, start, wstate


@pytest.fixture
def async_client(tmp_path):
    """The production code path: translation runs in the background (not inline)."""
    s = Settings(
        app_env="test",
        ai_provider="mock",
        gemini_api_key=None,
        database_url=f"sqlite:///{(tmp_path / 'async.db').as_posix()}",
        knowledge_base_dir=REPO_ROOT / "knowledge_base",
        bridge_translate_inline=False,
        _env_file=None,
    )
    with TestClient(create_app(s)) as c:
        yield c


def case(client) -> str:
    cid = new_case(client)["id"]
    say(client, cid, BASE)
    return cid


def wait_for(fn, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.05)
    raise AssertionError("condition not reached")


# ---- concurrency: the race that produced «Connection lost» ------------------------------------------------
def test_concurrent_polls_create_one_instance_and_never_fail(async_client, monkeypatch):
    client = async_client
    cid = case(client)
    token = start(client, cid)
    calls = []
    real = client.app.state.ctx.ai.translate

    def slow(texts, source, target, ctx=None):
        calls.append(list(texts))
        time.sleep(0.4)  # a slow Gemini call
        return real(texts, source, target, ctx)

    monkeypatch.setattr(client.app.state.ctx.ai, "translate", slow)
    client.post("/api/bridge/language", json={"language": "en"}, headers=hdr(token))

    codes: list[int] = []

    def phone():
        for _ in range(12):
            codes.append(client.get("/api/bridge/state", headers=hdr(token)).status_code)

    def desk():
        for _ in range(12):
            codes.append(client.get(f"/api/cases/{cid}/voice-bridge").status_code)

    threads = [threading.Thread(target=f) for f in (phone, desk, phone, desk)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert set(codes) == {200}, set(codes)  # no 500, no lock error
    assert len(calls) == 1, calls  # translated once, not once per poller
    wait_for(lambda: mstate(client, token)["question"] is not None)
    with client.app.state.ctx.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(VoiceBridgeSession)) == 1


def test_a_poll_never_waits_for_the_translation(async_client, monkeypatch):
    client = async_client
    cid = case(client)
    token = start(client, cid)
    gate = threading.Event()
    real = client.app.state.ctx.ai.translate

    def blocked(texts, source, target, ctx=None):
        gate.wait(10)
        return real(texts, source, target, ctx)

    monkeypatch.setattr(client.app.state.ctx.ai, "translate", blocked)
    t0 = time.time()
    s = client.post("/api/bridge/language", json={"language": "uk"}, headers=hdr(token)).json()
    assert time.time() - t0 < 2.0  # returned although the translation is still running
    assert s["status"] == "QUESTION_ACTIVE" and s["question"] is None
    assert s["notice"] == "translation_pending"
    assert wstate(client, cid)["question"]["translation_status"] == "PENDING"
    gate.set()
    q = wait_for(lambda: mstate(client, token)["question"])
    assert q["text"].startswith("[UK · Mock]")


def test_pending_question_cannot_be_answered_and_does_not_end_the_session(
    async_client, monkeypatch
):
    client = async_client
    cid = case(client)
    token = start(client, cid)
    gate = threading.Event()
    real = client.app.state.ctx.ai.translate

    def blocked(*a, **k):
        gate.wait(10)
        return real(*a, **k)

    monkeypatch.setattr(client.app.state.ctx.ai, "translate", blocked)
    client.post("/api/bridge/language", json={"language": "ar"}, headers=hdr(token))
    assert client.get("/api/bridge/state", headers=hdr(token)).status_code == 200
    r = client.post(
        "/api/bridge/answer",
        json={"instance_id": "x" * 12, "request_id": "req-pending-1", "kind": "unknown"},
        headers=hdr(token),
    )
    assert r.status_code == 409
    gate.set()


# ---- translation failures are classified and never touch the connection ------------------------------------
@pytest.mark.parametrize(
    "exc,code",
    [
        (AIBudgetExceededError("Limit", reason="daily_requests"), "limit"),
        (AIRateLimitError("429", retryable=True), "rate_limited"),
        (RuntimeError("boom"), "error"),
    ],
)
def test_failure_is_classified_session_stays_connected(client, monkeypatch, exc, code):
    cid = case(client)
    token = start(client, cid)

    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(client.app.state.ctx.ai, "translate", boom)
    s = client.post("/api/bridge/language", json={"language": "en"}, headers=hdr(token)).json()
    assert s["notice"] == "translation_failed" and s["language"] == "en" and s["question"] is None
    assert client.get("/api/bridge/state", headers=hdr(token)).status_code == 200  # still connected
    w = wstate(client, cid)
    assert w["active"] and w["status"] == "QUESTION_ACTIVE"
    assert w["question"]["translation_status"] == "FAILED"
    assert w["question"]["translation_error_code"] == code
    assert w["question"]["translation_error"]


def test_failures_are_not_retried_automatically_and_manual_retries_are_limited(client, monkeypatch):
    from app.services.bridge import service as bs

    cid = case(client)
    token = start(client, cid)
    n = {"calls": 0}

    def boom(*a, **k):
        n["calls"] += 1
        raise RuntimeError("down")

    monkeypatch.setattr(client.app.state.ctx.ai, "translate", boom)
    client.post("/api/bridge/language", json={"language": "en"}, headers=hdr(token))
    for _ in range(10):  # many polls on both devices: no automatic retries, no cost
        mstate(client, token)
        wstate(client, cid)
    assert n["calls"] == 1
    too_soon = client.post(f"/api/cases/{cid}/voice-bridge/retry-translation")
    assert too_soon.status_code == 409 and too_soon.json()["error"]["code"] == "retry_too_soon"
    monkeypatch.setattr(bs, "TRANSLATION_MIN_INTERVAL_S", 0.0)
    codes = [
        client.post(f"/api/cases/{cid}/voice-bridge/retry-translation").status_code
        for _ in range(8)
    ]
    assert codes.count(200) == bs.TRANSLATION_MAX_ATTEMPTS - 1 and codes[-1] == 409
    assert n["calls"] == bs.TRANSLATION_MAX_ATTEMPTS  # bounded: no unlimited Gemini calls


def test_retry_succeeds_and_the_phone_returns_to_the_question(client, monkeypatch):
    from app.services.bridge import service as bs

    cid = case(client)
    token = start(client, cid)
    ai = client.app.state.ctx.ai
    real = ai.translate

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(ai, "translate", boom)
    client.post("/api/bridge/language", json={"language": "uk"}, headers=hdr(token))
    assert mstate(client, token)["notice"] == "translation_failed"
    monkeypatch.setattr(ai, "translate", real)
    monkeypatch.setattr(bs, "TRANSLATION_MIN_INTERVAL_S", 0.0)
    assert client.post(f"/api/cases/{cid}/voice-bridge/retry-translation").status_code == 200
    s = mstate(client, token)
    assert s["question"] is not None and s["notice"] is None
    q = s["question"]  # answers still work afterwards, with the same session
    assert send(client, token, q, answer_value(q)).status_code == 200


def test_translation_is_cached_and_cache_writes_tolerate_duplicates(client, ctx, monkeypatch):
    from app.services.bridge.service import translate_cached

    f, ai = ctx.session_factory, ctx.ai
    text = "Wann haben Sie die Kündigung erhalten?"
    first = translate_cached(f, ai, [text], "en", "c")
    calls = []
    orig = ai.translate

    def counting(*x, **k):
        calls.append(1)
        return orig(*x, **k)

    monkeypatch.setattr(ai, "translate", counting)
    assert translate_cached(f, ai, [text], "en", "c") == first  # served from the cache
    assert calls == []

    def go():
        translate_cached(f, ai, ["Ein ganz neuer Satz."], "ar", "c")

    ts = [threading.Thread(target=go) for _ in range(4)]  # four writers, same key
    [t.start() for t in ts]
    [t.join() for t in ts]
    with f() as s:
        rows = list(
            s.scalars(
                select(TranslationCache.source_text).where(
                    TranslationCache.source_text == "Ein ganz neuer Satz."
                )
            )
        )
    assert rows == ["Ein ganz neuer Satz."]


# ---- heartbeat / sync do not hammer the database ------------------------------------------------------------
def test_polling_writes_only_on_change(client, ctx):
    cid = case(client)
    token = start(client, cid)
    connect(client, token, "en")
    rev = mstate(client, token)["rev"]
    for _ in range(20):
        assert mstate(client, token)["rev"] == rev  # polls do not change the revision
        wstate(client, cid)


def test_session_survives_a_pause_in_polling(client):
    """A locked/backgrounded phone stops polling; the session stays valid and shows the current question afterwards."""
    cid = case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    time.sleep(0.2)
    assert mstate(client, token)["question"]["instance_id"] == q["instance_id"]
    assert wstate(client, cid)["status"] == "QUESTION_ACTIVE"


# ---- rate limits and headers ----------------------------------------------------------------------------------
def test_mobile_responses_are_not_cacheable(client):
    cid = case(client)
    token = start(client, cid)
    r = client.get("/api/bridge/state", headers=hdr(token))
    assert "no-store" in r.headers["cache-control"]
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_unknown_tokens_are_rate_limited_per_client(client):
    lan = {"X-Forwarded-For": "192.168.5.5"}
    codes = [
        client.get("/api/bridge/state", headers={**lan, "X-Bridge-Token": f"guess{i}"}).status_code
        for i in range(40)
    ]
    assert codes[0] == 401 and 429 in codes
    other = client.get(
        "/api/bridge/state", headers={"X-Forwarded-For": "192.168.5.6", "X-Bridge-Token": "x"}
    )
    assert other.status_code == 401  # a different client is not affected


def test_a_valid_token_is_not_throttled_by_normal_polling(client):
    cid = case(client)
    token = start(client, cid)
    lan = {"X-Forwarded-For": "192.168.5.7", **hdr(token)}
    codes = {client.get("/api/bridge/state", headers=lan).status_code for _ in range(40)}
    assert codes == {200}


def test_remote_clients_cannot_reach_docs_or_admin_endpoints(client):
    cid = case(client)
    lan = {"X-Forwarded-For": "192.168.5.8"}
    for path in (
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/ai/usage",
        "/api/knowledge-base/status",
        "/api/system/status",
        f"/api/cases/{cid}/voice-bridge",
        f"/api/cases/{cid}/messages",
        "/api/intake/pdf-text",
    ):
        assert client.get(path, headers=lan).status_code in (403, 405), path
    assert client.get("/api/health", headers=lan).status_code == 200


def test_a_token_belongs_to_exactly_one_case(client):
    a, b = case(client), case(client)
    ta, tb = start(client, a), start(client, b)
    connect(client, ta, "en")
    connect(client, tb, "en")
    qa = mstate(client, ta)["question"]
    # the phone API has no case parameter at all; a token only ever drives its own session
    r = client.post(
        "/api/bridge/answer?case_id=" + b,
        json={
            "instance_id": qa["instance_id"],
            "request_id": "own-case-001",
            "kind": "value",
            "value": answer_value(qa),
            "case_id": b,
        },
        headers=hdr(ta),
    )
    assert r.status_code == 200
    assert wstate(client, a)["answer"] is not None and wstate(client, b)["answer"] is None


def test_tokens_never_appear_in_logs(client, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    cid = case(client)
    token = start(client, cid)
    connect(client, token, "en")
    mstate(client, token)
    assert token not in caplog.text
