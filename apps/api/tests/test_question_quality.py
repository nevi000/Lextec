"""Question quality audit (Fragequalität): every question of the seven tenancy issues asks for exactly what its answer type captures.

Only wording changed (scripts/kb/question_fixes.py); fact IDs, answer types, enum values, conditions and rules are unchanged."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import REPO_ROOT
from app.models.tables import TranslationCache
from app.services.knowledge.loader import load_knowledge_base
from app.services.knowledge.question_quality import UPLOAD, audit
from tests.conftest import answer_question, new_case, say

KB = load_knowledge_base(REPO_ROOT / "knowledge_base")
REAL = {i.id: i for i in KB.issues.values() if i.content_status != "DEMO_SYNTHETIC"}
BASELINE = json.loads(
    (Path(__file__).parent / "fixtures" / "question_types_baseline.json").read_text(
        encoding="utf-8"
    )
)
SIMPLE = "In der Wohnung der Klientin ist Schimmel im Schlafzimmer."
BASE = "Mein Vermieter hat der Klientin die Wohnung gekündigt, ohne amtliches Formular, in Zürich."


def test_the_seven_tenancy_issues_are_audited():
    assert len(REAL) == 7
    assert sum(len(i.facts) for i in REAL.values()) >= 260


# ---- A: no upload requests ---------------------------------------------------------------------------------
def test_a_no_question_asks_for_an_upload():
    for issue in REAL.values():
        for f in issue.facts:
            for text in (f.question_de, f.why_needed_de or ""):
                assert not UPLOAD.search(text), (issue.id, f.id, text)


def test_a_the_documented_replacements_read_as_availability_questions():
    f = {x.id: x for x in REAL["CH_TENANCY_RENT_INCREASE"].facts}
    assert (
        f["increase_letter_available"].question_de
        == "Liegt das Schreiben der Vermieterschaft vollständig vor (alle Seiten, Umschlag)?"
    )
    assert f["increase_letter_available"].data_type == "boolean"
    e = {x.id: x for x in REAL["CH_TENANCY_EVICTION"].facts}
    assert e["eviction_document_available"].question_de.startswith(
        "Liegt das Schreiben vollständig vor"
    )


# ---- static audit: no technical errors, no unexplained hints -------------------------------------------------------
def test_static_audit_finds_no_error_and_no_open_hint():
    findings = audit(KB)
    assert [f for f in findings if f.severity == "error"] == []
    assert [(f.fact_id, f.rule) for f in findings if f.severity == "hint"] == []


# ---- B/C/D/E/L: question wording matches the answer type -------------------------------------------------------------
@pytest.mark.parametrize("issue_id", sorted(REAL))
def test_l_every_fact_is_answerable_with_its_input_type(issue_id):
    for f in REAL[issue_id].facts:
        assert f.data_type in {"boolean", "date", "integer", "enum", "string"}
        if f.data_type == "enum":
            assert len(f.enum_values) >= 2, f.id
            assert set(f.enum_labels_de) <= set(f.enum_values), f.id
        assert "?" in f.question_de or f.question_de.strip().endswith("."), (f.id, f.question_de)


def test_b_yes_no_questions_are_plain_yes_no():
    for issue in REAL.values():
        for f in issue.facts:
            if f.data_type == "boolean":
                assert f.question_de.count("?") == 1, (f.id, f.question_de)


def test_c_two_part_questions_are_separate_facts_with_the_right_types():
    f = {x.id: x for x in REAL["CH_TENANCY_DEFECTS"].facts}
    assert (
        f["landlord_informed"].data_type == "boolean"
        and "Wie" not in f["landlord_informed"].question_de
    )
    assert f["landlord_informed_in_writing"].data_type == "boolean"
    assert f["landlord_informed_date"].data_type == "date"
    assert f["landlord_reacted"].data_type == "boolean"
    assert (
        f["defect_since"].data_type == "date"
        and "Seit wann" not in f["defect_description"].question_de
    )
    p = {x.id: x for x in REAL["CH_TENANCY_EXTENSION"].facts}
    assert (
        p["previous_extension"].data_type == "boolean"
        and p["previous_extension_end_date"].data_type == "date"
    )


def test_d_receipt_dates_are_date_facts():
    for iid, fid in [
        ("CH_TENANCY_TERMINATION", "receipt_date"),
        ("CH_TENANCY_PAYMENT_WARNING", "warning_receipt_date"),
        ("CH_TENANCY_RENT_INCREASE", "increase_receipt_date"),
        ("CH_TENANCY_EVICTION", "document_receipt_date"),
    ]:
        fact = {x.id: x for x in REAL[iid].facts}[fid]
        assert fact.data_type == "date" and "Datum" in fact.question_de


def test_e_amounts_and_days_are_numbers():
    inc = {x.id: x for x in REAL["CH_TENANCY_RENT_INCREASE"].facts}
    for fid in ("old_rent_chf", "new_rent_chf"):
        assert inc[fid].data_type == "integer"
    warn = {x.id: x for x in REAL["CH_TENANCY_PAYMENT_WARNING"].facts}
    assert (
        warn["warning_deadline_days"].data_type == "integer"
        and "Tage" in warn["warning_deadline_days"].question_de
    )
    assert (
        warn["warning_amount_clear"].data_type == "boolean"
    )  # «Welcher Betrag?» is no longer hidden in a yes/no


# ---- H/K: nothing about types, enum values or rules changed ------------------------------------------------------------
def test_h_k_answer_types_and_enum_values_are_unchanged():
    now = {
        f"{i.id}:{f.id}": {"type": f.data_type, "enum": list(f.enum_values)}
        for i in REAL.values()
        for f in i.facts
    }
    assert (
        now == BASELINE
    )  # old stored answers keep their meaning; the rule engine reads the same facts


# ---- F/G: conditional follow-up and «weiss nicht» ---------------------------------------------------------------------
def _next_is(client, cid, fact_id):
    for _ in range(60):
        q = client.get(f"/api/cases/{cid}/current-decision").json()["next_question"]
        if q["fact_id"] == fact_id:
            return q
        answer_question(client, cid, q)
    raise AssertionError(f"{fact_id} never became the next question")


def _missing_ids(client, cid):
    return {
        m["fact_id"]
        for m in client.get(f"/api/cases/{cid}/current-decision").json()["missing_facts"]
    }


def test_f_follow_up_only_when_its_condition_holds(client):
    ids = {}
    for answer in ("nein", "ja"):
        cid = new_case(client)["id"]
        say(client, cid, SIMPLE)
        _next_is(client, cid, "landlord_informed")
        say(client, cid, answer, answers="landlord_informed")
        ids[answer] = _missing_ids(client, cid)
    assert "landlord_informed_in_writing" not in ids["nein"]
    assert "landlord_informed_in_writing" in ids["ja"]


def test_g_unknown_is_stored_without_a_value(client):
    cid = new_case(client)["id"]
    say(client, cid, BASE)
    q = client.get(f"/api/cases/{cid}/current-decision").json()["next_question"]
    r = client.post(
        f"/api/cases/{cid}/messages",
        json={"content": "Weiss nicht.", "answers_fact_id": q["fact_id"], "unknown": True},
    )
    assert r.status_code == 201
    fact = next(
        f for f in client.get(f"/api/cases/{cid}/facts").json() if f["fact_id"] == q["fact_id"]
    )
    assert fact["status"] == "UNKNOWN" and fact["value"] in (None, "")


def _reach(client, cid, fact_id):
    for _ in range(60):
        q = client.get(f"/api/cases/{cid}/current-decision").json()["next_question"]
        if q["fact_id"] == fact_id:
            return True
        answer_question(client, cid, q)
    return False


def test_d_a_date_answer_is_stored_as_a_date(client):
    cid = new_case(client)["id"]
    say(client, cid, BASE)
    assert _reach(client, cid, "receipt_date")
    say(client, cid, "04.11.2026", answers="receipt_date")
    fact = next(
        f for f in client.get(f"/api/cases/{cid}/facts").json() if f["fact_id"] == "receipt_date"
    )
    assert fact["status"] == "KNOWN" and str(fact["value"]).startswith("2026-11-04")


# ---- I: Sprachbrücke uses the corrected wording, never an old translation -----------------------------------------------
def test_i_phone_shows_the_corrected_question_and_a_changed_text_is_translated_afresh(client, ctx):
    from app.services.bridge.service import translate_cached

    cid = new_case(client)["id"]
    say(client, cid, BASE)
    token = client.post(f"/api/cases/{cid}/voice-bridge").json()["join_token"]
    s = client.post(
        "/api/bridge/language", json={"language": "en"}, headers={"X-Bridge-Token": token}
    ).json()
    engine_q = client.get(f"/api/cases/{cid}/current-decision").json()["next_question"][
        "question_de"
    ]
    assert s["question"]["text"] == f"[EN · Mock] {engine_q}"
    assert not UPLOAD.search(s["question"]["text"])

    old = "Bitte das Schreiben hochladen (alle Seiten, mit Umschlag). Ist es vorhanden?"
    new = "Liegt das Schreiben vollständig vor (alle Seiten, mit Umschlag)?"
    calls = []
    real = ctx.ai.translate

    def counting(texts, *a, **k):
        calls.append(list(texts))
        return real(texts, *a, **k)

    ctx.ai.translate = counting  # type: ignore[method-assign]
    try:
        translate_cached(ctx.session_factory, ctx.ai, [old], "ar", cid)
        translate_cached(
            ctx.session_factory, ctx.ai, [new], "ar", cid
        )  # a reworded question is a different cache entry
        assert calls == [[old], [new]]
        translate_cached(ctx.session_factory, ctx.ai, [new], "ar", cid)
        assert len(calls) == 2
    finally:
        ctx.ai.translate = real  # type: ignore[method-assign]
    with ctx.session_factory() as db:
        assert (
            db.scalar(select(TranslationCache).where(TranslationCache.source_text == new))
            is not None
        )


# ---- J: the briefing shows corrected answers --------------------------------------------------------------------------
def test_j_briefing_contains_the_answer_to_a_corrected_question(client):
    cid = new_case(client)["id"]
    say(client, cid, BASE)
    assert _reach(client, cid, "receipt_date")
    say(client, cid, "04.11.2026", answers="receipt_date")
    b = client.post(f"/api/cases/{cid}/briefings")
    assert b.status_code == 201
    assert "04.11.2026" in b.text
