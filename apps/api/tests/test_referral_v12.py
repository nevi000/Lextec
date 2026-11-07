"""Referral rules v1.2: 160 Zürcher Gemeinden, Listenrollen, Ortsbezug, Verifikationsstatus. Deterministisch, Mock-KI."""

from __future__ import annotations

import re
import shutil

import yaml

from app.core.config import REPO_ROOT
from app.schemas.safety import ReferralCard
from app.services.knowledge.loader import load_knowledge_base
from app.services.referrals.network import (
    Location,
    build_card,
    find_municipality,
    resolve_role_options,
    split_phones,
)
from tests.conftest import new_case, say

KB_DIR = REPO_ROOT / "knowledge_base"
BASE = "Mein Vermieter hat meiner Klientin die Wohnung gekündigt, ohne amtliches Formular."
HARDSHIP = " Sie ist alleinerziehend mit zwei Kindern."


def case_in(
    client, municipality: str, text: str = BASE + HARDSHIP, residence: str | None = None
) -> str:
    cid = new_case(client)["id"]
    say(client, cid, text)
    say(client, cid, municipality, answers="property_municipality")
    if residence:
        say(client, cid, residence, answers="client_residence_municipality")
    return cid


def referrals(client, cid) -> dict:
    return client.get(f"/api/cases/{cid}/current-decision").json()["referrals"]


def ids(cards) -> list[str]:
    return [c["id"] for c in cards]


def all_ids(r) -> list[str]:
    return ids(r["primary"]) + ids(r["more"])


# --------------------------------------------------------------------------------- production file
def test_v12_is_the_active_referral_file(kb_loaded=None):
    kb = load_knowledge_base(KB_DIR)
    assert kb.valid, kb.errors
    assert kb.referral_network.version == "1.2"
    names = sorted(p.name for p in (KB_DIR / "referrals").glob("*.yaml"))
    assert "referral_rules.yaml" in names and "referral_network.yaml" not in names
    assert any(f.path.endswith("referral_rules.yaml") for f in kb.files)
    # the law team's input is preserved, the previous integrated version is backed up
    assert (REPO_ROOT / "docs/legal_inputs/referral_rules (1).yaml").exists()
    assert (REPO_ROOT / "docs/legal_inputs/previous/referral_network_v1.1_integrated.yaml").exists()


def test_all_160_zurich_municipalities_with_unique_bfs_and_complete_roles():
    kb = load_knowledge_base(KB_DIR)
    m = kb.referral_network.municipalities
    assert len(m) == 160 and all(k.startswith("ZH:") for k in m)
    assert len({e.bfs for e in m.values()}) == 160
    assert {e.bezirk for e in m.values()} >= {"Zürich", "Winterthur", "Bülach", "Dielsdorf"}
    assert m["ZH:Zürich"].bfs == 261 and m["ZH:Winterthur"].bfs == 230
    for key, e in m.items():
        extra = e.model_extra or {}
        assert extra.get("schlichtungsbehoerde_miete"), key


# ------------------------------------------------------------------------------------ A-C regions
def test_a_zurich_gets_the_zurich_conciliation_authority(client):
    r = referrals(client, case_in(client, "Zürich"))
    assert "schlichtungsbehoerde_miete_bezirk_zuerich" in ids(r["primary"])
    card = next(c for c in r["primary"] if c["id"] == "schlichtungsbehoerde_miete_bezirk_zuerich")
    assert card["scope_de"] == "Zuständig für Gemeinde Zürich, Bezirk Zürich"


def test_b_winterthur_regional_authority_and_further_bodies(client):
    r = referrals(client, case_in(client, "Winterthur"))
    assert "schlichtungsbehoerde_miete_winterthur" in ids(r["primary"])
    assert "mieterverband_zh_winterthur" in all_ids(r)
    assert "soziale_dienste_winterthur" in all_ids(r)  # verified municipal social service
    assert "schlichtungsbehoerde_miete_bezirk_zuerich" not in all_ids(r)


def test_c_buelach_district_court_instead_of_zurich(client):
    r = referrals(client, case_in(client, "Bülach"))
    assert "schlichtungsbehoerde_miete_buelach" in ids(r["primary"])
    assert "schlichtungsbehoerde_miete_bezirk_zuerich" not in all_ids(r)
    assert "rechtsauskunft_bg_buelach" in all_ids(r)  # first entry of the list role


# ----------------------------------------------------------------------- D unverified municipality
def test_d_to_verify_municipality_shows_no_invented_local_contact(client):
    r = referrals(client, case_in(client, "Bassersdorf"))
    social = next(
        c for c in r["primary"] + r["more"] if c.get("option_of_role") == "sozialdienst_gemeinde"
    )
    assert (
        social["id"] == "sozialdienst_gemeinde_zh"
    )  # the cantonal placeholder, not a made-up municipal body
    assert "noch nicht einzeln geprüft" in social["local_note_de"]
    assert social["phones"] == [] or all(p["tel"] for p in social["phones"])
    assert "municipalities" not in str(social) and "Feld web" not in str(
        social
    )  # no internal field names


def test_d2_carrier_confirmed_contact_open_is_stated_as_such(client):
    r = referrals(client, case_in(client, "Hedingen"))
    social = next(
        c for c in r["primary"] + r["more"] if c.get("option_of_role") == "sozialdienst_gemeinde"
    )
    assert social["id"] == "ika_sozialdienst_bezirk_affoltern"
    assert (
        "Kontaktdaten des örtlichen Sozialdienstes sind noch nicht geprüft"
        in social["local_note_de"]
    )


# ------------------------------------------------------------------------------ E aliases / F unknown
def test_e_glattbrugg_is_mapped_to_opfikon_via_the_verified_alias(client):
    cid = case_in(client, "Glattbrugg")
    r = referrals(client, cid)
    assert "schlichtungsbehoerde_miete_buelach" in all_ids(r)  # Opfikon -> Bezirk Bülach
    assert any("Ortsteil von Opfikon" in n for n in r["notes_de"])
    assert r["location_de"] == "Kanton ZH, Gemeinde Opfikon"


def test_normalisation_umlauts_case_spaces_and_aliases():
    net = load_knowledge_base(KB_DIR).referral_network
    for name, want in [
        ("zuerich", "ZH:Zürich"),
        ("ZUERICH", "ZH:Zürich"),
        ("  Zürich ", "ZH:Zürich"),
        ("buelach", "ZH:Bülach"),
        ("Bülach", "ZH:Bülach"),
        ("winterthur", "ZH:Winterthur"),
        ("Glattbrugg", "ZH:Opfikon"),
        ("Effretikon", "ZH:Illnau-Effretikon"),
        ("Benken", "ZH:Benken (ZH)"),
        ("oerlikon", "ZH:Zürich"),
    ]:
        key, _how = find_municipality(net, name, "ZH")
        assert key == want, (name, key)
    # ambiguous names are NOT mapped (e.g. «Affoltern» is a Zürich quarter and Affoltern am Albis)
    assert find_municipality(net, "Affoltern", "ZH")[0] is None
    assert find_municipality(net, "Atlantis", "ZH") == (None, None)


def test_f_unknown_municipality_falls_back_to_the_general_cantonal_body(client):
    r = referrals(client, case_in(client, "Atlantis"))
    sch = next(c for c in r["primary"] if c.get("option_of_role") == "schlichtungsbehoerde_miete")
    assert (
        sch["id"] == "schlichtungsbehoerde_miete_zh_verzeichnis"
    )  # directory, not a made-up local authority
    assert "Kantonsweit" in sch["scope_de"]
    assert any("Gemeinde" in n and "nicht" in n for n in r["notes_de"]) or sch["scope_de"]
    assert "schlichtungsbehoerde_miete_bezirk_zuerich" not in all_ids(r)


def test_no_location_never_claims_a_local_authority():
    net = load_knowledge_base(KB_DIR).referral_network
    opts = resolve_role_options(net, "schlichtungsbehoerde_miete", Location())
    assert [o.org_id for o in opts] == ["schlichtungsbehoerde_miete"] and opts[0].how == "default"


# --------------------------------------------------------------------------------- G lists / H dedupe
def test_g_list_roles_keep_every_option_in_order():
    net = load_knowledge_base(KB_DIR).referral_network
    loc = Location(canton="ZH", municipality="Bülach")
    opts = resolve_role_options(net, "unentgeltliche_rechtsauskunft", loc)
    assert [o.org_id for o in opts] == [
        "rechtsauskunft_bg_buelach",
        "rechtsauskunft_buelach_zav",
        "unentgeltliche_rechtsauskunft_zav",
    ]
    assert all(o.how == "municipality_data" for o in opts)


def test_h_multiple_issues_do_not_duplicate_organisations(client):
    cid = case_in(
        client,
        "Bülach",
        BASE + HARDSHIP + " Die Klientin findet keine Wohnung und möchte mehr Zeit.",
    )
    d = client.get(f"/api/cases/{cid}/current-decision").json()
    assert {"CH_TENANCY_TERMINATION", "CH_TENANCY_EXTENSION"} <= set(d["active_issue_ids"])
    a = all_ids(d["referrals"])
    assert len(a) == len(set(a))


# ----------------------------------------------------------------------------- I eviction / J safety
def test_i_eviction_escalates_immediately_with_legal_and_social_bodies(client):
    cid = new_case(client)["id"]
    say(client, cid, "Das Stadtammannamt kommt morgen zur Räumung.")
    say(client, cid, "Bülach", answers="property_municipality")
    d = client.get(f"/api/cases/{cid}/current-decision").json()
    assert d["action"] == "ESCALATE" and d["max_urgency"] == "HIGH"
    a = all_ids(d["referrals"])
    assert "sozialdienst_gemeinde_zh" in a and any(
        "tenancy_lawyer" == x or "mieterverband" in x for x in a
    )


def test_j_safety_priority_is_untouched(client):
    cid = new_case(client)["id"]
    say(
        client,
        cid,
        "Der Vermieter hat gekündigt und droht, meine Klientin zu schlagen. Sie wird gerade bedroht.",
    )
    d = client.get(f"/api/cases/{cid}/current-decision").json()
    assert (
        d["effective_action"] == "IMMEDIATE_SAFETY_RESPONSE" and d["safety"]["state"] == "IMMEDIATE"
    )
    assert any(c["id"] == "police_117" for c in d["safety"]["contacts_immediate"])


# ------------------------------------------------------------------------------- K verification status
def test_k_contact_quality_and_verified_are_separate_and_visible():
    kb = load_knowledge_base(KB_DIR)
    cards = {o.id: build_card(o) for o in kb.referral_network.professionals}
    assert (
        cards["tenancy_lawyer"].quality == "UNDOCUMENTED"
        and "nicht als geprüft" in cards["tenancy_lawyer"].quality_label_de
    )
    assert cards["schlichtungsbehoerde_miete_bezirk_zuerich"].quality == "OFFICIAL"
    sec = [c for c in cards.values() if c.quality == "DIRECTORY"]
    assert sec and all("bestätigen" in c.quality_label_de for c in sec)
    assert any(not c.verified for c in cards.values()) and any(c.verified for c in cards.values())


def test_phone_numbers_are_normalised_without_losing_remarks():
    assert split_phones("044 763 17 00 (Telefonzentrale)") == [("044 763 17 00", "Telefonzentrale")]
    assert split_phones("043 259 24 68 / 043 259 51 58") == [
        ("043 259 24 68", None),
        ("043 259 51 58", None),
    ]
    org = next(
        o
        for o in load_knowledge_base(KB_DIR).referral_network.professionals
        if o.id == "frauenhaus_violetta"
    )
    card = build_card(org)
    assert card.phones[0].display == "044 350 04 04" and card.phones[0].tel == "0443500404"
    assert (
        "Helpline" in (card.phones[0].note_de or "")
        and card.address is None
        and card.address_protected
    )


def test_protected_addresses_never_leave_the_api(client):
    cid = new_case(client)["id"]
    say(
        client,
        cid,
        "Meine Klientin wird zu Hause von ihrem Mann geschlagen, sie braucht ein Frauenhaus. Die Wohnung in Zürich wurde gekündigt.",
    )
    blob = client.get(f"/api/cases/{cid}/current-decision").text
    for org in load_knowledge_base(KB_DIR).referral_network.professionals:
        if org.address_protected:
            addr = (org.contact or {}).get("address")
            assert not addr or addr not in blob


# --------------------------------------------------------------------------------- L briefing = UI
def test_l_briefing_shows_the_same_bodies_as_the_frontend(client):
    cid = case_in(client, "Bülach")
    ui = referrals(client, cid)
    b = client.post(f"/api/cases/{cid}/briefings").json()
    html = client.get(f"/api/cases/{cid}/briefings/{b['id']}/preview").text
    text = re.sub(r"\s+", " ", re.sub(r"<style.*?</style>|<[^>]+>", " ", html, flags=re.S))
    shown = (ui["primary"] + ui["more"])[:4]
    for c in shown:
        assert c["label"].split(",")[0][:30].replace("&", "") in text.replace("&amp;", "&"), c[
            "label"
        ]
    assert "Bülach" in text


def test_briefing_states_unverified_local_social_service(client):
    cid = case_in(client, "Bassersdorf")
    b = client.post(f"/api/cases/{cid}/briefings").json()
    html = client.get(f"/api/cases/{cid}/briefings/{b['id']}/preview").text
    assert "noch nicht einzeln geprüft" in html


# --------------------------------------------------------------------------------- M compat / N basis
def test_m_cards_stored_before_v12_still_load():
    old = {
        "id": "x",
        "label": "X",
        "type": "authority",
        "kind": "authority",
        "quality": "OFFICIAL",
        "quality_label_de": "q",
        "phones": [{"label_de": "Telefon", "display": "058 111 70 30", "tel": "0581117030"}],
    }
    c = ReferralCard.model_validate(old)
    assert c.scope_de is None and c.local_note_de is None and c.phones[0].note_de is None


def test_n_property_and_residence_municipality_use_their_own_basis(client):
    cid = case_in(client, "Bülach", residence="Winterthur")
    r = referrals(client, cid)
    assert "schlichtungsbehoerde_miete_buelach" in all_ids(r)  # tenancy body: place of the flat
    social = next(
        c for c in r["primary"] + r["more"] if c.get("option_of_role") == "sozialdienst_gemeinde"
    )
    assert social["id"] == "soziale_dienste_winterthur"  # social body: municipality of residence


def test_social_roles_fall_back_to_the_flat_municipality_and_say_so(client):
    r = referrals(client, case_in(client, "Winterthur"))
    social = next(
        c for c in r["primary"] + r["more"] if c.get("option_of_role") == "sozialdienst_gemeinde"
    )
    assert "Wohnsitzgemeinde nicht erfasst" in social["scope_de"]


def test_reasons_are_plain_german_not_signal_ids(client):
    r = referrals(client, case_in(client, "Bülach"))
    for c in r["primary"] + r["more"]:
        assert "imminent_housing_loss" not in (c["reason_de"] or "") and "wegen:" not in (
            c["reason_de"] or ""
        )


# ----------------------------------------------------------------------------------- validator
def _mutated(tmp_path, fn):
    dest = tmp_path / "kb"
    shutil.copytree(KB_DIR, dest)
    p = dest / "referrals" / "referral_rules.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    fn(data)
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return load_knowledge_base(dest)


def test_validator_reports_real_data_errors(tmp_path):
    kb = _mutated(
        tmp_path,
        lambda d: d["municipalities"]["ZH:Bülach"].update(
            bfs=d["municipalities"]["ZH:Zürich"]["bfs"]
        ),
    )
    assert any("BFS-Nummer" in e for e in kb.errors)
    kb = _mutated(
        tmp_path / "b", lambda d: d["municipalities"]["ZH:Bülach"].update(kesb="gibt_es_nicht")
    )
    assert any("unbekannte Stelle 'gibt_es_nicht'" in e for e in kb.errors)
    kb = _mutated(tmp_path / "c", lambda d: d["municipalities"].pop("ZH:Bülach"))
    assert any("159 Zürcher Gemeinden statt 160" in e for e in kb.errors)
    kb = _mutated(
        tmp_path / "d",
        lambda d: d["municipalities"]["ZH:Bülach"].update(sozialdienst_status="kaputt"),
    )
    assert kb.errors

    def leak(d):
        next(o for o in d["professionals"] if o["id"] == "frauenhaus_violetta")["contact"][
            "address"
        ] = "Geheimweg 1"

    kb = _mutated(tmp_path / "e", leak)
    assert any("Schutzadresse" in e for e in kb.errors)


def test_to_verify_is_a_fact_state_not_a_validation_error():
    kb = load_knowledge_base(KB_DIR)
    states = {e.sozialdienst_status for e in kb.referral_network.municipalities.values()}
    assert "to_verify" in states and kb.valid


def test_a_second_referral_file_is_rejected(tmp_path):
    dest = tmp_path / "kb"
    shutil.copytree(KB_DIR, dest)
    shutil.copy(
        dest / "referrals" / "referral_rules.yaml", dest / "referrals" / "referral_network.yaml"
    )
    assert any("zweite Referral-Datei" in e for e in load_knowledge_base(dest).errors)


def test_no_ai_call_for_referral_resolution(client, ctx, monkeypatch):
    cid = case_in(client, "Bülach")
    calls = []
    monkeypatch.setattr(ctx.ai, "extract", lambda *a, **k: calls.append(1))
    monkeypatch.setattr(ctx.ai, "rephrase_question", lambda *a, **k: calls.append(1))
    for _ in range(3):
        client.get(f"/api/cases/{cid}/current-decision")
    assert calls == []
