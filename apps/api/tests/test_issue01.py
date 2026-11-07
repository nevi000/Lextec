"""Issue 1 (Kündigung durch die Vermieterschaft): classification, missing information, escalation,
statement limits, briefing, demo flow. All with the MOCK provider (no real AI, no cost)."""

from __future__ import annotations

import json
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from app.core.config import REPO_ROOT
from app.domain.enums import Action, FactStatus, IssueStatus
from app.domain.state import CaseSnapshot, FactState, IssueState
from app.services.decisions.engine import decide
from app.services.knowledge.loader import load_knowledge_base
from app.services.policy.guard import find_violations, sanitize
from app.services.rules.derived import compute_derived
from tests.conftest import new_case, say

TT = "CH_TENANCY_TERMINATION"
STEP1 = (
    "Ich betreue eine Klientin in Zürich. Sie hat von ihrem Vermieter die Kündigung für ihre Wohnung "
    "erhalten und weiss nicht, ob sie ausziehen muss."
)
STEP2 = (
    "Die Klientin ist alleinige Mieterin einer normalen Wohnung in der Stadt Zürich. Der Vertrag ist "
    "unbefristet. Es handelt sich nicht um eine Untermiete oder Ferienwohnung."
)
STEP3 = (
    "Die Kündigung hat sie am 4. November 2026 mit normaler Post erhalten. Es war nur ein gewöhnlicher "
    "Brief ohne amtliches Kündigungsformular. Die Kündigung soll per 31. Januar 2027 gelten."
)
STEP4 = (
    "Die Klientin hat keine Mietrückstände. Es gibt keine weiteren Mitmieter und keine Ehe- oder "
    "eingetragene Partnerperson in der Wohnung. Sie hat noch nichts unterschrieben und keine Anfechtung "
    "eingereicht."
)


@pytest.fixture(scope="module")
def kb():
    k = load_knowledge_base(REPO_ROOT / "knowledge_base")
    assert k.valid, k.errors
    return k


def facts_of(client, cid):
    return {f["fact_id"]: f for f in client.get(f"/api/cases/{cid}/facts").json()}


def decision(client, cid):
    return client.get(f"/api/cases/{cid}/current-decision").json()


# ---- A. classification ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Mein Vermieter hat mir gekündigt.",
        "Meine Klientin muss ihre Wohnung verlassen.",
        "Wir haben eine Kündigung der Wohnung erhalten.",
        "Die Vermieterschaft will die Wohnung zurück.",
        "Die Klientin hat ein Kündigungsformular bekommen.",
        "Die Vermieterin kündigt wegen Eigenbedarf.",
    ],
)
def test_dossier_example_phrasings_are_classified_as_issue_1(client, text):
    cid = new_case(client)["id"]
    r = say(client, cid, text)
    assert TT in r["case"]["current_decision"]["active_issue_ids"]


def test_multiple_issues_and_unsupported_issue(client):
    cid = new_case(client)["id"]
    r = say(client, cid, "Der Vermieter hat gekündigt und ausserdem läuft die Scheidung.")
    d = r["case"]["current_decision"]
    assert TT in d["active_issue_ids"]
    assert d["action"] == "ESCALATE" and "UNSUPPORTED_LEGAL_AREA" in d["reason_codes"]
    assert any(i["classification_status"] == "UNSUPPORTED" for i in r["case"]["issues"])


# ---- demo flow: the four documented steps, end to end through the real pipeline ---------------------
def test_demo_flow_steps_1_to_4_and_briefing(client):
    cid = new_case(client)["id"]

    d = say(client, cid, STEP1)["case"]["current_decision"]  # step 1
    assert d["action"] == "ASK" and TT in d["active_issue_ids"]
    assert d["next_question"]["fact_id"] == "tenant_role"  # highest-priority required fact
    assert "Mieterin" in d["next_question"]["question_de"] and d["next_question"]["why_needed_de"]
    f = facts_of(client, cid)
    assert f["property_municipality"]["value"] == "Zürich"

    d = say(client, cid, STEP2)["case"]["current_decision"]  # step 2
    f = facts_of(client, cid)
    assert f["tenant_role"]["value"] == "hauptmieterin" and f["object_type"]["value"] == "wohnung"
    assert f["contract_term_type"]["value"] == "unbefristet"
    assert "tenant_role" not in [m["fact_id"] for m in d["missing_facts"]], (
        "never ask again what is known"
    )
    assert d["next_question"]["fact_id"] == "delivery_method"

    d = say(client, cid, STEP3)["case"]["current_decision"]  # step 3
    f = facts_of(client, cid)
    assert f["delivery_method"]["value"] == "normale_post"
    assert f["receipt_date"]["value"] == "2026-11-04"
    assert f["termination_date"]["value"] == "2027-01-31"
    assert f["official_form_used"]["value"] is False
    assert d["action"] == "ESCALATE" and "TT_FORM_MISSING" in d["triggered_rule_ids"]
    assert d["max_urgency"] == "MEDIUM"
    assert d["derived_values"]["days_since_earliest_receipt"] == 3
    assert any(s["rule_id"] == "TT_HINT_OFFICIAL_FORM" for s in d["approved_statements"])
    assert "TT_DAYS_LT_20_ALL_KNOWN" not in d["triggered_rule_ids"], "not 'all known' yet"
    assert d["missing_facts"], "open questions stay visible while escalating"

    d = say(client, cid, STEP4)["case"]["current_decision"]  # step 4
    f = facts_of(client, cid)
    assert (
        f["co_tenants_exist"]["value"] is False and f["family_home_with_spouse"]["value"] is False
    )
    assert f["already_reacted"]["value"] is False and f["termination_kind"]["value"] == "ordentlich"
    assert d["action"] == "ESCALATE" and d["missing_facts"] == []
    assert {"TT_FORM_MISSING", "TT_DAYS_LT_20_ALL_KNOWN"} <= set(d["triggered_rule_ids"])
    assert "tenancy_law_counsel" in d["recommended_professionals"]

    # --- expert briefing ---
    b = client.post(f"/api/cases/{cid}/briefings").json()["briefing"]
    ib = b["issue_briefings"][0]
    assert ib["issue_id"] == TT and ib["canton"] == "ZH"
    rows = {r["fact_id"]: r for g in ib["groups"] for r in g["rows"]}
    assert rows["receipt_date"]["value_display"] == "04.11.2026"
    assert rows["receipt_date"]["evidence_level"] == "AI_EXTRACTED"  # extracted, not yet confirmed
    assert rows["rent_payer"]["evidence_level"] == "NOT_ASKED"
    assert {t["rule_id"] for t in ib["triggered_rules"]} >= {"TT_FORM_MISSING"}
    assert ib["max_urgency_label_de"] == "bald"
    assert (
        "Produktentscheide" in ib["urgency_note_de"] and "kein Fristende" in ib["urgency_note_de"]
    )
    assert [x["value"] for x in ib["derived"]] == [3, 85]
    assert all(x["evidence_level"] == "SYSTEM_DERIVED" for x in ib["derived"])
    assert ib["documents_to_request"] and len(ib["review_points"]) >= 5
    assert all(a["contact_verified"] is False for a in ib["authorities"])
    assert any("Kontaktdaten" in a["verification_note_de"] for a in ib["authorities"])
    src = {s["source"]["id"]: s["source"] for s in b["legal_sources"]}
    assert src["CH_OR_266L"]["dossier_status"] == "DOSSIER_CHECKED"
    assert all(s["verification_status"] == "UNVERIFIED" for s in src.values()), (
        "no fake live verification"
    )
    assert src["CH_OR_266L"]["text_de"].startswith("«1 Vermieter und Mieter")
    assert "TT_HINT_30_DAYS" in {s["rule_id"] for s in b["approved_statements"]}

    # --- hard rule: never a computed deadline end date, never a validity verdict ---
    # verbatim statute / BGE quotes (legal_sources) are allowed by the dossier; the policy covers system statements
    own = {k: v for k, v in b.items() if k != "legal_sources"}
    blob = json.dumps(own, ensure_ascii=False) + json.dumps(d, ensure_ascii=False)
    end = date(2026, 11, 4) + timedelta(days=30)
    for rendered in (end.isoformat(), end.strftime("%d.%m.%Y"), "4. Dezember 2026", "04.12.2026"):
        assert rendered not in blob
    assert find_violations(load_knowledge_base(REPO_ROOT / "knowledge_base"), blob) == []


# ---- B. missing information: not asked vs. asked-but-unknown ------------------------------------------
def test_not_asked_is_ask_but_asked_unknown_escalates_and_is_never_asked_again(client):
    cid = new_case(client)["id"]
    say(client, cid, STEP1)
    say(client, cid, STEP2)
    d = decision(client, cid)
    assert d["next_question"]["fact_id"] == "delivery_method" and d["action"] == "ASK"

    # the person was asked about the delivery method and does not know (recorded locally, no AI)
    r = client.post(
        f"/api/cases/{cid}/messages",
        json={"content": "Weiss nicht.", "answers_fact_id": "delivery_method", "unknown": True},
    )
    assert r.status_code == 201
    f = facts_of(client, cid)["delivery_method"]
    assert f["status"] == "UNKNOWN" and f["origin"] == "USER_ANSWER"
    d = decision(client, cid)
    assert d["action"] == "ESCALATE" and d["max_urgency"] == "HIGH"
    assert {"TT_UNKNOWN_DELIVERY_OR_RECEIPT", "SYSTEM_REQUIRED_FACT_UNKNOWN"} <= set(
        d["triggered_rule_ids"]
    )
    assert "DELIVERY_OR_RECEIPT_UNKNOWN" in d["reason_codes"]
    assert [m["fact_id"] for m in d["unknown_required_facts"]] == ["delivery_method"]
    assert "delivery_method" not in [m["fact_id"] for m in d["missing_facts"]], (
        "must not repeat the question"
    )
    assert d["next_question"]["fact_id"] != "delivery_method"

    # a later concrete answer (human) resolves the unknown; human values keep priority
    r = client.patch(f"/api/cases/{cid}/facts/delivery_method", json={"value": "eingeschrieben"})
    assert r.status_code == 200
    f = facts_of(client, cid)["delivery_method"]
    assert f["status"] == "KNOWN" and f["origin"] == "USER_CORRECTION" and f["confirmed"]
    say(
        client, cid, "Es war eine normale Post, hat die Nachbarin gesagt."
    )  # AI must not overwrite it
    assert facts_of(client, cid)["delivery_method"]["value"] == "eingeschrieben"


def test_unknown_only_valid_for_unresolved_facts(client):
    cid = new_case(client)["id"]
    say(client, cid, STEP1)
    client.patch(f"/api/cases/{cid}/facts/tenant_role", json={"value": "hauptmieterin"})
    r = client.post(
        f"/api/cases/{cid}/messages",
        json={"content": "x", "answers_fact_id": "tenant_role", "unknown": True},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_state"
    r = client.post(f"/api/cases/{cid}/messages", json={"content": "x", "unknown": True})
    assert r.status_code == 400


def test_contradiction_between_messages_is_flagged(client):
    cid = new_case(client)["id"]
    say(client, cid, "Der Vermieter hat gekündigt. Die Klientin ist alleinige Mieterin.")
    say(
        client,
        cid,
        "Die Wohnung ist eine Ferienwohnung, die Klientin ist Untermieterin von Frau Meier.",
    )
    f = facts_of(client, cid)
    assert f["tenant_role"]["status"] == "CONTRADICTORY"
    d = decision(client, cid)
    assert "CONTRADICTORY_FACTS" in d["reason_codes"] or d["action"] == "ESCALATE"


def test_simple_answers_are_parsed_locally_without_ai_call(client, ctx):
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
    say(client, cid, STEP1)
    assert calls["n"] == 1
    say(client, cid, "Hauptmieterin", answers="tenant_role")  # enum label -> local
    say(client, cid, "Nein", answers="co_tenants_exist")  # boolean -> local
    say(client, cid, "04.11.2026", answers="receipt_date")  # date -> local
    say(client, cid, "Unklar", answers="official_form_used")  # ambiguous -> local
    assert calls["n"] == 1, "simple answers must not cost an AI call"
    f = facts_of(client, cid)
    assert f["tenant_role"]["value"] == "hauptmieterin" and f["co_tenants_exist"]["value"] is False
    assert (
        f["receipt_date"]["value"] == "2026-11-04"
        and f["official_form_used"]["status"] == "AMBIGUOUS"
    )
    say(client, cid, "Es war ein gewöhnlicher Brief ohne amtliches Kündigungsformular.")
    assert calls["n"] == 2, "free text still goes to the extractor"


# ---- C. escalation rules (YAML scenarios cover boundaries; here: semantic checks) ----------------------
def snap(facts=None, unknown=(), today=date(2026, 11, 7), issue=TT, conf=0.9):
    fs = {k: FactState(FactStatus.KNOWN, v) for k, v in (facts or {}).items()}
    fs.update({k: FactState(FactStatus.UNKNOWN) for k in unknown})
    return CaseSnapshot(True, [IssueState(IssueStatus.DETECTED, issue, conf)], fs, today)


BASE = dict(
    tenant_role="hauptmieterin",
    co_tenants_exist=False,
    object_type="wohnung",
    property_municipality="Zürich",
    property_in_canton_zh=True,
    contract_term_type="unbefristet",
    delivery_method="normale_post",
    receipt_date="2026-11-04",
    official_form_used=True,
    family_home_with_spouse=False,
    termination_kind="ordentlich",
    already_reacted=False,
)


def test_out_of_scope_cases_suppress_standard_statements_and_never_proceed(kb):
    for over in (
        {"tenant_role": "untermieterin"},
        {"object_type": "notwohnung_heim"},
        {"termination_kind": "zahlungsverzug"},
        {"eviction_or_court_proceeding": True},
    ):
        d = decide(kb, snap({**BASE, **over}))
        assert d.action == Action.ESCALATE and d.statements_suppressed
        assert d.approved_statements == [] and d.legal_findings == []


def test_in_scope_case_shows_only_source_bound_statements(kb):
    d = decide(kb, snap(BASE))
    assert d.approved_statements and all(s.source_ids for s in d.approved_statements)
    for s in d.approved_statements:
        assert all(sid in kb.sources for sid in s.source_ids)


def test_time_rules_use_internal_thresholds_only_and_unknown_dates_do_not_fire(kb):
    assert compute_derived(kb.issues[TT].derived, {}, date(2026, 11, 7)) == {
        "days_since_earliest_receipt": None,
        "days_until_termination_date": None,
    }
    d = decide(kb, CaseSnapshot(True, [IssueState(IssueStatus.DETECTED, TT, 0.9)], {}, None))
    assert not {"TT_DAYS_GE_20", "TT_DAYS_GT_30", "TT_DAYS_LT_20_ALL_KNOWN"} & set(
        d.triggered_rule_ids
    )
    assert d.derived_values["days_since_earliest_receipt"] is None


def test_internal_thresholds_are_flagged_as_product_decisions(kb):
    rules = {r.id: r for r in kb.issues[TT].escalation_rules}
    for rid in ("TT_DAYS_GE_20", "TT_DAYS_LT_20_ALL_KNOWN", "TT_MOVE_OUT_LT_60"):
        assert "PRODUKTENTSCHEID" in rules[rid].description


def test_available_related_issue_is_applied_only_if_legally_reviewed(kb, tmp_path):
    dest = tmp_path / "kb"
    shutil.copytree(REPO_ROOT / "knowledge_base", dest)
    (dest / "legal_issues" / "CH_TENANCY_PAYMENT_DEFAULT.yaml").write_text(
        yaml.safe_dump(
            dict(
                schema_version=1,
                id="CH_TENANCY_PAYMENT_DEFAULT",
                version="1",
                content_status="LEGALLY_REVIEWED",
                legal_area="tenancy",
                issue="payment_default",
                title_de="Zahlungsverzug (Test)",
                facts=[],
                default_professionals=["tenancy_law_counsel"],
            ),
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    k2 = load_knowledge_base(dest)
    assert k2.valid, k2.errors
    d = decide(k2, snap({**BASE, "termination_kind": "zahlungsverzug"}))
    route = next(r for r in d.related_routes if r.issue_id == "CH_TENANCY_PAYMENT_DEFAULT")
    assert route.available and "CH_TENANCY_PAYMENT_DEFAULT" in d.active_issue_ids
    # not reviewed -> never treated as available (the shipped KB has no such issue at all)
    d0 = decide(kb, snap({**BASE, "termination_kind": "zahlungsverzug"}))
    assert (
        not d0.related_routes[0].available
        and "CH_TENANCY_PAYMENT_DEFAULT" not in d0.active_issue_ids
    )


# ---- D. statement limits ----------------------------------------------------------------------------------
FORBIDDEN_SAMPLES = [
    "Sie haben bis am 4. Dezember 2026 Zeit.",
    "Sie haben bis 04.12.2026 Zeit, die Kündigung anzufechten.",
    "Die Kündigung ist gültig.",
    "Die Kündigung ist ungültig.",
    "Die Kündigung ist leider nichtig.",
    "Ohne Begründung ist die Kündigung ungültig.",
    "Weil der Auszug für Sie hart ist, können Sie die Kündigung anfechten.",
    "Sie waren in den Ferien, deshalb läuft die Frist später.",
    "Die Anfechtung hat gute Chancen.",
    "Sie bekommen sicher eine Erstreckung.",
    "Der Eigenbedarf ist vorgeschoben.",
    "Die Klientin muss nicht ausziehen.",
    "Das Fristende: 4.12.2026.",
]


@pytest.mark.parametrize("text", FORBIDDEN_SAMPLES)
def test_forbidden_statements_are_detected_and_replaced(kb, text):
    assert find_violations(kb, text), text
    safe, hits = sanitize(kb, text)
    assert hits and safe == kb.safe_fallback_de and safe != text


def test_all_shipped_texts_and_allowed_statements_comply_with_the_policy(kb):
    for issue in kb.issues.values():
        for lr in issue.legal_rules:
            assert lr.legal_source_ids, lr.id
            assert not find_violations(kb, lr.result_de), lr.id
        for er in issue.escalation_rules:
            assert not find_violations(kb, er.reason_de), er.id
    allowed = [lr for lr in kb.issues[TT].legal_rules if lr.kind == "HINT"]
    assert len(allowed) >= 7  # the dossier's allowed statements


def test_kb_rejects_a_forbidden_statement_in_a_rule_text(tmp_path):
    dest = tmp_path / "kb"
    shutil.copytree(REPO_ROOT / "knowledge_base", dest)
    p = Path(dest) / "legal_issues" / "CH_TENANCY_TERMINATION.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    data["escalation_rules"][0]["reason_de"] = "Die Kündigung ist ungültig."
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    k = load_knowledge_base(dest)
    assert not k.valid and any("verbotene Aussage" in e for e in k.errors)


def test_rule_without_source_is_rejected(tmp_path):
    dest = tmp_path / "kb"
    shutil.copytree(REPO_ROOT / "knowledge_base", dest)
    p = Path(dest) / "legal_issues" / "CH_TENANCY_TERMINATION.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    data["legal_rules"][0]["legal_source_ids"] = []
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert not load_knowledge_base(dest).valid


def test_ai_free_text_cannot_bypass_the_policy(client, ctx):
    from app.services.ai.mock import MockAIProvider
    from app.services.ai.schemas import ExtractionResult

    class Violating(MockAIProvider):
        def extract(self, data, c=None):
            res = super().extract(data, c)
            return ExtractionResult(
                **{
                    **res.model_dump(),
                    "summary_de": "Die Kündigung ist nichtig. Sie haben bis am 4. Dezember 2026 Zeit.",
                }
            )

    ctx.ai = Violating()
    cid = new_case(client)["id"]
    r = say(client, cid, STEP1)
    assert r["case"]["summary"] == ctx.kb.safe_fallback_de


# ---- E. sources ---------------------------------------------------------------------------------------------
def test_source_statuses_are_separated_and_never_faked(kb):
    bge = [s for s in kb.sources.values() if s.citation and s.dossier_status == "DOSSIER_CHECKED"]
    assert {s.citation for s in bge} == {
        "BGE 140 III 244 (Volltext: Urteil 4A_120/2014)",
        "BGE 143 III 15",
        "BGE 139 III 7",
        "BGE 140 III 491",
        "BGE 145 III 143",
        "BGE 142 III 91",
        "BGE 143 III 344",
        "BGE 151 III 481",
    }
    reserve = [s for s in kb.sources.values() if s.type == "case_law" and "(Reserve)" in s.title_de]
    assert len(reserve) == 6 and all(s.dossier_status == "DOSSIER_PENDING" for s in reserve)
    assert all(s.verification_status == "UNVERIFIED" for s in kb.sources.values())
    s = kb.sources["BGE_140_III_244"]
    assert s.case_number == "4A_120/2014" and s.decision_date == "2014-05-19" and s.url is None
    assert (
        kb.sources["CH_ZPO_211"].valid_as_of == "2026-07-01"
        and kb.sources["CH_OR_273_1"].valid_as_of == "2026-10-01"
    )
    assert (
        kb.sources["CH_OR_272"].dossier_status == "REFERENCED_ONLY"
        and kb.sources["CH_OR_272"].text_de is None
    )


def test_authorities_are_unverified_and_contain_no_invented_phone_numbers(kb):
    assert len(kb.authorities) == 7
    assert all(not a.contact_verified and a.verified_at is None for a in kb.authorities.values())
    blob = (REPO_ROOT / "knowledge_base" / "referrals" / "authorities.yaml").read_text(
        encoding="utf-8"
    )
    assert not re.search(r"\b0\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b|\+41", blob), (
        "no phone numbers invented"
    )


# ---- UX redesign guard: pure reading/UI endpoints never reach the AI provider ------------------------------------
def test_read_only_endpoints_never_call_the_ai_provider(client, ctx, monkeypatch):
    cid = new_case(client)["id"]
    say(client, cid, STEP1)
    calls = {"extract": 0, "rephrase": 0}
    real_extract, real_rephrase = ctx.ai.extract, ctx.ai.rephrase_question

    def counting_extract(*a, **k):
        calls["extract"] += 1
        return real_extract(*a, **k)

    def counting_rephrase(*a, **k):
        calls["rephrase"] += 1
        return real_rephrase(*a, **k)

    monkeypatch.setattr(ctx.ai, "extract", counting_extract)
    monkeypatch.setattr(ctx.ai, "rephrase_question", counting_rephrase)

    for path in (
        "",
        "/messages",
        "/facts",
        "/decisions",
        "/current-decision",
        "/briefings",
    ):
        assert client.get(f"/api/cases/{cid}{path}").status_code == 200
    assert client.get("/api/cases").status_code == 200
    assert client.get("/api/sources/fedlex/status").status_code == 200
    assert client.get("/api/knowledge-base/status").status_code == 200
    assert calls == {"extract": 0, "rephrase": 0}


def test_conditional_questions_are_not_asked_when_not_applicable(client):
    """required_if / relevance: after the facts say there is no family home, no spouse question is open."""
    cid = new_case(client)["id"]
    for step in (STEP1, STEP2, STEP3, STEP4):
        d = say(client, cid, step)["case"]["current_decision"]
    assert d["missing_facts"] == []
    assert (
        d["next_question"] is None
        or d["next_question"].get("optional")
        or d["next_question"].get("deferred")
    )
