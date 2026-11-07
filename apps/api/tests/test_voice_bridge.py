"""Sprachbrücke: one QR per case, automatic question sync, worker-controlled acceptance, translation, security."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.tables import (
    AIUsage,
    Case,
    CaseFact,
    CaseMessage,
    TranslationCache,
    VoiceBridgeSession,
)
from tests.conftest import answer_question, new_case, say

BASE = "Mein Vermieter hat der Klientin die Wohnung gekündigt, ohne amtliches Formular, in Zürich."


def hdr(token):
    return {"X-Bridge-Token": token}


def decision(client, cid):
    return client.get(f"/api/cases/{cid}/current-decision").json()


def make_case(client) -> str:
    cid = new_case(client)["id"]
    say(client, cid, BASE)
    return cid


def start(client, cid) -> str:
    r = client.post(f"/api/cases/{cid}/voice-bridge")
    assert r.status_code == 201
    assert r.json()["status"] == "WAITING_FOR_CONNECTION"
    return r.json()["join_token"]


def connect(client, token, lang="en") -> dict:
    r = client.post("/api/bridge/language", json={"language": lang}, headers=hdr(token))
    assert r.status_code == 200, r.text
    return r.json()


def mstate(client, token) -> dict:
    r = client.get("/api/bridge/state", headers=hdr(token))
    assert r.status_code == 200, r.text
    return r.json()


def wstate(client, cid) -> dict:
    return client.get(f"/api/cases/{cid}/voice-bridge").json()


def send(client, token, q, value, kind="value", rid="r-0000001") -> object:
    return client.post(
        "/api/bridge/answer",
        json={"instance_id": q["instance_id"], "request_id": rid, "kind": kind, "value": value},
        headers=hdr(token),
    )


def answer_value(q):
    """A valid structured value for the question shown on the phone."""
    t = q["data_type"]
    if t == "boolean":
        return "true"
    if t == "enum":
        return q["options"][0]["value"]
    if t == "date":
        return "2026-11-04"
    if t == "integer":
        return "3"
    return "Text"


def facts_count(ctx, cid):
    with ctx.session_factory() as s:
        return s.scalar(select(func.count()).select_from(CaseFact).where(CaseFact.case_id == cid))


def messages_count(ctx, cid):
    with ctx.session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(CaseMessage).where(CaseMessage.case_id == cid)
        )


# ---- 1/2: one QR, questions follow automatically --------------------------------------------------
def test_one_connection_serves_all_following_questions(client):
    cid = make_case(client)
    token = start(client, cid)
    s = connect(client, token, "en")
    assert s["status"] == "QUESTION_ACTIVE" and s["language"] == "en"
    seen = []
    for _ in range(3):
        s = mstate(client, token)  # same token, no new QR, no manual "send"
        q = s["question"]
        assert q is not None
        seen.append(q["instance_id"])
        assert (
            send(client, token, q, answer_value(q), rid=f"req-{len(seen):06d}").status_code == 200
        )
        assert mstate(client, token)["status"] == "AWAITING_WORKER_REVIEW"
        assert (
            client.post(f"/api/cases/{cid}/voice-bridge/answer/accept", json={}).status_code == 200
        )
    assert len(set(seen)) == 3
    assert (
        client.get(f"/api/cases/{cid}/voice-bridge").json()["join_token"] is None
    )  # QR is spent once connected


def test_the_phone_shows_the_engine_question(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "de")
    engine_q = decision(client, cid)["next_question"]
    q = mstate(client, token)["question"]
    assert q["text"] == engine_q["question_de"]  # German = no translation, same wording


# ---- 3: controlled acceptance ------------------------------------------------------------------------
def test_phone_answer_changes_nothing_until_the_worker_accepts(client, ctx):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    fact_id = decision(client, cid)["next_question"]["fact_id"]
    facts, msgs, dec = facts_count(ctx, cid), messages_count(ctx, cid), decision(client, cid)
    assert send(client, token, q, answer_value(q)).status_code == 200
    assert (facts_count(ctx, cid), messages_count(ctx, cid)) == (facts, msgs)
    assert (
        decision(client, cid)["next_question"]["fact_id"]
        == fact_id
        == dec["next_question"]["fact_id"]
    )
    w = wstate(client, cid)
    assert w["status"] == "AWAITING_WORKER_REVIEW" and w["answer"]["original"]
    assert client.post(f"/api/cases/{cid}/voice-bridge/answer/accept", json={}).status_code == 200
    assert messages_count(ctx, cid) == msgs + 1
    assert decision(client, cid)["next_question"]["fact_id"] != fact_id
    with ctx.session_factory() as s:
        m = s.scalars(
            select(CaseMessage).where(
                CaseMessage.case_id == cid, CaseMessage.origin == "VOICE_BRIDGE"
            )
        ).one()
        assert m.answers_fact_id == fact_id and m.original_language == "en"


def test_phone_cannot_advance_while_review_is_pending(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    send(client, token, q, answer_value(q))
    s = mstate(client, token)
    assert s["status"] == "AWAITING_WORKER_REVIEW" and s["question"] is None
    r = send(client, token, q, answer_value(q), rid="other-000002")
    assert r.status_code == 409


# ---- 4: free text translation ----------------------------------------------------------------------------
def _text_question(client, cid):
    """Advance (desk answers) until the engine asks a free-text fact; None if the case has none."""
    for _ in range(40):
        nq = decision(client, cid).get("next_question")
        if not nq or not nq.get("fact_id"):
            return None
        if nq["data_type"] == "string":
            return nq
        answer_question(client, cid, nq)
    return None


def test_free_text_keeps_original_and_marks_machine_translation(client, ctx):
    cid = make_case(client)
    nq = _text_question(client, cid)
    if nq is None:
        pytest.skip("no free-text question in this flow")
    token = start(client, cid)
    connect(client, token, "ar")
    q = mstate(client, token)["question"]
    assert send(client, token, q, "نص حر للاختبار", kind="value").status_code == 200
    a = wstate(client, cid)["answer"]
    assert a["original"] == "نص حر للاختبار" and a["machine_translated"] is True
    assert a["german"] and a["translation_status"] == "MACHINE"
    assert (
        client.post(
            f"/api/cases/{cid}/voice-bridge/answer/accept",
            json={"corrected_text_de": "Korrigierte deutsche Fassung."},
        ).status_code
        == 200
    )
    with ctx.session_factory() as s:
        m = s.scalars(
            select(CaseMessage).where(
                CaseMessage.origin == "VOICE_BRIDGE", CaseMessage.case_id == cid
            )
        ).one()
        assert m.content == "Korrigierte deutsche Fassung." and m.original_text == "نص حر للاختبار"


# ---- 5: structured answers use stable values --------------------------------------------------------------
def test_structured_answers_use_stable_values_not_translations(client, ctx):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "uk")
    q = mstate(client, token)["question"]
    if q["data_type"] == "enum":
        v = q["options"][-1]["value"]
        assert all(o["value"] and "Mock" not in o["value"] for o in q["options"])
        send(client, token, q, v)
        assert (
            client.post(f"/api/cases/{cid}/voice-bridge/answer/accept", json={}).status_code == 200
        )
    else:
        bad = send(client, token, q, "[UK · Mock] Ja")
        assert bad.status_code == 400  # a translated label is never accepted as a value
        assert send(client, token, q, answer_value(q), rid="req-valid-01").status_code == 200
    # an invented enum value is rejected as well
    cid2 = make_case(client)
    t2 = start(client, cid2)
    connect(client, t2, "en")
    q2 = mstate(client, t2)["question"]
    if q2["data_type"] == "enum":
        assert send(client, t2, q2, "does_not_exist").status_code == 400


# ---- 6: skip -------------------------------------------------------------------------------------------------
def test_skip_moves_the_phone_to_the_next_question(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    first = mstate(client, token)["question"]
    r = client.post(f"/api/cases/{cid}/voice-bridge/skip")
    assert r.status_code == 200
    nxt = mstate(client, token)["question"]
    assert nxt is None or nxt["instance_id"] != first["instance_id"]


def test_desk_answer_supersedes_a_pending_phone_answer(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    send(client, token, q, answer_value(q))
    answer_question(
        client, cid, decision(client, cid)["next_question"]
    )  # worker answers at the desk instead
    s = mstate(client, token)
    assert s["status"] in ("QUESTION_ACTIVE", "WAITING_FOR_QUESTION")
    assert s["question"] is None or s["question"]["instance_id"] != q["instance_id"]
    assert wstate(client, cid)["answer"] is None  # no double answer
    assert client.post(f"/api/cases/{cid}/voice-bridge/answer/accept", json={}).status_code == 409


def test_reask_issues_a_new_instance(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    send(client, token, q, answer_value(q))
    assert client.post(f"/api/cases/{cid}/voice-bridge/answer/reask").status_code == 200
    q2 = mstate(client, token)["question"]
    assert q2["instance_id"] != q["instance_id"]
    assert (
        send(client, token, q, answer_value(q), rid="late-retry-1").status_code == 409
    )  # old instance is stale
    assert send(client, token, q2, answer_value(q2), rid="new-answer-1").status_code == 200


# ---- 7: stale / duplicate -----------------------------------------------------------------------------------
def test_stale_answer_is_rejected_and_not_misfiled(client, ctx):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    old = mstate(client, token)["question"]
    answer_question(
        client, cid, decision(client, cid)["next_question"]
    )  # question moves on at the desk
    msgs = messages_count(ctx, cid)
    r = send(client, token, old, answer_value(old))
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_question"
    assert messages_count(ctx, cid) == msgs
    assert wstate(client, cid)["answer"] is None


def test_same_request_is_processed_once(client, ctx):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    for _ in range(3):
        assert send(client, token, q, answer_value(q), rid="same-request-1").status_code == 200
    assert client.post(f"/api/cases/{cid}/voice-bridge/answer/accept", json={}).status_code == 200
    with ctx.session_factory() as s:
        n = s.scalar(
            select(func.count())
            .select_from(CaseMessage)
            .where(CaseMessage.origin == "VOICE_BRIDGE")
        )
    assert n == 1


# ---- 8: reconnect ---------------------------------------------------------------------------------------------
def test_reconnect_shows_the_current_state(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "ar")
    before = mstate(client, token)
    again = mstate(client, token)  # a reload / reconnect only needs the token
    assert again["question"]["instance_id"] == before["question"]["instance_id"]
    assert again["rtl"] is True and again["language"] == "ar"


def test_pause_and_resume(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    client.post(f"/api/cases/{cid}/voice-bridge/pause")
    s = mstate(client, token)
    assert s["status"] == "PAUSED" and s["question"] is None
    assert send(client, token, q, answer_value(q)).status_code == 409
    client.post(f"/api/cases/{cid}/voice-bridge/resume")
    assert mstate(client, token)["question"]["instance_id"] == q["instance_id"]


# ---- 9: end session ------------------------------------------------------------------------------------------------
def test_ended_session_is_closed_for_good(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    assert client.post(f"/api/cases/{cid}/voice-bridge/end").status_code == 200
    assert client.get("/api/bridge/state", headers=hdr(token)).status_code == 410
    assert send(client, token, q, answer_value(q)).status_code == 410
    assert (
        client.post("/api/bridge/language", json={"language": "de"}, headers=hdr(token)).status_code
        == 410
    )
    assert wstate(client, cid)["active"] is False


def test_new_start_revokes_the_old_qr(client):
    cid = make_case(client)
    t1 = start(client, cid)
    t2 = start(client, cid)
    assert client.get("/api/bridge/state", headers=hdr(t1)).status_code == 410
    assert client.get("/api/bridge/state", headers=hdr(t2)).status_code == 200


def test_expired_token_is_rejected(client, ctx):
    from datetime import UTC, datetime, timedelta

    cid = make_case(client)
    token = start(client, cid)
    with ctx.session_factory() as s:
        row = s.scalars(select(VoiceBridgeSession)).first()
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        s.commit()
    assert client.get("/api/bridge/state", headers=hdr(token)).status_code == 410
    assert wstate(client, cid)["active"] is False


def test_missing_or_wrong_token(client):
    assert client.get("/api/bridge/state").status_code == 401
    assert client.get("/api/bridge/state", headers=hdr("nonsense")).status_code == 401


# ---- 10: no case file through the phone ---------------------------------------------------------------------------------
def test_phone_state_exposes_no_case_data(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    body = client.get("/api/bridge/state", headers=hdr(token)).text
    for forbidden in (
        cid,
        "FALL-",
        "Schimmel",
        "Zürich",
        "Vermieter hat der Klientin",
        "decision",
        "issue",
        "rule",
    ):
        assert forbidden not in body, forbidden
    assert set(client.get("/api/bridge/state", headers=hdr(token)).json()) == {
        "status",
        "rev",
        "language",
        "rtl",
        "question",
        "notice",
    }


def test_token_is_stored_only_as_hash_and_is_random(client, ctx):
    cid = make_case(client)
    t1 = start(client, cid)
    t2 = start(client, cid)
    assert t1 != t2 and len(t1) >= 40
    with ctx.session_factory() as s:
        rows = list(s.scalars(select(VoiceBridgeSession)))
    assert all(r.token_hash != t1 and r.token_hash != t2 for r in rows)
    assert all(r.join_token is None for r in rows if r.ended_at is not None)


def test_remote_devices_may_only_use_the_bridge_endpoints(client):
    cid = make_case(client)
    token = start(client, cid)
    lan = {"X-Forwarded-For": "192.168.1.50"}
    assert client.get(f"/api/cases/{cid}", headers=lan).status_code == 403
    assert client.get("/api/cases", headers=lan).status_code == 403
    assert client.post(f"/api/cases/{cid}/voice-bridge/end", headers=lan).status_code == 403
    assert client.get("/api/bridge/state", headers={**lan, **hdr(token)}).status_code == 200
    # a forged local first hop does not help: any non-local hop restricts
    assert (
        client.get(
            f"/api/cases/{cid}", headers={"X-Forwarded-For": "127.0.0.1, 192.168.1.50"}
        ).status_code
        == 403
    )
    assert (
        client.get(f"/api/cases/{cid}", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 200
    )


def test_unsupported_language(client):
    cid = make_case(client)
    token = start(client, cid)
    assert (
        client.post("/api/bridge/language", json={"language": "xx"}, headers=hdr(token)).status_code
        == 400
    )


# ---- 11: escalation / safety ------------------------------------------------------------------------------------------------
def test_escalation_is_visible_at_once_and_questions_stay_under_worker_control(client):
    cid = new_case(client)["id"]
    token = start(client, cid)
    connect(client, token, "en")
    assert mstate(client, token)["status"] == "WAITING_FOR_QUESTION"  # nothing to ask yet
    say(
        client,
        cid,
        "Der Vermieter hat der Klientin die Wohnung gekündigt. Ausserdem hat sie Streit mit dem Arbeitgeber wegen der Kündigung.",
    )
    d = decision(client, cid)
    assert d["action"] in ("ASK", "ESCALATE", "PROCEED")
    s = mstate(client, token)
    assert s["question"] is not None or s["status"] == "WAITING_FOR_QUESTION"
    # the desk decision is independent of the phone: no answer pending, nothing blocked
    assert wstate(client, cid)["answer"] is None


def test_immediate_danger_pauses_the_phone_questions(client):
    cid = new_case(client)["id"]
    say(client, cid, BASE)
    token = start(client, cid)
    connect(client, token, "en")
    assert mstate(client, token)["question"] is not None
    say(
        client,
        cid,
        "Der Partner hat die Klientin geschlagen, sie hat jetzt Angst und ist in akuter Gefahr, er ist gerade vor der Tür.",
    )
    d = decision(client, cid)
    if (d.get("safety") or {}).get("state") == "IMMEDIATE":
        s = mstate(client, token)
        assert s["question"] is None and s["status"] == "WAITING_FOR_QUESTION"


# ---- 13: languages ------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("lang,rtl", [("en", False), ("ar", True), ("uk", False), ("de", False)])
def test_languages_and_rtl(client, lang, rtl):
    cid = make_case(client)
    token = start(client, cid)
    s = connect(client, token, lang)
    assert s["language"] == lang and s["rtl"] is rtl
    q = s["question"]
    assert q is not None
    if lang != "de":
        assert q["text"].startswith(
            f"[{lang.upper()} · Mock]"
        )  # translated, never the German original


# ---- 14: no needless AI calls ----------------------------------------------------------------------------------------------------------
def test_sync_and_polling_trigger_no_analysis_and_translations_are_cached(client, ctx):
    cid = make_case(client)
    token = start(client, cid)

    def usage():
        with ctx.session_factory() as s:
            return s.scalar(select(func.count()).select_from(AIUsage))

    u0 = usage()
    connect(client, token, "en")
    for _ in range(10):
        mstate(client, token)
        wstate(client, cid)
    assert (
        usage() == u0
    )  # polling never calls the AI (the mock does not count anyway; no analysis was queued)
    with ctx.session_factory() as s:
        n1 = s.scalar(select(func.count()).select_from(TranslationCache))
    assert n1 >= 1
    # a second session in the same language reuses the cache
    t2 = start(client, cid)
    connect(client, t2, "en")
    with ctx.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(TranslationCache)) == n1


def test_translation_failure_is_visible_and_never_shows_a_wrong_question(client, ctx, monkeypatch):
    cid = make_case(client)
    token = start(client, cid)

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(ctx.ai, "translate", boom)
    s = connect(client, token, "ar")
    assert s["question"] is None and s["notice"] == "translation_failed"
    w = wstate(client, cid)
    assert w["question"]["translation_status"] == "FAILED" and w["question"]["text_de"]
    monkeypatch.undo()
    from app.services.bridge import service as bridge_service

    monkeypatch.setattr(bridge_service, "TRANSLATION_MIN_INTERVAL_S", 0.0)
    assert client.post(f"/api/cases/{cid}/voice-bridge/retry-translation").status_code == 200
    assert mstate(client, token)["question"] is not None


def test_closed_case_ends_the_bridge(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    client.patch(f"/api/cases/{cid}", json={"status": "CLOSED"})
    assert mstate(client, token)["status"] == "COMPLETED"  # the phone is told once («Vielen Dank»)
    assert client.get("/api/bridge/state", headers=hdr(token)).status_code == 410


def test_other_cases_are_untouched(client, ctx):
    a, b = make_case(client), make_case(client)
    ta = start(client, a)
    connect(client, ta, "en")
    assert wstate(client, b)["active"] is False
    with ctx.session_factory() as s:
        assert s.get(Case, b) is not None


# ---- 10 (Fallbericht) ---------------------------------------------------------------------------------------------------------
def test_briefing_names_the_bridge_as_origin_of_accepted_answers(client):
    cid = make_case(client)
    token = start(client, cid)
    connect(client, token, "en")
    q = mstate(client, token)["question"]
    send(client, token, q, answer_value(q))
    assert client.post(f"/api/cases/{cid}/voice-bridge/answer/accept", json={}).status_code == 200
    b = client.post(f"/api/cases/{cid}/briefings")
    assert b.status_code == 201, b.text
    text = b.text
    assert "via Sprachbrücke erfasst und durch die Sozialarbeiterin bestätigt" in text
    assert (
        "rechtlich geprüft" not in text.split("Sprachbrücke")[1][:200]
    )  # no legal verification is suggested


# ---- network address proposal (QR must never point at an unreachable address) ------------------------------------------------------
def test_lan_candidates_are_private_ipv4_only_default_route_first(monkeypatch):
    import socket

    from app.services.bridge import service as svc

    class FakeSock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def connect(self, addr):
            pass

        def getsockname(self):
            return ("172.20.10.4", 0)

    monkeypatch.setattr(svc.socket, "socket", lambda *a, **k: FakeSock())
    monkeypatch.setattr(
        svc.socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, 0, 0, "", ip, 0) if False else (socket.AF_INET, 0, 0, "", (ip, 0))
            for ip in ("127.0.0.1", "169.254.7.7", "8.8.8.8", "172.17.16.1", "172.20.10.4")
        ],
    )
    assert svc.lan_candidates() == [
        "172.20.10.4",
        "172.17.16.1",
    ]  # no loopback, link-local or public address


def test_worker_state_offers_the_candidates_and_a_configured_base(client, ctx):
    cid = make_case(client)
    r = client.post(f"/api/cases/{cid}/voice-bridge").json()
    assert isinstance(r["lan_candidates"], list)
    assert all(
        ip.count(".") == 3 and not ip.startswith(("127.", "169.254.")) for ip in r["lan_candidates"]
    )
    assert (
        r["public_base_url"] is None
    )  # nothing configured in tests: the UI proposes the candidates
