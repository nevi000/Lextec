from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import new_case, say

EXAMPLE = (
    "Mein Arbeitgeber hat mir gekündigt. Jetzt kann ich meine Miete nicht mehr bezahlen "
    "und habe Angst, meine Wohnung zu verlieren."
)


def decision(client, case_id):
    return client.get(f"/api/cases/{case_id}/current-decision").json()


def test_health_and_status(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    st = client.get("/api/system/status").json()
    assert st["ai_provider"] == "mock" and st["ai_is_external"] is False
    assert st["knowledge_base_valid"] is True


def test_full_ask_flow_with_facts_decisions_and_briefing(client):
    case = new_case(client)
    assert case["display_id"] == "FALL-0001"
    assert decision(client, case["id"])["main_reason_code"] == "NO_INPUT"

    r = say(client, case["id"], "Mein Arbeitgeber hat mir gekündigt.")
    d = r["case"]["current_decision"]
    assert (
        d["action"] == "ASK"
        and d["next_question"]["fact_id"] == "employer_termination_received_date"
    )
    assert r["case"]["title"] == "Arbeitskündigung"
    assert r["message"]["analysis_status"] == "DONE"

    facts = {f["fact_id"]: f for f in client.get(f"/api/cases/{case['id']}/facts").json()}
    f = facts["employer_termination_received"]
    assert f["status"] == "KNOWN" and f["value"] is True
    assert f["origin"] == "AI_EXTRACTED" and f["evidence_quote"] == "Arbeitgeber hat mir gekündigt"
    assert f["source_message_id"] == r["message"]["id"]
    assert facts["employment_start_date"]["status"] == "MISSING"

    r2 = say(
        client, case["id"], "Am 15.01.2026 erhalten.", answers="employer_termination_received_date"
    )
    f2 = {x["fact_id"]: x for x in client.get(f"/api/cases/{case['id']}/facts").json()}
    assert f2["employer_termination_received_date"]["value"] == "2026-01-15"
    assert f2["employer_termination_received_date"]["origin"] == "USER_ANSWER"
    assert r2["case"]["current_decision"]["next_question"]["fact_id"] == "deadline_pending"

    # history has one row per distinct outcome
    hist = client.get(f"/api/cases/{case['id']}/decisions").json()
    assert len(hist) >= 2 and hist[0]["decision"]["knowledge_base_version"].startswith("kb-")

    # answer everything -> PROCEED
    for fid, text in [
        ("deadline_pending", "Nein"),
        ("employer_termination_in_writing", "Ja, schriftlich"),
        ("employment_start_date", "01.03.2020"),
        ("incapacity_for_work", "Nein"),
    ]:
        say(client, case["id"], text, answers=fid)
    detail = client.get(f"/api/cases/{case['id']}").json()
    assert detail["current_decision"]["action"] == "PROCEED"
    assert detail["briefing_stale"] is True

    b = client.post(f"/api/cases/{case['id']}/briefings")
    assert b.status_code == 201
    brief = b.json()["briefing"]
    assert brief["decision"]["action"] == "PROCEED"
    assert any(x["fact_id"] == "employer_termination_received" for x in brief["known_facts"])
    prov = {x["fact_id"]: x["provenance"] for x in brief["known_facts"]}
    assert prov["employer_termination_received"] == "REPORTED_BY_AI_EXTRACTION"
    assert prov["employment_start_date"] == "ANSWER_RECORDED"
    shown = {x["fact_id"]: x["value_display"] for x in brief["known_facts"]}
    assert shown["employment_start_date"] == "01.03.2020"  # Swiss date format, not ISO
    assert shown["employer_termination_received"] == "Ja"
    assert brief["legal_sources"] and all(
        s["source"]["verification_status"] == "UNVERIFIED" for s in brief["legal_sources"]
    )
    assert (
        brief["knowledge_base_notice"]
        and "nicht juristisch freigegeben" in brief["knowledge_base_notice"]
    )
    assert len(brief["section_order"]) == 11

    # versions
    b2 = client.post(f"/api/cases/{case['id']}/briefings").json()
    assert b2["version"] == 2
    lst = client.get(f"/api/cases/{case['id']}/briefings").json()
    assert [x["version"] for x in lst] == [2, 1]
    assert client.get(f"/api/cases/{case['id']}/briefings/{b2['id']}").json()["version"] == 2
    assert client.get(f"/api/cases/{case['id']}").json()["briefing_stale"] is False


def test_escalation_example_with_multiple_issues_and_handover_states(client):
    case = new_case(client)
    r = say(client, case["id"], EXAMPLE)
    d = r["case"]["current_decision"]
    # the weak mention of rent/housing is a low-confidence match for Issue 1 (< 0.5 would escalate; 0.6 asks)
    assert set(d["active_issue_ids"]) == {"employment_termination", "CH_TENANCY_TERMINATION"}
    say(client, case["id"], "Die Klientin hat auch Härtegründe: alleinerziehend mit zwei Kindern.")
    d = client.get(f"/api/cases/{case['id']}/current-decision").json()
    assert d["action"] == "ESCALATE"
    assert "TT_HARDSHIP" in d["triggered_rule_ids"]
    assert "social_counselling" in d["recommended_professionals"]
    assert d["missing_facts"], "missing facts remain visible on escalation"
    assert [r["issue_id"] for r in d["related_routes"]] == ["CH_TENANCY_EXTENSION"]
    assert d["related_routes"][0]["available"] is False
    assert client.get(f"/api/cases/{case['id']}").json()["handover"]["status"] == "RECOMMENDED"

    # cannot be completed without being requested first
    bad = client.post(
        f"/api/cases/{case['id']}/handover/complete", json={"note": "telefonisch erfolgt"}
    )
    assert bad.status_code == 409
    ok = client.post(f"/api/cases/{case['id']}/handover/request")
    assert ok.json()["handover"]["status"] == "HANDOFF_REQUESTED"
    done = client.post(
        f"/api/cases/{case['id']}/handover/complete", json={"note": "Zusage per Mail"}
    )
    assert done.json()["handover"]["status"] == "HANDOFF_COMPLETED"
    assert client.post(
        f"/api/cases/{case['id']}/handover/complete", json={"note": "x"}
    ).status_code in (409, 422)

    brief = client.post(f"/api/cases/{case['id']}/briefings").json()["briefing"]
    assert brief["handover"]["status"] == "HANDOFF_COMPLETED"
    assert brief["escalation_reasons"]


def test_unsupported_area_escalates(client):
    case = new_case(client)
    r = say(client, case["id"], "Ich brauche Hilfe bei meiner Scheidung.")
    d = r["case"]["current_decision"]
    assert d["action"] == "ESCALATE" and "UNSUPPORTED_LEGAL_AREA" in d["reason_codes"]
    assert any(i["classification_status"] == "UNSUPPORTED" for i in r["case"]["issues"])


def test_human_correction_is_not_overwritten_by_later_ai_output(client):
    case = new_case(client)
    cid = case["id"]
    say(client, cid, "Mein Arbeitgeber hat mir gekündigt.")
    url = f"/api/cases/{cid}/facts/employer_termination_received"
    r = client.patch(url, json={"value": False, "note": "Fehler der KI"})
    assert r.status_code == 200
    fact = {f["fact_id"]: f for f in r.json()}["employer_termination_received"]
    assert fact["value"] is False and fact["origin"] == "USER_CORRECTION" and fact["confirmed"]

    say(client, cid, "Mein Arbeitgeber hat mir gekündigt, wie gesagt.")
    fact = {f["fact_id"]: f for f in client.get(f"/api/cases/{cid}/facts").json()}[
        "employer_termination_received"
    ]
    assert fact["value"] is False, "confirmed human value must survive new AI extraction"
    assert fact["status"] == "KNOWN"
    assert any(h["event"] == "ai_conflict_suppressed" for h in fact["history"])
    assert [h["event"] for h in fact["history"]][:2] == ["extracted", "corrected"]


def test_ai_contradiction_marks_fact_contradictory_then_answer_resolves(client):
    case = new_case(client)
    cid = case["id"]
    say(client, cid, "Ich hatte Schimmel gemeldet, der Vermieter ist informiert.")
    say(client, cid, "Der Vermieter ist noch nicht informiert worden.")
    facts = {f["fact_id"]: f for f in client.get(f"/api/cases/{cid}/facts").json()}
    f = facts["landlord_informed"]
    assert f["status"] == "CONTRADICTORY" and f["value"] is True and f["conflicting_values"]
    d = decision(client, cid)
    assert "CONTRADICTORY_FACTS" in d["reason_codes"]
    say(client, cid, "Nein, nicht informiert.", answers="landlord_informed")
    f = {x["fact_id"]: x for x in client.get(f"/api/cases/{cid}/facts").json()}["landlord_informed"]
    assert f["status"] == "KNOWN" and f["value"] is False and f["conflicting_values"] == []


def test_ambiguous_answer_is_not_treated_as_known(client):
    case = new_case(client)
    cid = case["id"]
    say(client, cid, "Mein Arbeitgeber hat mir gekündigt.")
    say(
        client, cid, "Irgendwann im Januar vielleicht", answers="employer_termination_received_date"
    )
    f = {x["fact_id"]: x for x in client.get(f"/api/cases/{cid}/facts").json()}[
        "employer_termination_received_date"
    ]
    assert f["status"] == "AMBIGUOUS" and f["value"] is None
    assert decision(client, cid)["next_question"]["fact_id"] == "employer_termination_received_date"
    # asked twice and still unclear -> no endless loop: treated as unknown and NOT asked again
    say(
        client,
        cid,
        "Eher im Januar, genau sagt man das nie",
        answers="employer_termination_received_date",
    )
    f = {x["fact_id"]: x for x in client.get(f"/api/cases/{cid}/facts").json()}[
        "employer_termination_received_date"
    ]
    assert f["status"] == "UNKNOWN"
    assert any(h["event"] == "ambiguity_exhausted" for h in f["history"])
    assert decision(client, cid)["next_question"]["fact_id"] != "employer_termination_received_date"


def test_defer_requires_reason_and_does_not_mark_known(client):
    case = new_case(client)
    cid = case["id"]
    say(client, cid, "Mein Arbeitgeber hat mir gekündigt.")
    url = f"/api/cases/{cid}/facts/employer_termination_received_date/defer"
    assert client.post(url, json={"reason": ""}).status_code == 422
    r = client.post(url, json={"reason": "Person hat Unterlagen nicht dabei"})
    assert r.status_code == 200
    f = {x["fact_id"]: x for x in r.json()}["employer_termination_received_date"]
    assert f["status"] == "MISSING" and f["deferred_reason"]
    assert decision(client, cid)["next_question"]["fact_id"] != "employer_termination_received_date"
    assert (
        client.post(
            f"/api/cases/{cid}/facts/employer_termination_received_date/undefer"
        ).status_code
        == 200
    )


def test_fact_patch_validation(client):
    case = new_case(client)
    cid = case["id"]
    say(client, cid, "Mein Arbeitgeber hat mir gekündigt.")
    bad = client.patch(f"/api/cases/{cid}/facts/employment_start_date", json={"value": "gestern"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_value"
    assert client.patch(f"/api/cases/{cid}/facts/nope", json={"value": 1}).status_code == 404
    assert client.patch(f"/api/cases/{cid}/facts/employment_start_date", json={}).status_code == 400


def test_validation_and_not_found_use_error_format(client):
    r = client.post("/api/cases/unknown/messages", json={"content": "x"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    case = new_case(client)
    r = client.post(f"/api/cases/{case['id']}/messages", json={"content": ""})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = client.post(
        f"/api/cases/{case['id']}/messages", json={"content": "x", "answers_fact_id": "bogus"}
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "unknown_fact"


def test_list_search_filter_dashboard(client):
    a = new_case(client)
    b = new_case(client, "Meine Akte")
    say(client, a["id"], "Mein Arbeitgeber hat mir gekündigt.")
    say(client, b["id"], "Ich brauche Hilfe bei meiner Scheidung.")
    assert len(client.get("/api/cases").json()) == 2
    assert [c["display_id"] for c in client.get("/api/cases?q=FALL-0002").json()] == ["FALL-0002"]
    assert len(client.get("/api/cases?action=ESCALATE").json()) == 1
    assert len(client.get("/api/cases?action=ASK").json()) == 1
    assert client.get("/api/cases?status=CLOSED").json() == []
    d = client.get("/api/dashboard").json()
    assert (d["total_cases"], d["open_cases"], d["needs_clarification"], d["escalated"]) == (
        2,
        2,
        1,
        1,
    )
    assert d["awaiting_professional_review"] == 1 and len(d["recent"]) == 2
    client.patch(f"/api/cases/{a['id']}", json={"status": "CLOSED"})
    assert client.get("/api/dashboard").json()["open_cases"] == 1
    closed = client.post(f"/api/cases/{a['id']}/messages", json={"content": "noch etwas"})
    assert closed.status_code == 409


def test_cases_survive_restart(settings):
    with TestClient(create_app(settings)) as c1:
        case = new_case(c1)
        say(c1, case["id"], "Mein Arbeitgeber hat mir gekündigt.")
        c1.post(f"/api/cases/{case['id']}/briefings")
    with TestClient(create_app(settings)) as c2:
        got = c2.get(f"/api/cases/{case['id']}").json()
        assert got["display_id"] == "FALL-0001" and got["current_decision"]["action"] == "ASK"
        assert len(c2.get(f"/api/cases/{case['id']}/messages").json()) == 1
        assert len(c2.get(f"/api/cases/{case['id']}/briefings").json()) == 1
        assert new_case(c2)["display_id"] == "FALL-0002"


def test_evaluation_and_kb_endpoints(client):
    st = client.get("/api/knowledge-base/status").json()
    assert (
        st["valid"]
        and st["issue_count"] == 4
        and st["unverified_source_count"] == st["source_count"]
    )
    assert len(client.get("/api/knowledge-base/issues").json()) == 4
    run = client.post("/api/evaluation/run").json()
    assert run["failed"] == 0 and run["legally_validated_total"] == 0 and run["total"] >= 10
    assert len(client.get("/api/evaluation/scenarios").json()) == run["total"]
    assert client.post("/api/knowledge-base/reload").json()["valid"]
