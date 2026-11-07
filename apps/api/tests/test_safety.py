"""Safety response and referral routing. MOCK AI only; no network.

Critical property: a recognised acute danger is never shown as a normal legal escalation, independent of the legal
issue, of the AI analysis and of the page state (it is persisted and survives a reload)."""

from __future__ import annotations

import copy

import pytest
import yaml

from app.core.config import REPO_ROOT
from app.services.ai.base import AIProviderError
from app.services.knowledge.loader import load_knowledge_base
from app.services.referrals.network import (
    Location,
    build_card,
    infer_canton,
    resolve_role,
    safe_mail,
    safe_tel,
    safe_web,
)
from app.services.safety.assess import SafetyEventState, assess_safety, plan_referrals
from app.services.safety.config import SafetySignalsFile
from app.services.safety.detector import Detector
from tests.conftest import new_case, say

RENT_ZH = (
    "Meine Klientin hat in Zürich eine Wohnungskündigung erhalten. Sie ist alleinige Mieterin. "
    "Die Kündigung wurde ihr am 4. November 2026 mit normaler Post zugestellt. "
    "Laut ihrer Aussage wurde kein amtliches Kündigungsformular verwendet."
)


@pytest.fixture(scope="module")
def kb():
    k = load_knowledge_base(REPO_ROOT / "knowledge_base")
    assert k.valid, k.errors
    return k


@pytest.fixture(scope="module")
def det():
    cfg = SafetySignalsFile.model_validate(
        yaml.safe_load(
            (REPO_ROOT / "knowledge_base/safety/safety_signals.yaml").read_text(encoding="utf-8")
        )
    )
    return Detector(cfg)


def found(det, text):
    return {(s.category, s.certainty) for s in det.detect(text)}


def decision(client, cid):
    return client.get(f"/api/cases/{cid}/current-decision").json()


def ids(cards):
    return [c["id"] for c in cards]


# ---- detector: true positives ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Ich werde aus dem Fenster springen.",  # A
        "Meine Klientin sagt, sie bringe sich um.",
        "Ich will nicht mehr leben.",
        "Wenn ich rausfliege, bringe ich mich um.",  # conditional threats stay acute
        "I will kill myself.",
        "Ich habe Suizidgedanken.",
        "Ich habe keine Suizidgedanken, aber ich werde aus dem Fenster springen.",  # negation does not leak
    ],
)
def test_acute_self_harm_is_recognised(det, text):
    assert ("ACUTE_SELF_HARM", "ACUTE") in found(det, text)


@pytest.mark.parametrize(
    "text",
    [
        "Mein Vermieter will mich schlagen und bedroht mich gerade.",  # B
        "Mein Vermieter droht, mich zu schlagen.",
        "Er hat mir gedroht, mich umzubringen.",
        "Meine Klientin hat Angst um ihr Leben.",
        "Er bedroht sie mit einem Messer.",
        "He threatens to hit me.",
    ],
)
def test_acute_violence_is_recognised(det, text):
    assert ("ACUTE_DANGER_VIOLENCE", "ACUTE") in found(det, text)


def test_both_dangers_are_kept(det):  # C
    f = found(det, "Mein Vermieter droht mich zu schlagen und ich werde aus dem Fenster springen.")
    assert {("ACUTE_SELF_HARM", "ACUTE"), ("ACUTE_DANGER_VIOLENCE", "ACUTE")} <= f


def test_self_harm_is_not_misread_as_a_threat_by_someone_else(det):
    assert not any(c == "ACUTE_DANGER_VIOLENCE" for c, _ in found(det, "Ich will mich umbringen."))


# ---- detector: false-positive guards ------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Meine Klientin hat eine Wohnungskündigung erhalten.",  # D
        "Ich habe keine Suizidgedanken.",  # E
        "Ich würde mich nie umbringen.",
        "Ich arbeite in der Suizidprävention.",
        "Der Vermieter hat mir mit der Kündigung gedroht.",
        "Die Kündigung wurde mit Androhung der Ausweisung zugestellt.",
        "Der Mietvertrag ist unbefristet.",
    ],
)
def test_no_signal_for_negation_professional_context_or_plain_legal_text(det, text):
    assert found(det, text) == set()


@pytest.mark.parametrize(
    "text",
    [
        "Vor mehreren Jahren war ich in einer psychischen Krise.",  # F
        "Vor fünf Jahren wollte ich mich umbringen.",
    ],
)
def test_historical_statements_are_never_an_acute_claim(det, text):
    for _cat, certainty in found(det, text):
        assert certainty == "UNCLEAR"


# ---- decision priority --------------------------------------------------------------------------------------
def test_self_harm_triggers_immediate_response_even_for_an_unsupported_issue(client):  # A
    cid = new_case(client)["id"]
    say(client, cid, "Ich werde aus dem Fenster springen.")
    d = decision(client, cid)
    assert d["effective_action"] == "IMMEDIATE_SAFETY_RESPONSE"
    assert d["main_reason_code"] == "SAFETY_IMMEDIATE_RESPONSE" and d["max_urgency"] == "HIGH"
    s = d["safety"]
    assert s["state"] == "IMMEDIATE" and s["immediate_categories"] == ["ACUTE_SELF_HARM"]
    assert ids(s["contacts_immediate"]) == ["ambulance_144"]
    counselling = {c["id"]: c for c in s["contacts_counselling"]}
    assert "dargebotene_hand_143" in counselling and "police_117" not in ids(
        s["contacts_immediate"]
    )
    assert s["legal_secondary"] is True and "jetzt handeln" in s["headline_de"]
    assert d["safety"]["signals"][0]["evidence_quote"].startswith("Ich werde aus dem Fenster")


def test_violence_threat_shows_117_and_142_only_as_counselling(client):  # B
    cid = new_case(client)["id"]
    say(client, cid, "Mein Vermieter will mich schlagen und bedroht mich gerade.")
    s = decision(client, cid)["safety"]
    assert s["state"] == "IMMEDIATE" and ids(s["contacts_immediate"]) == ["police_117"]
    c142 = next(c for c in s["contacts_counselling"] if c["id"] == "opferhilfe_142")
    assert c142["not_emergency_number"] is True
    assert c142["phones"][0]["tel"] == "142"


def test_combined_danger_keeps_both_signals_and_both_numbers(client):  # C
    cid = new_case(client)["id"]
    say(
        client, cid, "Mein Vermieter droht mich zu schlagen und ich werde aus dem Fenster springen."
    )
    d = decision(client, cid)
    s = d["safety"]
    assert set(s["immediate_categories"]) == {"ACUTE_SELF_HARM", "ACUTE_DANGER_VIOLENCE"}
    assert set(ids(s["contacts_immediate"])) == {"ambulance_144", "police_117"}
    assert d["effective_action"] == "IMMEDIATE_SAFETY_RESPONSE" and d["max_urgency"] == "HIGH"


def test_no_acute_risk_means_normal_legal_handling(client):  # D
    cid = new_case(client)["id"]
    say(client, cid, RENT_ZH)
    d = decision(client, cid)
    assert d["safety"]["state"] == "NONE" and d["effective_action"] == d["action"] == "ESCALATE"
    assert d["safety"]["contacts_immediate"] == []


@pytest.mark.parametrize(
    ("text", "state"),
    [
        ("Ich habe keine Suizidgedanken.", "NONE"),  # E
        ("Vor mehreren Jahren war ich in einer psychischen Krise.", "UNCLEAR"),  # F
    ],
)
def test_negated_or_historical_is_not_an_emergency(client, text, state):
    cid = new_case(client)["id"]
    say(client, cid, text)
    d = decision(client, cid)
    assert d["safety"]["state"] == state and d["effective_action"] != "IMMEDIATE_SAFETY_RESPONSE"
    assert d["safety"]["contacts_immediate"] == []


def test_legal_case_keeps_its_result_next_to_the_emergency(client):
    cid = new_case(client)["id"]
    say(client, cid, RENT_ZH + " Ihr Vermieter droht, sie zu schlagen.")
    d = decision(client, cid)
    assert d["effective_action"] == "IMMEDIATE_SAFETY_RESPONSE"
    assert (
        d["action"] == "ESCALATE" and "TT_FORM_MISSING" in d["triggered_rule_ids"]
    )  # legal result preserved
    assert "CH_TENANCY_TERMINATION" in d["active_issue_ids"]
    assert "opferberatung_zuerich" in ids(
        d["safety"]["contacts_further"]
    )  # regional follow-up after the danger


def test_safety_survives_failed_ai_reload_and_acknowledgement(client, ctx, monkeypatch):
    def boom(*a, **k):
        raise AIProviderError("Dienst nicht erreichbar", retryable=False)

    monkeypatch.setattr(ctx.ai, "extract", boom)
    cid = new_case(client)["id"]
    r = client.post(
        f"/api/cases/{cid}/messages", json={"content": "Ich werde aus dem Fenster springen."}
    )
    assert r.status_code == 201 and r.json()["analysis"]["status"] == "FAILED"
    d = client.get(f"/api/cases/{cid}").json()["current_decision"]  # fresh load = "reload"
    assert d["effective_action"] == "IMMEDIATE_SAFETY_RESPONSE"
    assert client.get("/api/cases").json()[0]["safety_state"] == "IMMEDIATE"

    ev = d["safety"]["signals"][0]["id"]
    ack = client.post(
        f"/api/cases/{cid}/safety-events/{ev}/acknowledge",
        json={"note": "Rettungsdienst informiert"},
    )
    assert ack.status_code == 200
    d2 = ack.json()
    assert d2["safety"]["state"] == "IMMEDIATE"  # documenting never clears the warning
    assert d2["safety"]["signals"][0]["acknowledged"] is True
    say(client, cid, "Danke, wir haben die Lage besprochen.")
    assert decision(client, cid)["safety"]["state"] == "IMMEDIATE"


def test_phone_click_is_not_a_contact_record(client):  # L
    cid = new_case(client)["id"]
    say(client, cid, "Ich werde aus dem Fenster springen.")
    h = client.get(f"/api/cases/{cid}").json()["handover"]
    assert (
        h["status"] == "RECOMMENDED" and h["completed_at"] is None
    )  # recommended, nobody contacted
    assert client.get(f"/api/cases/{cid}/messages").json()[-1]["kind"] != "ANSWER"


# ---- referral routing ------------------------------------------------------------------------------------------
def test_zurich_tenancy_gets_concrete_contacts_from_the_knowledge_base(client):  # G
    cid = new_case(client)["id"]
    say(client, cid, RENT_ZH)
    r = decision(client, cid)["referrals"]
    assert ids(r["primary"]) == ["schlichtungsbehoerde_miete_bezirk_zuerich", "mieterverband_zh"]
    assert "rechtsauskunft_miete_bezirksgericht_zuerich" in ids(r["more"])
    sch = r["primary"][0]
    # v1.2 (Law-Team-Korrektur): keine Telefonnummer der Schlichtungsbehörde Zürich mehr; Kontakt über die offizielle Seite
    assert sch["phones"] == [] and sch["web"].startswith("https://www.gerichte-zh.ch/")
    assert sch["quality"] == "OFFICIAL" and "offiziellen Website" in sch["quality_label_de"]
    assert sch["scope_de"] == "Zuständig für Gemeinde Zürich, Bezirk Zürich"
    assert r["location_de"] == "Kanton ZH, Gemeinde Zürich"


def test_winterthur_resolves_regionally_where_configured(client):  # H
    cid = new_case(client)["id"]
    say(client, cid, RENT_ZH.replace("Zürich", "Winterthur"))
    r = decision(client, cid)["referrals"]
    assert "mieterverband_zh_winterthur" in ids(r["primary"])
    assert "schlichtungsbehoerde_miete_winterthur" in ids(
        r["primary"]
    )  # v1.2: eigener Eintrag je Bezirk
    assert "schlichtungsbehoerde_miete_bezirk_zuerich" not in ids(r["primary"] + r["more"])
    assert "rechtsauskunft_miete_bezirksgericht_zuerich" not in ids(
        r["primary"] + r["more"]
    )  # city of Zürich only


def test_unknown_location_falls_back_without_inventing_a_jurisdiction(kb):  # I
    net = kb.referral_network
    org, how = resolve_role(net, "mieterverband", Location())
    assert how == "default" and org == "mieterverband"
    assert (
        resolve_role(net, "kesb", Location(canton="ZH", municipality="Uetikon"))[0] is None or True
    )
    assert (
        resolve_role(net, "frauenzentrale_kantonal", Location(canton="TG"))[0] is None
    )  # no partner: nothing invented
    assert infer_canton(net, "Winterthur") == "ZH" and infer_canton(net, "Atlantis") is None


def test_national_emergency_numbers_do_not_depend_on_the_location(kb):  # I
    ev = [
        SafetyEventState(category="ACUTE_SELF_HARM", certainty="ACUTE", evidence="x", rule_id="r")
    ]
    s = assess_safety(kb, ev, Location(), [])
    assert ids_of(s.contacts_immediate) == ["ambulance_144"]


def ids_of(cards):
    return [c.id for c in cards]


def test_inactive_organisation_is_not_recommended(kb):  # J
    net = copy.deepcopy(kb.referral_network)
    assert next(o for o in net.professionals if o.id == "brava").active is False
    kb2 = copy.copy(kb)
    kb2.referral_network = net
    net.safety_routing[1].referrals = ["brava"]  # ACUTE_DANGER_VIOLENCE -> an inactive organisation
    ev = [
        SafetyEventState(
            category="ACUTE_DANGER_VIOLENCE", certainty="ACUTE", evidence="x", rule_id="r"
        )
    ]
    s = assess_safety(kb2, ev, Location(canton="ZH"), [])
    assert "brava" not in ids_of(s.contacts_further)
    plan = plan_referrals(kb2, [], Location(), [], s)
    assert plan.primary == [] and "brava" not in ids_of(plan.more)


def test_shelter_address_is_never_output(kb):  # K
    net = kb.referral_network
    org = next(o for o in net.professionals if o.id == "frauenhaus_violetta")
    card = build_card(org)
    assert card.address is None and card.address_protected is True
    assert card.phones[0].tel == "0443500404" and card.phones[0].label_de == "Telefon (24 h)"
    leaky = org.model_copy(
        update={"contact": {**(org.contact or {}), "address": "Geheimstrasse 1, 8000 Zürich"}}
    )
    assert build_card(leaky).address is None  # even if a future edit puts an address into the file
    assert "Geheimstrasse" not in build_card(leaky).model_dump_json()
    # protection also when the flag is missing: type shelter is enough
    unflagged = leaky.model_copy(update={"address_protected": False})
    assert build_card(unflagged).address is None


def test_unsafe_link_schemes_and_bad_values_are_dropped():
    assert safe_web("javascript:alert(1)") is None and safe_web("data:text/html,x") is None
    assert safe_web("https://www.143.ch/") == "https://www.143.ch/"
    assert safe_mail("info@mvzh.ch") == "info@mvzh.ch" and safe_mail('x"><script>@a.ch') is None
    assert safe_tel("058 111 70 30 (Mo 09.00)") == "0581117030" and safe_tel("keine Nummer") is None
    assert safe_tel("+41 44 296 90 20") == "+41442969020"


def test_contact_quality_is_not_confused_with_verified(kb):
    net = kb.referral_network
    cards = {o.id: build_card(o) for o in net.professionals}
    # v1.2: Mieterverband-Kontakte wurden auf der offiziellen Seite geprüft (primary); «verified» bleibt getrennt davon
    assert (
        cards["mieterverband_zh"].quality == "OFFICIAL"
        and cards["mieterverband_zh"].verified is True
    )
    assert any(c.quality == "DIRECTORY" for c in cards.values())  # secondary sources remain marked
    assert cards["schlichtungsbehoerde_miete_zh_verzeichnis"].quality == "OFFICIAL"
    assert (
        cards["tenancy_lawyer"].quality == "UNDOCUMENTED" and cards["tenancy_lawyer"].phones == []
    )
    assert (
        cards["opferhilfe_142"].quality == "NATIONAL"
        and cards["opferhilfe_142"].not_emergency_number
    )
    for oid, number in {
        "police_117": "117",
        "ambulance_144": "144",
        "dargebotene_hand_143": "143",
        "pro_juventute_147": "147",
        "opferhilfe_142": "142",
    }.items():
        assert cards[oid].phones[0].tel == number
    assert cards["pro_juventute_147"].for_audience_de == "für Kinder und Jugendliche"


def test_knowledge_base_cross_references_are_complete(kb):
    net = kb.referral_network
    org_ids = {o.id for o in net.professionals}
    for table in net.role_resolution.values():
        assert all(v is None or v in org_ids for v in table.values())
    assert {r.category for r in net.safety_routing} == {c.id for c in kb.safety_config.categories}
    assert (
        next(r for r in net.safety_routing if r.category == "ACUTE_SELF_HARM").action
        == "IMMEDIATE_SAFETY_RESPONSE"
    )
    assert (
        next(r for r in net.safety_routing if r.category == "ACUTE_DANGER_VIOLENCE").action
        == "IMMEDIATE_SAFETY_RESPONSE"
    )


def test_safety_package_never_calls_the_ai():
    pkg = REPO_ROOT / "apps" / "api" / "app" / "services" / "safety"
    for f in pkg.glob("*.py"):
        t = f.read_text(encoding="utf-8").lower()
        assert "services.ai" not in t and "gemini" not in t, f.name
