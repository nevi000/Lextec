"""Fallbericht und Fallaufnahme stimmen überein: relevante Angaben, keine «Fehlt»-Kataloge, kompakte Quellen. Mock-KI."""

from __future__ import annotations

import re

import pymupdf

from tests.conftest import new_case, say

FALL14 = (
    "Meine Klientin hat in Zürich eine Wohnungskündigung erhalten. Sie ist alleinige Mieterin. "
    "Die Kündigung wurde ihr am 4. November 2026 mit normaler Post zugestellt. "
    "Laut ihrer Aussage wurde kein amtliches Kündigungsformular verwendet."
)


def report(client, cid):
    b = client.post(f"/api/cases/{cid}/briefings").json()
    html = client.get(f"/api/cases/{cid}/briefings/{b['id']}/preview").text
    return b, re.sub(r"\s+", " ", re.sub(r"<style.*?</style>|<[^>]+>", " ", html, flags=re.S))


def fall14(client):
    cid = new_case(client)["id"]
    say(client, cid, FALL14)
    say(client, cid, "Nein", answers="family_home_with_spouse")
    say(client, cid, "Ordentliche Kündigung", answers="termination_kind")
    say(client, cid, "Ja", answers="already_reacted")
    return cid


def test_regression_fall_0014_known_open_and_not_applicable(client):
    cid = fall14(client)
    _, t = report(client, cid)
    # known facts taken over, with their origin
    assert "Normale Post" in t and "04.11.2026" in t and "Zürich" in t
    assert "Ordentliche Kündigung" in t
    # important open facts are stated plainly
    assert (
        "Wichtige Angaben, die noch fehlen" in t
        and "Aufhebungsvereinbarung" in t
        and "Vertragsart" in t
    )
    # «ja» without details is NOT turned into a more specific fact
    assert "Art der Reaktion" in t and "nicht näher bestimmt" in t
    for invented in ("angefochten: Ja", "unterschrieben: Ja"):
        assert invented not in t
    # not applicable (no family home) and optional/unasked fields do not show up as a list of «Fehlt»
    assert "separat an die Partnerperson" not in t.lower()
    assert t.count("Fehlt") <= 2
    # no invented personal data, no catalogue of missing personal fields
    assert "Geburtsdatum" not in t and "Referenzzinssatz bei Vertragsabschluss" not in t
    assert "Name nicht erfasst" not in t
    # urgency comes from the rule engine
    assert "Bald bearbeiten" in t and "TT_FORM_MISSING" in t


def test_pdf_is_much_more_compact_than_the_nine_page_reference(client):
    cid = fall14(client)
    b = client.post(f"/api/cases/{cid}/briefings").json()
    r = client.get(f"/api/cases/{cid}/briefings/{b['id']}/pdf")
    assert r.status_code == 200
    doc = pymupdf.open(stream=r.content, filetype="pdf")
    assert 3 <= len(doc) <= 6  # reference had 9 pages for the same four inputs
    first_two = " ".join(doc[i].get_text() for i in range(2))
    for must in (
        "Kurzsachverhalt",
        "Dringlichkeit",
        "Fachperson nötig",
        "Wichtige Angaben, die noch fehlen",
        "Prozess",
    ):
        assert (
            must in first_two
        )  # what / known / unclear / urgent / why / next step on the first two pages
    full = " ".join(p.get_text() for p in doc)
    assert (
        full.count("Zurück") < 20 and "Art. 271a Abs. 1 1 Die Kündigung" not in full
    )  # no 15-article wording dump


def test_a_only_first_description_shows_known_and_required_open(client):
    cid = new_case(client)["id"]
    say(client, cid, FALL14)
    _, t = report(client, cid)
    assert "Normale Post" in t and "Wichtige Angaben, die noch fehlen" in t


def test_b_all_required_answered_no_false_missing_messages(client, ctx):
    cid = new_case(client)["id"]
    say(client, cid, FALL14)
    for _ in range(40):  # answer whatever the system still asks (structured, local, no AI)
        q = client.get(f"/api/cases/{cid}/current-decision").json()["next_question"]
        if not q or not q["fact_id"] or q["optional"]:
            break
        ev = (q["enum_values"] or [None])[0]
        text = {
            "enum": q["enum_labels_de"].get(ev, ev) if ev else "",
            "boolean": "nein",
            "date": "2026-11-02",
            "integer": "1500",
        }.get(q["data_type"], "Zürich")
        say(client, cid, text, answers=q["fact_id"])
    _, t = report(client, cid)
    assert "Wichtige Angaben, die noch fehlen" not in t
    assert "Alle wichtigen Angaben sind erfasst" in t or "Offene Punkte" not in t


def test_c_unanswered_optional_questions_are_not_a_missing_catalogue(client):
    cid = new_case(client)["id"]
    say(client, cid, FALL14)
    _, t = report(client, cid)
    for optional_label in (
        "Ferien oder Abwesenheit beim Empfang",
        "Krankheit beim Empfang",
        "Härtegründe",
    ):
        assert optional_label not in t


def test_d_answered_optional_facts_appear(client):
    cid = new_case(client)["id"]
    say(client, cid, FALL14)
    say(client, cid, "nein", answers="illness_at_receipt")
    say(client, cid, "nein", answers="absence_at_receipt")
    _, t = report(client, cid)
    assert "Krankheit beim Empfang" in t and "Ferien oder Abwesenheit" in t


def test_e_conditionally_not_applicable_questions_are_hidden(client):
    cid = new_case(client)["id"]
    say(client, cid, FALL14)
    say(client, cid, "Nein", answers="family_home_with_spouse")
    _, t = report(client, cid)
    assert "Partnerperson wohnt noch dort" not in t and "separate Zustellung" not in t.lower()


def test_f_multiple_issues_one_report_without_duplicate_facts(client):
    cid = new_case(client)["id"]
    say(
        client,
        cid,
        "Der Vermieter hat gekündigt. Die Klientin hat Schimmel im Schlafzimmer und die Miete gekürzt, in Zürich.",
    )
    b = client.post(f"/api/cases/{cid}/briefings").json()
    html = client.get(f"/api/cases/{cid}/briefings/{b['id']}/preview").text
    assert "Kündigung durch die Vermieterschaft" in html and "Mängel an der Mietsache" in html
    annex = html[
        html.index('<section class="annex"') :
    ]  # page 1 is a summary; the facts section lists each fact once
    rows = re.findall(r'<div class="k">([^<]+)</div>', annex)
    dup = {r for r in rows if rows.count(r) > 1}
    assert not dup, dup  # a shared fact is listed once in the facts section


def test_g_human_correction_wins_and_origin_stays_visible(client):
    cid = fall14(client)
    r = client.patch(
        f"/api/cases/{cid}/facts/delivery_method",
        json={"value": "eingeschrieben", "reason": "Umschlag geprüft"},
    )
    assert r.status_code == 200, r.text
    _, t = report(client, cid)
    assert "Eingeschrieben" in t and "bestätigt" in t.lower()


def test_h_acute_danger_comes_first(client):
    cid = new_case(client)["id"]
    say(
        client,
        cid,
        "Der Vermieter hat gekündigt und droht, meine Klientin zu schlagen. Sie wird gerade bedroht.",
    )
    _, t = report(client, cid)
    assert t.index("Akute Gefahr erkannt") < t.index("Kurzsachverhalt")
    assert "Sofort handeln" in t


def test_i_ai_failure_never_invents_facts(client, ctx, monkeypatch):
    from app.services.ai.base import AIProviderError

    class Down(AIProviderError):
        code = "ai_unavailable"

    def boom(*a, **k):
        raise Down("KI nicht erreichbar")

    monkeypatch.setattr(ctx.ai, "extract", boom)
    cid = new_case(client)["id"]
    r = client.post(f"/api/cases/{cid}/messages", json={"content": FALL14})
    assert r.status_code == 201
    detail = client.get(f"/api/cases/{cid}").json()
    assert detail["analysis"]["status"] != "OK"
    facts = [f for f in client.get(f"/api/cases/{cid}/facts").json() if f["status"] == "KNOWN"]
    assert facts == []  # nothing invented
    b = client.post(f"/api/cases/{cid}/briefings")
    assert b.status_code == 409  # honest: no report from an incomplete analysis


def test_j_old_briefing_versions_stay_unchanged(client):
    cid = fall14(client)
    b1, _ = report(client, cid)
    before = client.get(f"/api/cases/{cid}/briefings/{b1['id']}").json()
    say(client, cid, "nein", answers="illness_at_receipt")
    report(client, cid)
    after = client.get(f"/api/cases/{cid}/briefings/{b1['id']}").json()
    assert before == after and len(client.get(f"/api/cases/{cid}/briefings").json()) == 2


def test_sources_wording_only_for_triggered_findings(client):
    cid = fall14(client)
    _, t = report(client, cid)
    assert "Weitere Quellen (Kurzverweis)" in t
    assert "Art. 266l" in t  # the triggered form finding keeps its wording
    html = client.get(
        f"/api/cases/{cid}/briefings/{client.get(f'/api/cases/{cid}/briefings').json()[0]['id']}/preview"
    ).text
    assert html.count('class="src-card"') <= 5  # not 15 full article cards


def test_report_needs_no_ai_call(client, ctx, monkeypatch):
    cid = fall14(client)
    calls = []
    monkeypatch.setattr(ctx.ai, "extract", lambda *a, **k: calls.append(1))
    monkeypatch.setattr(ctx.ai, "rephrase_question", lambda *a, **k: calls.append(1))
    report(client, cid)
    client.get(f"/api/cases/{cid}/briefings")
    assert calls == []
