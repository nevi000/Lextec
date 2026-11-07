"""ESCALATE beendet die Fallaufnahme nicht: Frageauswahl, Intake-Zustand, Bericht, Kosten. Nur Mock-KI."""

from __future__ import annotations

from tests.conftest import new_case, say

TERMINATION = "Mein Vermieter hat der Klientin die Wohnung gekündigt, ohne amtliches Formular, in der Stadt Zürich."


def answer(client, cid, q):
    """Answer the open question with a plausible value for its data type (structured answer, handled locally)."""
    dt = q["data_type"]
    if dt == "enum":
        ev = q["enum_values"][0]
        text = q["enum_labels_de"].get(ev, ev)
    elif dt == "boolean":
        text = "nein"
    elif dt == "date":
        text = "2026-11-02"
    elif dt == "integer":
        text = "1500"
    else:
        text = "Zürich"
    return say(client, cid, text, answers=q["fact_id"])


def decision(client, cid):
    return client.get(f"/api/cases/{cid}/current-decision").json()


def test_a_escalation_keeps_important_questions_open_and_answerable(client):
    cid = new_case(client)["id"]
    say(client, cid, TERMINATION)
    d = decision(client, cid)
    assert d["action"] == "ESCALATE" and "TT_FORM_MISSING" in d["triggered_rule_ids"]
    assert d["intake"]["important_open"] >= 3 and not d["intake"]["complete"]
    q = d["next_question"]
    assert q and q["fact_id"] and not q["optional"]  # eine wichtige Frage, nicht optional
    before = d["intake"]["important_open"]
    answer(client, cid, q)
    d2 = decision(client, cid)
    assert (
        d2["action"] == "ESCALATE" and "TT_FORM_MISSING" in d2["triggered_rule_ids"]
    )  # Entscheid bleibt
    assert d2["intake"]["important_open"] < before
    assert d2["next_question"]["fact_id"] != q["fact_id"]


def test_b_report_can_be_created_immediately_and_lists_open_items(client):
    cid = new_case(client)["id"]
    say(client, cid, TERMINATION)
    assert decision(client, cid)["intake"]["important_open"] >= 3
    r = client.post(f"/api/cases/{cid}/briefings")
    assert r.status_code in (200, 201)  # kein Vollständigkeitszwang
    html = client.get(f"/api/cases/{cid}/briefings/{r.json()['id']}/preview").text
    assert "Offen" in html or "offen" in html


def test_c_answer_after_escalation_updates_state_and_new_report_version(client):
    cid = new_case(client)["id"]
    say(client, cid, TERMINATION)
    b1 = client.post(f"/api/cases/{cid}/briefings").json()
    q = decision(client, cid)["next_question"]
    answer(client, cid, q)
    assert (
        client.get(f"/api/cases/{cid}").json()["briefing_stale"] is True
    )  # Bericht veraltet erkennbar
    b2 = client.post(f"/api/cases/{cid}/briefings").json()
    assert b2["version"] == b1["version"] + 1  # Versionierung bleibt
    facts = {f["fact_id"]: f for f in client.get(f"/api/cases/{cid}/facts").json()}
    assert facts[q["fact_id"]]["status"] == "KNOWN"


def test_d_unknown_answer_is_documented_and_never_asked_again(client):
    cid = new_case(client)["id"]
    say(client, cid, TERMINATION)
    q = decision(client, cid)["next_question"]
    say(client, cid, "Weiss ich nicht.", answers=q["fact_id"])
    d = decision(client, cid)
    assert d["intake"]["unknown"] >= 1
    assert q["fact_id"] not in [m["fact_id"] for m in d["missing_facts"]]
    assert d["next_question"]["fact_id"] != q["fact_id"]


def test_e_not_applicable_conditional_question_disappears(client):
    cid = new_case(client)["id"]
    say(client, cid, TERMINATION)
    ids = [m["fact_id"] for m in decision(client, cid)["missing_facts"]]
    assert "spouse_still_lives_there" not in ids  # nur bei Familienwohnung
    say(client, cid, "nein", answers="family_home_with_spouse")
    ids = [m["fact_id"] for m in decision(client, cid)["missing_facts"]]
    assert "spouse_still_lives_there" not in ids and "separate_delivery_to_spouse" not in ids


def test_f_multiple_issues_share_one_deduplicated_question_list(client):
    cid = new_case(client)["id"]
    say(
        client,
        cid,
        "Der Vermieter hat gekündigt. Die Klientin hat Schimmel im Schlafzimmer und die Miete gekürzt.",
    )
    d = decision(client, cid)
    ids = [m["fact_id"] for m in d["missing_facts"]]
    assert len(ids) == len(set(ids)) and len(d["active_issue_ids"]) >= 2
    assert d["next_question"]["fact_id"] in ids  # genau eine gemeinsame Auswahl


def test_g_eviction_escalates_immediately_and_intake_continues_afterwards(client):
    cid = new_case(client)["id"]
    say(client, cid, "Das Stadtammannamt kommt morgen zur Räumung.")
    d = decision(client, cid)
    assert d["action"] == "ESCALATE" and d["max_urgency"] == "HIGH"
    assert d["main_reason_code"] and "EV_GRUNDREGEL" in d["triggered_rule_ids"]
    assert d["intake"]["important_open"] >= 1  # Ergänzung weiterhin möglich, ohne Vorab-Rückfrage
    assert d["recommended_professionals"][0] == "social_counselling"


def test_h_acute_danger_overrides_the_normal_question_flow(client):
    cid = new_case(client)["id"]
    say(
        client,
        cid,
        "Der Vermieter hat gekündigt und droht, meine Klientin zu schlagen. Sie wird gerade bedroht.",
    )
    d = decision(client, cid)
    assert (
        d["effective_action"] == "IMMEDIATE_SAFETY_RESPONSE" and d["safety"]["state"] == "IMMEDIATE"
    )


def test_i_facts_added_after_escalation_appear_in_the_new_briefing(client):
    cid = new_case(client)["id"]
    say(client, cid, TERMINATION)
    say(client, cid, "Normale Post.", answers="delivery_method")
    b = client.post(f"/api/cases/{cid}/briefings").json()
    html = client.get(f"/api/cases/{cid}/briefings/{b['id']}/preview").text
    assert "Normale Post" in html


def test_j_navigating_and_reading_never_calls_the_ai(client, ctx, monkeypatch):
    cid = new_case(client)["id"]
    say(client, cid, TERMINATION)
    calls = []
    monkeypatch.setattr(ctx.ai, "extract", lambda *a, **k: calls.append("extract"))
    monkeypatch.setattr(ctx.ai, "rephrase_question", lambda *a, **k: calls.append("rephrase"))
    for _ in range(3):
        decision(client, cid)
        client.get(f"/api/cases/{cid}")
        client.get(f"/api/cases/{cid}/facts")
    q = decision(client, cid)["next_question"]
    answer(client, cid, q)  # strukturierte Antwort: lokal, kein KI-Aufruf
    assert calls == []


def test_handover_priority_orders_questions_only_after_escalation(client, ctx):
    from app.domain.enums import Action, IssueStatus
    from app.domain.state import CaseSnapshot, IssueState
    from app.services.decisions.engine import decide

    snap = CaseSnapshot(
        has_user_input=True,
        issues=[IssueState(IssueStatus.DETECTED, "CH_TENANCY_TERMINATION", 0.9)],
    )
    d = decide(ctx.kb, snap)
    assert d.action in (Action.ASK, Action.ESCALATE)
    if d.action == Action.ESCALATE:
        pr = [m.handover_priority for m in d.missing_facts]
        assert pr == sorted(pr, key=lambda p: 0 if p == "high" else 1)
