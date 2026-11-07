"""Issues 2-7 (Law-Dossiers vom 7.11.2026) und die zehn Cross-Issue-Tests. Ausschliesslich Mock-KI.

Soll-Ergebnisse stammen aus den Dossiers (Eskalationsregeln, Testfälle T5-xx/T6-xx/T7-xx, erlaubte/verbotene Aussagen).
Die Szenarien der einzelnen Issues liegen als YAML in knowledge_base/tests/scenarios_<ISSUE>.yaml und werden hier
zusätzlich als Ganzes durch die deterministische Engine geprüft.
"""

from __future__ import annotations

import json
import re

import pytest

from app.core.config import REPO_ROOT
from app.domain.enums import Action, FactStatus, IssueStatus
from app.domain.state import CaseSnapshot, FactState, IssueState
from app.services.decisions.engine import decide
from app.services.decisions.evaluation import run_scenarios
from app.services.knowledge.loader import load_knowledge_base
from app.services.policy.guard import find_violations
from tests.conftest import new_case, say

NEW_ISSUES = [
    "CH_TENANCY_PAYMENT_WARNING",
    "CH_TENANCY_PAYMENT_DEFAULT",
    "CH_TENANCY_EXTENSION",
    "CH_TENANCY_DEFECTS",
    "CH_TENANCY_EVICTION",
    "CH_TENANCY_RENT_INCREASE",
]
ALL_SEVEN = ["CH_TENANCY_TERMINATION", *NEW_ISSUES]


@pytest.fixture(scope="module")
def kb():
    k = load_knowledge_base(REPO_ROOT / "knowledge_base")
    assert k.valid, k.errors
    return k


def snap(issues, facts=None, today="2026-11-07", unknown=()):
    from datetime import date

    f = {k: FactState(FactStatus.KNOWN, v) for k, v in (facts or {}).items()}
    for u in unknown:
        f[u] = FactState(FactStatus.UNKNOWN, None)
    return CaseSnapshot(
        has_user_input=True,
        issues=[IssueState(IssueStatus.DETECTED, i, 0.9) for i in issues],
        facts=f,
        today=date.fromisoformat(today),
    )


# --------------------------------------------------------------------------- Struktur & Quellen
def test_all_seven_issues_are_loaded_as_draft_dossier_status(kb):
    for iid in ALL_SEVEN:
        assert iid in kb.issues, iid
        assert (
            kb.issues[iid].content_status == "DRAFT"
        )  # nie stillschweigend «juristisch freigegeben»
        assert (
            kb.issues[iid].escalation_rules and kb.issues[iid].legal_rules and kb.issues[iid].facts
        )
    # Legacy-Demo-Issue bleibt für alte Fälle geladen, wird aber nicht mehr klassifiziert
    assert "tenancy_defects" in kb.issues
    offered = {d.id for d in kb.catalog_issues()}
    assert "tenancy_defects" not in offered and "CH_TENANCY_DEFECTS" in offered
    assert kb.issues["tenancy_defects"].content_status == "DEMO_SYNTHETIC"


def test_issue_scenarios_from_the_law_documents_all_pass(kb):
    summary = run_scenarios(kb)
    failed = [(r.scenario_id, r.mismatches) for r in summary.results if not r.passed]
    assert not failed, failed
    per_issue = {iid: 0 for iid in NEW_ISSUES}
    for sc in kb.scenarios:
        for i in sc.issues:
            if i["id"] in per_issue:
                per_issue[i["id"]] += 1
    assert all(n >= 10 for n in per_issue.values()), per_issue
    ids = {s.id for s in kb.scenarios}
    for n in range(1, 17):  # T5-01 .. T5-16 aus Issue 5
        assert f"SC_DF_T5{n:02d}" in ids
    for n in range(1, 8):  # T6-01 .. T6-07
        assert f"SC_EV_T60{n}" in ids
    for n in range(1, 11):  # T7-01 .. T7-10
        assert f"SC_RI_T7{n:02d}" in ids


def test_sources_are_split_by_provider_and_hierarchy(kb):
    s = kb.sources
    assert (
        s["CH_VMWG_19_1_A"].sr_number == "221.213.11" and s["CH_VMWG_19_1_A"].provider == "fedlex"
    )
    assert s["CH_SCHKG_74_1"].sr_number == "281.1" and s["CH_SCHKG_74_1"].provider == "fedlex"
    assert s["CH_ZPO_257"].sr_number == "272" and s["CH_OR_257D_1"].sr_number == "220"
    assert (
        s["ZH_GOG_147"].provider == "other" and s["ZH_GOG_147"].fedlex_sync is False
    )  # kantonal, nicht Fedlex
    assert s["BGE_119_II_147"].type == "case_law" and s["BGE_119_II_147"].core_statement_de
    assert s["LEHRBUCH_MIETE_31"].type == "other" and s["PRODUKTREGEL"].type == "other"
    # nichts ist stillschweigend «verifiziert»
    assert all(x.verification_status == "UNVERIFIED" for x in s.values())


def test_every_fact_and_rule_of_the_new_issues_has_valid_sources(kb):
    for iid in ALL_SEVEN:
        d = kb.issues[iid]
        for lr in d.legal_rules:
            assert lr.legal_source_ids, lr.id
            assert all(kb.resolve_source_id(x) for x in lr.legal_source_ids), lr.id
        for f in d.facts:
            assert all(kb.resolve_source_id(x) for x in f.source_ids), (iid, f.id)


def test_consent_briefing_fact_exists_in_every_issue(kb):
    for iid in ALL_SEVEN:
        ids = {f.id for f in kb.issues[iid].facts}
        assert "consent_briefing" in ids, iid
    f = next(f for f in kb.issues["CH_TENANCY_TERMINATION"].facts if f.id == "consent_briefing")
    assert f.data_type == "boolean" and not f.required  # blockiert die lokale Fallaufnahme nicht


def test_ids_of_shared_facts_are_stable(kb):
    # Fakt-IDs aus Issue 1 bleiben unverändert (Rückwärtskompatibilität)
    ids = {f.id for f in kb.issues["CH_TENANCY_TERMINATION"].facts}
    for old in (
        "tenant_role",
        "receipt_date",
        "delivery_method",
        "official_form_used",
        "termination_date",
        "contract_term_type",
        "hardship_present",
        "eviction_or_court_proceeding",
    ):
        assert old in ids
    assert "contract_termination_dates" in ids and "contract_end_date" in ids


# ---------------------------------------------------------------------- Issue 1: neue Dossierfassung
def test_issue1_fixed_term_75_day_team_decision(kb):
    base = {
        "tenant_role": "hauptmieterin",
        "object_type": "wohnung",
        "contract_term_type": "befristet",
    }
    d = decide(kb, snap(["CH_TENANCY_TERMINATION"], {**base, "contract_end_date": "2027-01-20"}))
    assert "TT_FIXED_TERM_LE_75" in d.triggered_rule_ids and d.max_urgency == "HIGH"
    d = decide(kb, snap(["CH_TENANCY_TERMINATION"], {**base, "contract_end_date": "2027-04-30"}))
    assert "TT_FIXED_TERM_LE_75" not in d.triggered_rule_ids
    d = decide(kb, snap(["CH_TENANCY_TERMINATION"], base, unknown=["contract_end_date"]))
    assert "TT_FIXED_TERM_LE_75" in d.triggered_rule_ids  # Ende unbekannt = sofort


def test_issue1_local_terms_are_only_a_check_hint_never_hardcoded(kb):
    d = decide(
        kb,
        snap(
            ["CH_TENANCY_TERMINATION"],
            {"contract_term_type": "unbefristet"},
            unknown=["contract_termination_dates"],
        ),
    )
    texts = [s.text_de for s in d.approved_statements]
    assert any("ortsüblichen Termine" in t and "prüfen" in t for t in texts)
    for i in kb.issues["CH_TENANCY_TERMINATION"].legal_rules:
        assert not re.search(
            r"Ende\s+(März|Juni|September|Dezember)", i.result_de
        )  # keine hart kodierten Termine


# ---------------------------------------------------------------------------- Issue-Logik (Engine)
def test_issue2_parallel_social_and_legal_escalation_without_computed_deadline(kb):
    facts = {"tenant_role": "hauptmieterin", "payment_status": "nicht_bezahlt"}
    d = decide(kb, snap(["CH_TENANCY_PAYMENT_WARNING"], facts))
    assert d.action == Action.ESCALATE and d.max_urgency == "HIGH"
    assert {"social_counselling", "tenancy_law_counsel"} <= set(d.recommended_professionals)
    blob = " ".join(s.text_de for s in d.approved_statements) + d.explanation_de
    assert not re.search(
        r"\b(bis|spätestens)\s+(zum\s+)?\d{1,2}\.", blob
    )  # kein berechnetes Fristende
    assert any(
        "3 Arbeitstage" in s.text_de for s in d.approved_statements
    )  # Produktempfehlung, kein Gesetz


def test_issue2_receipt_rule_is_relative_not_issue1_absolute(kb):
    f2 = {fid: f for f in kb.issues["CH_TENANCY_PAYMENT_WARNING"].facts for fid in [f.id]}
    f1 = {f.id for f in kb.issues["CH_TENANCY_TERMINATION"].facts}
    assert "warning_receipt_date" in f2 and "warning_receipt_date" not in f1
    assert (
        "7. Tag der Abholfrist" in f2["warning_pickup_notice_date"].why_needed_de
        or "7." in f2["warning_pickup_notice_date"].why_needed_de
    )


def test_issue3_always_escalates_immediately_even_when_facts_are_missing(kb):
    d = decide(kb, snap(["CH_TENANCY_PAYMENT_DEFAULT"], {}))
    assert d.action == Action.ESCALATE and d.max_urgency == "HIGH"
    assert (
        "PD_GRUNDREGEL" in d.triggered_rule_ids and d.missing_facts
    )  # fragt weiter, wartet aber nicht
    assert {"tenancy_law_counsel", "social_counselling"} <= set(d.recommended_professionals)
    assert not any(
        "Erstreckung" in s.text_de and "möglich" in s.text_de for s in d.approved_statements
    )


def test_issue4_excluded_for_payment_default_suppresses_extension_statements(kb):
    d = decide(kb, snap(["CH_TENANCY_EXTENSION"], {"ending_reason": "zahlungsverzug"}))
    assert "EX_ZAHLUNGSVERZUG" in d.triggered_rule_ids
    assert d.statements_suppressed and not d.approved_statements
    assert "CH_TENANCY_PAYMENT_DEFAULT" in d.active_issue_ids  # Wechsel zu Issue 3


def test_issue4_thresholds_20_and_75_days_are_product_decisions(kb):
    base = {
        "ending_reason": "ordentliche_kuendigung",
        "contract_term_type": "unbefristet",
        "delivery_method": "persoenlich",
    }
    d = decide(kb, snap(["CH_TENANCY_EXTENSION"], {**base, "receipt_date": "2026-10-17"}))
    assert "EX_UNBEFRISTET_FRIST" in d.triggered_rule_ids
    d = decide(kb, snap(["CH_TENANCY_EXTENSION"], {**base, "receipt_date": "2026-11-02"}))
    assert "EX_UNBEFRISTET_FRIST" not in d.triggered_rule_ids
    assert (
        d.recommended_professionals[0] == "tenancy_law_counsel"
    )  # immer Rechtsperson, keine Prognose


def test_issue5_simple_case_may_proceed_but_health_info_escalates(kb):
    sc = {s.id: s for s in kb.scenarios}
    d = decide(kb, snap(["CH_TENANCY_DEFECTS"], sc["SC_DF_T501"].facts))
    assert d.action == Action.PROCEED
    d = decide(
        kb,
        snap(["CH_TENANCY_DEFECTS"], {**sc["SC_DF_T501"].facts, "health_symptoms_reported": True}),
    )
    assert d.action == Action.ESCALATE and "DF_H1_BESCHWERDEN" in d.triggered_rule_ids


def test_issue5_unknown_is_never_no_and_h7_escalates(kb):
    sc = {s.id: s for s in kb.scenarios}["SC_DF_T501"].facts
    facts = {k: v for k, v in sc.items() if k != "medical_risk_reported"}
    d = decide(kb, snap(["CH_TENANCY_DEFECTS"], facts, unknown=["medical_risk_reported"]))
    assert "DF_H7_GESUNDHEIT_UNBEKANNT" in d.triggered_rule_ids
    assert d.action == Action.ESCALATE


def test_issue5_has_no_diagnosis_and_no_percentage_in_any_statement(kb):
    d = kb.issues["CH_TENANCY_DEFECTS"]
    for lr in d.legal_rules:
        assert not re.search(r"\d\s?%|Prozent", lr.result_de), lr.id
    for f in d.facts:
        if f.id in ("health_symptoms_reported", "medical_risk_reported"):
            assert f.store_evidence is False and f.data_type == "boolean"


def test_issue6_has_no_question_round_before_escalation(kb):
    d = decide(kb, snap(["CH_TENANCY_EVICTION"], {}))
    assert d.action == Action.ESCALATE and d.max_urgency == "HIGH"
    assert (
        d.main_reason_code == "EVICTION_ALWAYS_IMMEDIATE"
        or "EVICTION_ALWAYS_IMMEDIATE" in d.reason_codes
    )
    assert not any(t.reason_code == "MISSING_REQUIRED_FACTS" and False for t in d.triggered_rules)
    d = decide(kb, snap(["CH_TENANCY_EVICTION"], {"eviction_stage": "ammannamt_raeumungstermin"}))
    assert (
        d.recommended_professionals[0] == "social_counselling"
    )  # SOZIAL + RECHT bei Räumungstermin


def test_issue6_quotes_deadline_verbatim_and_never_computes(kb):
    f = next(f for f in kb.issues["CH_TENANCY_EVICTION"].facts if f.id == "deadline_quoted_text")
    assert f.data_type == "string" and "wörtlich" in f.question_de
    blob = " ".join(lr.result_de for lr in kb.issues["CH_TENANCY_EVICTION"].legal_rules)
    assert not re.search(
        r"\b\d{1,2}\.\s?(\d{1,2}\.|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)",
        blob,
    )


def test_issue7_never_judges_abusiveness_or_names_the_reference_rate(kb):
    d = kb.issues["CH_TENANCY_RENT_INCREASE"]
    blob = " ".join(lr.result_de for lr in d.legal_rules)
    assert not re.search(r"Referenzzinssatz\s+(beträgt|liegt|ist)", blob)
    assert not re.search(r"\d[.,]\d{1,2}\s?%", blob)
    assert "Missbräuchlichkeit" not in {x.result_code for x in d.legal_rules}
    assert any(
        lr.result_code == "REVIEW_PRINTED_SIGNATURE_VALID" for lr in d.legal_rules
    )  # Art. 269d Abs. 4 OR


def test_issue7_threshold_20_days_and_relative_receipt(kb):
    base = {
        "tenant_role": "hauptmieterin",
        "object_type": "wohnung",
        "increase_delivery_method": "persoenlich",
    }
    d = decide(
        kb, snap(["CH_TENANCY_RENT_INCREASE"], {**base, "increase_receipt_date": "2026-10-13"})
    )
    assert "RI_FRIST_20_ODER_UNBEKANNT" in d.triggered_rule_ids and d.max_urgency == "HIGH"
    d = decide(
        kb, snap(["CH_TENANCY_RENT_INCREASE"], {**base, "increase_receipt_date": "2026-11-02"})
    )
    assert "RI_FRIST_20_ODER_UNBEKANNT" not in d.triggered_rule_ids


# ----------------------------------------------------------------------------- Cross-Issue-Logik
def test_routes_activate_loaded_issues_additionally_and_merge_reasons(kb):
    facts = {"tenant_role": "hauptmieterin", "object_type": "wohnung", "hardship_present": True}
    d = decide(kb, snap(["CH_TENANCY_TERMINATION"], facts))
    assert "CH_TENANCY_EXTENSION" in d.active_issue_ids  # Test-4-Muster: Issue 1 + Issue 4
    r = next(r for r in d.related_routes if r.issue_id == "CH_TENANCY_EXTENSION")
    assert (
        r.available and "nicht juristisch freigegeben" in r.note_de
    )  # DRAFT wird nie als freigegeben dargestellt
    assert (
        "TT_HARDSHIP" in d.triggered_rule_ids and "EX_GRUNDREGEL" in d.triggered_rule_ids
    )  # Gründe zusammengeführt
    assert d.max_urgency == "HIGH" or d.max_urgency == "MEDIUM"


def test_highest_actual_urgency_wins_across_issues(kb):
    facts = {"payment_status": "nicht_bezahlt", "hardship_present": True}
    d = decide(kb, snap(["CH_TENANCY_PAYMENT_WARNING", "CH_TENANCY_EXTENSION"], facts))
    assert d.max_urgency == "HIGH"
    ranks = [t.urgency for t in d.triggered_rules]
    assert ranks == sorted(
        ranks, key=lambda u: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[u]
    )  # sortiert, Höchste zuerst


def test_shared_facts_are_asked_only_once(kb):
    d = decide(
        kb,
        snap(
            ["CH_TENANCY_PAYMENT_WARNING", "CH_TENANCY_PAYMENT_DEFAULT", "CH_TENANCY_EXTENSION"], {}
        ),
    )
    ids = [m.fact_id for m in d.missing_facts]
    assert len(ids) == len(set(ids))
    tr = next(m for m in d.missing_facts if m.fact_id == "tenant_role")
    assert len(tr.issue_ids) >= 3  # eine Frage, mehrere Issues


def test_conditional_facts_are_not_asked_when_not_applicable(kb):
    # separate Zustellung an die Partnerperson nur bei Familienwohnung (Dossier: keine pauschale Frage)
    d = decide(kb, snap(["CH_TENANCY_PAYMENT_WARNING"], {"family_home_with_spouse": False}))
    assert "warning_family_separate" not in [m.fact_id for m in d.missing_facts]
    d = decide(
        kb,
        snap(
            ["CH_TENANCY_PAYMENT_WARNING"],
            {"family_home_with_spouse": True, "spouse_still_lives_there": True},
        ),
    )
    assert "warning_family_separate" in [m.fact_id for m in d.missing_facts]


def test_increase_and_termination_deadline_rules_stay_separate(kb):
    """Test 8: Mietzinserhöhung + Kündigung -> Issues 7 und 1, keine falsche Zusammenlegung der Fristregeln."""
    facts = {
        "tenant_role": "hauptmieterin",
        "object_type": "wohnung",
        "contract_term_type": "unbefristet",
        "delivery_method": "persoenlich",
        "receipt_date": "2026-11-02",  # Kündigung: 5 Tage
        "increase_delivery_method": "persoenlich",
        "increase_receipt_date": "2026-10-13",  # Erhöhung: 25 Tage
    }
    d = decide(kb, snap(["CH_TENANCY_TERMINATION", "CH_TENANCY_RENT_INCREASE"], facts))
    assert "RI_FRIST_20_ODER_UNBEKANNT" in d.triggered_rule_ids
    assert (
        "TT_DAYS_GE_20" not in d.triggered_rule_ids and "TT_DAYS_GT_30" not in d.triggered_rule_ids
    )
    assert d.derived_values["days_since_earliest_receipt"] == 5
    assert d.derived_values["days_since_increase_receipt"] == 25


def test_referrals_are_deduplicated_across_issues(kb):
    facts = {"payment_status": "nicht_bezahlt"}
    d = decide(
        kb,
        snap(
            ["CH_TENANCY_PAYMENT_WARNING", "CH_TENANCY_PAYMENT_DEFAULT", "CH_TENANCY_EXTENSION"],
            facts,
        ),
    )
    cards = [c.id for c in d.referrals.primary] + [c.id for c in d.referrals.more]
    assert len(cards) == len(set(cards))
    assert cards, "Fachstellen werden für die neuen Issues empfohlen"


# ---------------------------------------------------------------------- erlaubte/verbotene Aussagen
FORBIDDEN_SENTENCES = [
    # Issue 2
    "Die Mahnung ist ungültig, Sie müssen nichts zahlen.",
    "Eine Teilzahlung reicht aus.",
    "Der kleine Rest ist egal.",
    "Wenn Sie den Betrag bestreiten, müssen Sie nicht zahlen.",
    "Es reicht, wenn Sie am letzten Tag der Frist überweisen.",
    "Mit einem Rechtsvorschlag gegen die Betreibung ist die Kündigung abgewendet.",
    "Sie dürfen wegen der Mängel die Miete zurückbehalten.",
    "Bitte hinterlegen Sie den Rückstand.",
    "Wenn Sie später zahlen, ist alles in Ordnung.",
    "Wenn die Vermieterschaft die Zahlung annimmt, kann sie nicht mehr kündigen.",
    "Sie bekommen noch eine Erinnerung.",
    "Die Frist beginnt erst, wenn Sie den Brief abholen.",
    "Der Sozialdienst kann nicht für Sie zahlen, weil der Vertrag auf Sie lautet.",
    # Issue 3
    "Wenn Sie jetzt zahlen, ist die Kündigung hinfällig.",
    "Die Vermieterschaft hat das Geld angenommen, also gilt die Kündigung nicht.",
    "Die Kündigung ist ungültig.",
    "Die Kaution deckt den Rückstand.",
    "Weil Sie lange dort wohnen und immer pünktlich gezahlt haben, ist die Kündigung missbräuchlich.",
    "Solange Sie anfechten, können Sie sicher bleiben.",
    "Wegen der Kinder bekommen Sie mehr Zeit.",
    # Issue 4
    "Sie bekommen sicher eine Erstreckung.",
    "Mit Kindern bekommen Sie vier Jahre.",
    "Sie können bleiben, bis Sie eine neue Wohnung gefunden haben.",
    "Weil der Auszug hart ist, ist die Kündigung ungültig.",
    "Auch nach einer Kündigung wegen Zahlungsverzug können Sie Erstreckung verlangen.",
    "Da nur ordentlich gekündigt wurde, spielt die frühere Mahnung keine Rolle.",
    "Mit der Suche können Sie warten, bis über die Erstreckung entschieden ist.",
    "Sie können die Frist später noch nachholen.",
    "Unterschreiben Sie den Vergleich ruhig.",
    # Issue 5
    "Sie dürfen die Miete um 20 % kürzen.",
    "Zahlen Sie die Miete einfach nicht, bis repariert ist.",
    "Sie können die Miete hinterlegen.",
    "Das ist ein schwerer Mangel.",
    "Sie können fristlos kündigen und ausziehen.",
    "Lassen Sie es reparieren und schicken Sie die Rechnung der Vermieterschaft.",
    "Die Vermieterschaft muss bis zum 15. Dezember reparieren.",
    "Sie sind selbst schuld.",
    "Das haben Sie verursacht.",
    "Der Schimmel hat die Krankheit verursacht.",
    "Das ist harmlos.",
    "Sie haben ein Recht auf eine Ersatzwohnung.",
    # Issue 6
    "Ignorieren Sie das Schreiben, das ist nur eine Drohung.",
    "Sie müssen nicht öffnen, wenn das Ammannamt kommt.",
    "Sie haben gute Chancen.",
    "Das Gericht wird nicht eintreten.",
    "Wenn das Gericht nicht eintritt, haben Sie gewonnen.",
    "Mit Kindern darf man Sie nicht auf die Strasse stellen.",
    "Sie bekommen sicher noch Zeit.",
    "Wenn Sie jetzt alles nachzahlen, ist die Kündigung erledigt.",
    "Zahlungen des Sozialdienstes zählen nicht, weil der Vertrag auf Sie lautet.",
    # Issue 7
    "Die Erhöhung ist missbräuchlich.",
    "Die Erhöhung ist berechtigt.",
    "Der Referenzzinssatz beträgt zurzeit 1,25 %.",
    "Die Erhöhung ist ungültig, Sie müssen nichts tun.",
    "Ohne Originalunterschrift ist die Erhöhung ungültig.",
    "Zahlen Sie einfach weiter die alte Miete.",
    "Fragen Sie zuerst nach den Zahlen, dann haben Sie mehr Zeit.",
]


@pytest.mark.parametrize("sentence", FORBIDDEN_SENTENCES)
def test_forbidden_statements_from_the_dossiers_are_blocked(kb, sentence):
    assert find_violations(kb, sentence), sentence


def _allowed_statements_from_dossiers() -> list[tuple[int, str]]:
    out = []
    for n in range(2, 8):
        data = json.loads(
            (
                REPO_ROOT / "docs" / "legal_inputs" / "issues_extracted" / f"issue_{n:02d}.json"
            ).read_text(encoding="utf-8")
        )
        on = False
        for sec in data["sections"]:
            for it in sec["items"]:
                if it["type"] == "p" and it["text"].startswith("Erlaubte Aussagen"):
                    on = True
                    continue
                if it["type"] == "p" and it["text"].startswith(("Verbotene Aussagen", "Briefing")):
                    on = False
                if on and it["type"] == "bullet":
                    m = re.match(r"«(.+?)»", it["text"])
                    if m:
                        out.append((n, m.group(1)))
    return out


def test_every_allowed_statement_of_the_dossiers_passes_the_policy_and_is_covered(kb):
    allowed = _allowed_statements_from_dossiers()
    assert len(allowed) >= 40  # alle sechs Dossiers liefern erlaubte Aussagen
    for n, text in allowed:
        assert not find_violations(kb, text), (n, text)


def test_allowed_statements_are_carried_over_nearly_verbatim(kb):
    """Erlaubte Aussagen aus den Dossiers sind als HINT im KB (wörtlich oder unwesentlich gekürzt/ergänzt)."""
    from difflib import SequenceMatcher

    texts = [
        lr.result_de for iid in NEW_ISSUES for lr in kb.issues[iid].legal_rules if lr.kind == "HINT"
    ]
    missing = []
    for n, text in _allowed_statements_from_dossiers():
        best = max((SequenceMatcher(None, text, t).ratio() for t in texts), default=0)
        if best < 0.72:
            missing.append((n, round(best, 2), text[:70]))
    # Nicht abgebildete Aussagen sind in docs/ISSUE_COVERAGE_MATRIX.md ausgewiesen (PARTIAL), nicht verschwiegen.
    assert len(missing) <= 12, missing


# ------------------------------------------------------------------ zehn Cross-Issue-Tests (Mock-KI)
def _decision(r) -> dict:
    return r["case"]["current_decision"]


def test_x01_normal_termination_without_official_form(client):
    cid = new_case(client)["id"]
    r = say(
        client,
        cid,
        "Mein Vermieter hat meiner Klientin die Wohnung gekündigt, ohne amtliches Formular.",
    )
    d = _decision(r)
    assert "CH_TENANCY_TERMINATION" in d["active_issue_ids"]
    assert "TT_FORM_MISSING" in d["triggered_rule_ids"] and d["action"] == "ESCALATE"


def test_x02_payment_warning_without_termination(client):
    cid = new_case(client)["id"]
    r = say(
        client,
        cid,
        "Die Klientin hat von der Verwaltung eine Zahlungsaufforderung mit Kündigungsandrohung wegen Mietrückstand erhalten, noch keine Kündigung.",
    )
    d = _decision(r)
    assert "CH_TENANCY_PAYMENT_WARNING" in d["active_issue_ids"]
    assert "CH_TENANCY_PAYMENT_DEFAULT" not in d["active_issue_ids"]


def test_x03_termination_after_warning_uses_issue_3_with_issue_2_history(client):
    cid = new_case(client)["id"]
    r = say(
        client,
        cid,
        "Wegen Mietrückstand gab es eine Mahnung, danach hat der Vermieter der Klientin gekündigt.",
    )
    d = _decision(r)
    assert "CH_TENANCY_PAYMENT_DEFAULT" in d["active_issue_ids"]
    assert d["action"] == "ESCALATE" and d["max_urgency"] == "HIGH"
    assert "PD_GRUNDREGEL" in d["triggered_rule_ids"]
    facts = {f["fact_id"] for f in client.get(f"/api/cases/{cid}/facts").json()}
    assert {
        "warning_written",
        "warning_threat_present",
    } <= facts  # Vorgeschichte aus Issue 2 wird miterhoben


def test_x04_extension_with_children_activates_issue_1_and_4(client):
    cid = new_case(client)["id"]
    r = say(
        client,
        cid,
        "Der Vermieter hat einer Familie mit zwei Kindern gekündigt, und sie findet keine Wohnung.",
    )
    d = _decision(r)
    assert {"CH_TENANCY_TERMINATION", "CH_TENANCY_EXTENSION"} <= set(d["active_issue_ids"])
    assert d["action"] == "ESCALATE"


def test_x05_mould_and_withheld_rent_with_payment_threat(client):
    cid = new_case(client)["id"]
    r = say(
        client,
        cid,
        "Die Klientin hat die Miete wegen Schimmel gekürzt und jetzt eine Zahlungsaufforderung mit Kündigungsandrohung erhalten.",
    )
    d = _decision(r)
    assert {"CH_TENANCY_DEFECTS", "CH_TENANCY_PAYMENT_WARNING"} <= set(d["active_issue_ids"])
    assert d["action"] == "ESCALATE"


def test_x06_acute_eviction_escalates_immediately_without_question_loop(client):
    cid = new_case(client)["id"]
    r = say(client, cid, "Das Stadtammannamt kommt morgen zur Räumung.")
    d = _decision(r)
    assert d["active_issue_ids"] == ["CH_TENANCY_EVICTION"]
    assert d["action"] == "ESCALATE" and d["max_urgency"] == "HIGH"
    assert (
        "EV_GRUNDREGEL" in d["triggered_rule_ids"]
        and "EV_RAEUMUNG_STEHT" in d["triggered_rule_ids"]
    )
    assert d["recommended_professionals"][:2] == ["social_counselling", "tenancy_law_counsel"]


def test_x07_rent_increase_with_official_form(client):
    cid = new_case(client)["id"]
    r = say(
        client,
        cid,
        "Der Vermieter hat die Miete erhöht, die Mitteilung kam mit dem amtlichen Formular.",
    )
    d = _decision(r)
    assert "CH_TENANCY_RENT_INCREASE" in d["active_issue_ids"]
    assert "RI_KEIN_FORMULAR" not in d["triggered_rule_ids"]


def test_x08_rent_increase_plus_termination_keeps_both_issues(client):
    cid = new_case(client)["id"]
    r = say(
        client, cid, "Der Vermieter hat die Miete erhöht und gleichzeitig die Wohnung gekündigt."
    )
    d = _decision(r)
    assert {"CH_TENANCY_RENT_INCREASE", "CH_TENANCY_TERMINATION"} <= set(d["active_issue_ids"])


def test_x09_unsupported_area_is_never_proceed_by_misclassification(client):
    cid = new_case(client)["id"]
    r = say(client, cid, "Die Klientin möchte sich scheiden lassen und fragt nach dem Sorgerecht.")
    d = _decision(r)
    assert d["action"] == "ESCALATE" and "UNSUPPORTED_LEGAL_AREA" in d["reason_codes"]
    assert not set(d["active_issue_ids"]) & set(ALL_SEVEN)


def test_x10_acute_danger_has_priority_over_any_legal_issue(client):
    cid = new_case(client)["id"]
    r = say(
        client,
        cid,
        "Der Vermieter hat gekündigt, und er droht, meine Klientin zu schlagen. Sie wird gerade bedroht.",
    )
    d = _decision(r)
    assert d["safety"]["state"] == "IMMEDIATE"
    assert d["effective_action"] == "IMMEDIATE_SAFETY_RESPONSE"
    assert (
        "CH_TENANCY_TERMINATION" in d["active_issue_ids"]
    )  # juristische Einordnung bleibt daneben erhalten


def test_case_state_is_preserved_when_issues_are_added(client):
    cid = new_case(client)["id"]
    say(
        client,
        cid,
        "Mein Vermieter hat meiner Klientin die Wohnung gekündigt, in der Stadt Zürich.",
    )
    before = {
        f["fact_id"]: f["value"]
        for f in client.get(f"/api/cases/{cid}/facts").json()
        if f["status"] == "KNOWN"
    }
    say(client, cid, "Zusätzlich hat die Klientin Schimmel in der Wohnung.")
    after = {
        f["fact_id"]: f["value"]
        for f in client.get(f"/api/cases/{cid}/facts").json()
        if f["status"] == "KNOWN"
    }
    for k, v in before.items():
        assert after.get(k) == v, k  # Issue-Wechsel überschreibt nichts


def test_health_wording_is_not_persisted_but_the_yes_value_is(client):
    cid = new_case(client)["id"]
    say(client, cid, "Die Klientin hat Schimmel im Schlafzimmer und das Kind hustet seit Wochen.")
    facts = {f["fact_id"]: f for f in client.get(f"/api/cases/{cid}/facts").json()}
    f = facts.get("health_symptoms_reported")
    assert f and f["status"] == "KNOWN" and f["value"] is True
    assert (
        "hustet" not in (f["evidence_quote"] or "").lower()
    )  # kein Wortlaut, keine Diagnose gespeichert


def test_ai_catalog_is_scoped_by_keyword_prefilter(client, ctx):
    """Kostenkontrolle: Der Fakten-Katalog an das Modell umfasst nicht pauschal alle ~230 Fakten."""
    from app.services.ai.issue_keywords import candidate_issue_ids

    available = {d.id for d in ctx.kb.catalog_issues()}
    assert candidate_issue_ids(["Das Stadtammannamt kommt morgen zur Räumung."], available) == [
        "CH_TENANCY_EVICTION"
    ]
    total = sum(len(d.facts) for d in ctx.kb.catalog_issues())
    scoped = sum(
        len(ctx.kb.issues[i].facts)
        for i in candidate_issue_ids(["Schimmel in der Wohnung"], available)
    )
    assert scoped < total / 3


def test_consent_is_documented_in_the_report_without_blocking_local_creation(client):
    """consent_briefing: Status, Zeitpunkt, Erfasser, Geltungsbereich; lokale Berichtserstellung bleibt möglich."""
    cid = new_case(client)["id"]
    say(client, cid, "Mein Vermieter hat meiner Klientin die Wohnung gekündigt, in Zürich.")
    b = client.post(f"/api/cases/{cid}/briefings")
    assert b.status_code in (200, 201)  # ohne Einwilligung nicht blockiert
    html = client.get(f"/api/cases/{cid}/briefings/{b.json()['id']}/preview").text
    assert "Noch nicht dokumentiert" in html and "Einwilligung" in html
    say(client, cid, "Ja, die Klientin ist einverstanden.", answers="consent_briefing")
    b2 = client.post(f"/api/cases/{cid}/briefings").json()
    html2 = client.get(f"/api/cases/{cid}/briefings/{b2['id']}/preview").text
    assert "Ausdrückliche Einwilligung dokumentiert" in html2
    assert (
        "Sozialarbeiterin (Antwort)" in html2 and "nicht: lokale Erstellung" in html2
    )  # Erfasser + Geltungsbereich
    assert "voraussichtlich" in html2  # IDG-ZH-Einordnung nicht als endgültig dargestellt


def test_two_stage_extraction_adds_facts_of_an_issue_found_outside_the_first_catalog(
    client, ctx, monkeypatch
):
    """Stufe 1 erkennt das Issue, Stufe 2 holt gezielt dessen Fakten nach (max. ein zusätzlicher Aufruf)."""
    from app.services.cases.service import CaseService

    monkeypatch.setattr(
        CaseService, "_fact_scope", lambda self, cid, texts, av: {"CH_TENANCY_TERMINATION"}
    )
    calls = []
    real = ctx.ai.extract

    def counting(data, c=None):
        calls.append((c.function if c else "?", len(data.fact_catalog)))
        return real(data, c)

    monkeypatch.setattr(ctx.ai, "extract", counting)
    cid = new_case(client)["id"]
    r = say(client, cid, "Die Klientin hat Schimmel im Schlafzimmer.")
    assert [f for f, _ in calls] == ["extract", "extract_facts"]
    assert calls[1][1] < calls[0][1] + 60  # kleiner, gezielter Katalog
    assert "CH_TENANCY_DEFECTS" in _decision(r)["active_issue_ids"]
    facts = {f["fact_id"]: f for f in client.get(f"/api/cases/{cid}/facts").json()}
    assert facts["defect_type"]["value"] == "schimmel"  # nur durch Stufe 2 erkennbar


def test_no_second_call_when_the_first_catalog_already_covers_the_issue(client, ctx, monkeypatch):
    calls = []
    real = ctx.ai.extract
    monkeypatch.setattr(
        ctx.ai, "extract", lambda d, c=None: (calls.append(c.function), real(d, c))[1]
    )
    cid = new_case(client)["id"]
    say(client, cid, "Die Klientin hat Schimmel im Schlafzimmer.")
    assert calls == ["extract"]
