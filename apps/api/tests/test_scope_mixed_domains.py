"""Produkt-Scope: sieben Schweizer Mietrechts-Issues. Synthetische Demo-Issues nie für neue Fälle; Arbeits- und
Ausländerrecht nicht abgedeckt; gemischte Fälle werden geteilt. Mock-KI, keine echten Gemini-Aufrufe."""

from __future__ import annotations

import pytest

from tests.conftest import new_case, say

SEVEN = {
    "CH_TENANCY_TERMINATION",
    "CH_TENANCY_PAYMENT_WARNING",
    "CH_TENANCY_PAYMENT_DEFAULT",
    "CH_TENANCY_EXTENSION",
    "CH_TENANCY_DEFECTS",
    "CH_TENANCY_EVICTION",
    "CH_TENANCY_RENT_INCREASE",
}
T_EMPLOYMENT = "Mein Arbeitgeber hat mich gestern entlassen. Ist die Kündigung gültig?"
T_WAGES = "Meine Arbeitgeberin hat mir seit zwei Monaten keinen Lohn ausbezahlt."
T_CONTEXT = "Meine Klientin hat ihren Job verloren und kann die nächste Miete möglicherweise nicht bezahlen."
T_MIXED = (
    "Mein Arbeitgeber hat mir gekündigt und meinen Lohn nicht bezahlt. Deshalb konnte ich die Miete nicht bezahlen. "
    "Der Vermieter hat mir eine Mahnung mit Kündigungsandrohung geschickt."
)
T_EVICTION = "Mein Vermieter hat beim Gericht die Ausweisung aus meiner Wohnung beantragt."
T_IMMIGRATION = "Die Migrationsbehörde hat eine Wegweisungsverfügung erlassen. Mein Klient soll die Schweiz verlassen."


def run(client, text):
    cid = new_case(client)["id"]
    say(client, cid, text)
    d = client.get(f"/api/cases/{cid}/current-decision").json()
    detail = client.get(f"/api/cases/{cid}").json()
    return cid, d, detail


def labels(detail):
    return [
        i["description"] for i in detail["issues"] if i["classification_status"] == "UNSUPPORTED"
    ]


def test_t1_t2_plain_termination_and_rent_increase(client):
    _, d, detail = run(
        client, "Meine Klientin hat gestern eine Kündigung ihrer Wohnung vom Vermieter erhalten."
    )
    assert d["active_issue_ids"] == ["CH_TENANCY_TERMINATION"] and not labels(detail)
    _, d, detail = run(client, "Meine Klientin hat eine Erhöhung ihres Mietzinses erhalten.")
    assert d["active_issue_ids"] == ["CH_TENANCY_RENT_INCREASE"] and not labels(detail)


@pytest.mark.parametrize("text", [T_EMPLOYMENT, T_WAGES])
def test_t4_t5_employment_law_is_not_covered_and_uses_no_synthetic_rules(client, text):
    _, d, detail = run(client, text)
    assert labels(detail) == ["Arbeitsrecht"]
    assert d["active_issue_ids"] == [] and d["action"] == "ESCALATE"
    assert "lawyer_general" in d["recommended_professionals"]
    assert not [
        r for r in d["triggered_rule_ids"] if r.startswith(("EMP_", "SAL_", "DEF_DEMO", "DEMO_"))
    ]
    assert d["approved_statements"] == []  # no legal statements from synthetic content


def test_t6_job_loss_as_mere_context_is_not_an_employment_case(client):
    _, d, detail = run(client, T_CONTEXT)
    assert "Arbeitsrecht" not in labels(detail)
    assert not [
        i
        for i in detail["issues"]
        if i["issue_definition_id"] in ("employment_termination", "unpaid_salary")
    ]
    assert d["action"] in (
        "ASK",
        "ESCALATE",
    )  # nothing invented; human check where no tenancy question is recognised


def test_t7_mixed_case_processes_tenancy_and_flags_employment_separately(client):
    _, d, detail = run(client, T_MIXED)
    assert "CH_TENANCY_PAYMENT_WARNING" in d["active_issue_ids"]
    assert labels(detail) == ["Arbeitsrecht"]
    assert d["action"] == "ESCALATE" and "UNSUPPORTED_LEGAL_AREA" in d["reason_codes"]
    assert "GLOBAL_UNSUPPORTED_ISSUE" in d["triggered_rule_ids"]
    assert d["max_urgency"] == "HIGH"  # the tenancy rules keep the highest urgency
    assert (
        d["intake"]["important_open"] >= 1 and d["next_question"]["fact_id"]
    )  # tenancy intake continues
    assert not {"employment_termination", "unpaid_salary"} & set(d["active_issue_ids"])


def test_t8_tenancy_eviction_is_issue_6_without_immigration_label(client):
    _, d, detail = run(client, T_EVICTION)
    assert "CH_TENANCY_EVICTION" in d["active_issue_ids"] and not labels(detail)
    assert d["action"] == "ESCALATE" and d["max_urgency"] == "HIGH"
    for t in (
        "Mein Vermieter will mich aus der Wohnung ausweisen.",
        "Die Klientin hat einen gerichtlichen Ausweisungsentscheid erhalten.",
        "Der Vermieter hat die Räumung beantragt.",
        "Die Polizei soll morgen die Wohnung räumen.",
    ):
        _, d2, det2 = run(client, t)
        assert "CH_TENANCY_EVICTION" in d2["active_issue_ids"], t
        assert "Ausländerrecht" not in labels(det2), t


def test_t9_immigration_removal_is_not_covered_and_not_issue_6(client):
    _, d, detail = run(client, T_IMMIGRATION)
    assert labels(detail) == ["Ausländerrecht"] and d["active_issue_ids"] == []


def test_t10_historical_demo_cases_stay_readable_but_new_input_gets_no_demo_issue(client, ctx):
    """A case stored with a demo issue (created long ago) keeps loading; new input is never classified with demo content."""
    from app.domain.enums import IssueStatus
    from app.models.tables import CaseIssue

    cid = new_case(client)["id"]
    with ctx.session_factory() as s:
        for iid in ("employment_termination", "unpaid_salary"):
            s.add(
                CaseIssue(
                    case_id=cid,
                    issue_definition_id=iid,
                    classification_status=IssueStatus.DETECTED.value,
                    confidence=0.9,
                    evidence="alt",
                )
            )
        s.commit()
    detail = client.get(f"/api/cases/{cid}").json()
    assert {"employment_termination", "unpaid_salary"} <= {
        i["issue_definition_id"] for i in detail["issues"]
    }
    assert client.get(f"/api/cases/{cid}/current-decision").status_code == 200
    assert client.get(f"/api/cases/{cid}/facts").status_code == 200
    assert client.post(f"/api/cases/{cid}/briefings").status_code in (
        201,
        409,
    )  # still renders / or honest conflict
    r = client.post(
        f"/api/cases/{cid}/messages",
        json={"content": "Der Vermieter hat der Klientin die Wohnung gekündigt."},
    )
    assert r.status_code == 201
    ids = {i["issue_definition_id"] for i in client.get(f"/api/cases/{cid}").json()["issues"]}
    assert "CH_TENANCY_TERMINATION" in ids  # new input is classified with the real issues


def test_t11_catalog_has_no_demo_issue_and_all_seven_real_ones(ctx):
    cat = ctx.kb.catalog_issues()
    assert all(d.content_status != "DEMO_SYNTHETIC" for d in cat)
    assert {d.id for d in cat} == SEVEN
    synthetic = {i for i, d in ctx.kb.issues.items() if d.content_status == "DEMO_SYNTHETIC"}
    assert synthetic == {
        "employment_termination",
        "unpaid_salary",
        "tenancy_defects",
    }  # all demo-only, none offered
    assert not synthetic & {d.id for d in cat}


def test_t12_briefing_of_a_mixed_case_separates_supported_and_unsupported(client):
    cid, _, _ = run(client, T_MIXED)
    b = client.post(f"/api/cases/{cid}/briefings")
    assert b.status_code == 201
    html = client.get(f"/api/cases/{cid}/briefings/{b.json()['id']}/preview").text
    assert "Zahlungsaufforderung mit Kündigungsandrohung" in html
    assert "Arbeitsrecht" in html and "nicht abgedeckt" in html
    for synthetic in ("Kündigung durch Arbeitgeber erhalten", "Arbeitskündigung"):
        assert synthetic not in html
    assert "Ausländerrecht" not in html
    cid2, _, _ = run(client, T_EVICTION)
    b2 = client.post(f"/api/cases/{cid2}/briefings").json()
    html2 = client.get(f"/api/cases/{cid2}/briefings/{b2['id']}/preview").text
    assert "Ausländerrecht" not in html2
