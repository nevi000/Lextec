"""Fedlex integration - FIXTURE/MOCK tests only: no real network, no Gemini.

The XML documents here are built from trimmed copies of REAL Fedlex snapshots (tests/fixtures/fedlex).
Anything that must hit the real service lives in `python -m app.cli fedlex live-test`, never in this file.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from app.core.config import REPO_ROOT, Settings
from app.db.base import Base
from app.db.session import make_engine, make_session_factory
from app.models.tables import SourceSnapshot
from app.services.knowledge.loader import load_knowledge_base
from app.services.sources.fedlex import catalog
from app.services.sources.fedlex.akn import (
    AknDocument,
    ArticleNotFound,
    compare_wording,
    normalize_for_compare,
)
from app.services.sources.fedlex.fixtures import FIXTURE_FILE, seed_fixtures
from app.services.sources.fedlex.http import (
    FedlexBadResponse,
    FedlexDisabled,
    FedlexForbiddenUrl,
    FedlexHttp,
    FedlexHttpError,
    FedlexNetworkError,
    FedlexTooLarge,
)
from app.services.sources.fedlex.provider import CachedFedlexProvider
from app.services.sources.fedlex.reference import ReferenceError_, parse_article, parse_reference
from app.services.sources.fedlex.service import FedlexService
from tests.conftest import new_case, say

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
ABSTRACT = "https://fedlex.data.admin.ch/eli/cc/27/317_321_377"
VERSION = f"{ABSTRACT}/20261001"
XML_URL = "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/27/317_321_377/20261001/de/xml/or.xml"
FIX = json.loads(Path(FIXTURE_FILE).read_text(encoding="utf-8"))


def _article_xml(snap: dict) -> str:
    """Akoma Ntoso article from a stored snapshot structure (paragraphs, letters)."""
    paras = []
    for p in snap["structure"]:
        items = "".join(
            f'<item eId="{i["eid"]}"><num>{i["label"]}</num><p>{i["text"]}</p></item>'
            for i in p["items"]
        )
        body = (
            f"<content><p>{p['text']}</p></content>"
            if not items
            else f"<intro><p>{p['text']}</p></intro>{items}"
        )
        paras.append(f'<paragraph eId="{p["eid"]}"><num>{p["num"]}</num>{body}</paragraph>')
    num = "Art. " + snap["article"]
    return f'<article eId="{snap["article_eid"]}"><num>{num}</num><heading>{snap["heading"] or ""}</heading>{"".join(paras)}</article>'


def build_xml(
    version_uri: str = VERSION, snaps: list[dict] | None = None, extra: str = ""
) -> bytes:
    arts = "".join(
        _article_xml(s) for s in (snaps if snaps is not None else FIX) if s["sr_number"] == "220"
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><akomaNtoso xmlns="{AKN_NS}"><act><meta><identification>'
        f'<FRBRWork><FRBRuri value="{version_uri}"/><FRBRdate name="jolux:dateApplicability" date="2026-10-01"/>'
        f"</FRBRWork></identification></meta><body>{arts}{extra}</body></act></akomaNtoso>"
    ).encode()


class FakeFedlex:
    """httpx transport imitating the SPARQL endpoint + filestore. Records every request."""

    def __init__(self, *, candidates=None, versions=None, xml_url=XML_URL, xml=None, fail=None):
        self.candidates = (
            candidates
            if candidates is not None
            else [
                {
                    "abs": ABSTRACT,
                    "dentry": "1912-01-01",
                    "abbr": "OR",
                    "title": "Obligationenrecht",
                }
            ]
        )
        self.versions = (
            versions
            if versions is not None
            else [
                {"cons": VERSION, "dstart": "2026-10-01", "dend": "2027-06-30"},
                {"cons": f"{ABSTRACT}/20270701", "dstart": "2027-07-01"},
                {"cons": f"{ABSTRACT}/20250101", "dstart": "2025-01-01", "dend": "2026-09-30"},
            ]
        )
        self.xml_url = xml_url
        self.xml = xml if xml is not None else build_xml()
        self.fail = fail
        self.requests: list[httpx.Request] = []
        self.bodies: list[str] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        if self.fail:
            return self.fail(req)
        if req.url.path.startswith("/filestore/"):
            return httpx.Response(200, content=self.xml)
        q = parse_qs(req.content.decode())["query"][0]
        self.bodies.append(q)
        if "historicalLegalId" in q:
            rows = self.candidates
        elif "isMemberOf" in q:
            rows = self.versions
        else:
            rows = [{"url": self.xml_url}] if self.xml_url else []
        out = {
            "results": {
                "bindings": [
                    {k: {"type": "literal", "value": v} for k, v in r.items()} for r in rows
                ]
            }
        }
        return httpx.Response(200, json=out)

    @property
    def sparql_count(self) -> int:
        return len(self.bodies)


@pytest.fixture(scope="module")
def kb():
    k = load_knowledge_base(REPO_ROOT / "knowledge_base")
    assert k.valid, k.errors
    return k


@pytest.fixture
def fsettings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        ai_provider="mock",
        gemini_api_key=None,
        app_today=date(2026, 11, 7),
        database_url=f"sqlite:///{(tmp_path / 'f.db').as_posix()}",
        knowledge_base_dir=REPO_ROOT / "knowledge_base",
        fedlex_min_request_interval_seconds=0.0,
        fedlex_max_retries=2,
        _env_file=None,
    )


@pytest.fixture
def sf(fsettings):
    eng = make_engine(fsettings.database_url)
    Base.metadata.create_all(eng)
    return make_session_factory(eng)


def make_http(settings, fake: FakeFedlex, sleeps=None) -> FedlexHttp:
    return FedlexHttp(
        settings,
        transport=httpx.MockTransport(fake),
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
    )


def make_service(settings, sf, kb, fake: FakeFedlex) -> FedlexService:
    return FedlexService(sf, settings, kb, make_http(settings, fake))


REF = date(2026, 11, 7)
OR_IDS = ["CH_OR_266L", "CH_OR_266O", "CH_OR_273_1", "CH_OR_271"]


# ---- reference parsing ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("art", "eid", "label"),
    [
        ("266l", "art_266_l", "Art. 266l"),
        ("271a", "art_271_a", "Art. 271a"),
        ("273", "art_273", "Art. 273"),
        ("113", "art_113", "Art. 113"),
        ("266o", "art_266_o", "Art. 266o"),
    ],
)
def test_letter_suffix_articles(art, eid, label):
    r = parse_reference(art)
    assert (r.eid, r.label) == (eid, label)


def test_neighbours_are_distinct():
    assert len({parse_reference(a).eid for a in ("266", "266l", "266m")}) == 3
    assert parse_reference("271").eid != parse_reference("271a").eid


def test_paragraph_and_letter_parsing():
    r = parse_reference("113", "Abs. 2 lit. c", None)
    assert (r.para_from, r.letter) == (2, "c")
    assert parse_reference("271a", "Abs. 1", None).para_from == 1
    with pytest.raises(ReferenceError_):
        parse_article("2 66")
    with pytest.raises(ReferenceError_):
        parse_article("")


# ---- AKN parsing -----------------------------------------------------------------------------------------
def test_extract_article_paragraph_and_letter():
    doc = AknDocument(build_xml())
    a = doc.extract(parse_reference("266l"))
    assert a.label.startswith("Art. 266") and "schriftlich kündigen" in a.full_text
    p = doc.extract(parse_reference("273", "Abs. 1", None))
    assert p.selected_text.startswith("1 Will eine Partei") and "Abs" not in p.selected_text[:5]
    assert "271" not in doc.extract(parse_reference("266o")).selected_text[:10]


def test_missing_article_is_not_guessed():
    with pytest.raises(ArticleNotFound):
        AknDocument(build_xml()).extract(parse_reference("266zz"))


def test_paragraph_not_present():
    with pytest.raises(ArticleNotFound):
        AknDocument(build_xml()).extract(parse_reference("273", "Abs. 9", None))


def test_footnotes_are_not_statute_text():
    snap = dict(next(s for s in FIX if s["source_id"] == "CH_OR_266L"))
    snap["structure"] = [
        {
            "num": "1",
            "eid": "art_266_l/para_1",
            "text": "Text<authorialNote><p>FUSSNOTE</p></authorialNote>",
            "items": [],
        }
    ]
    art = AknDocument(build_xml(snaps=[snap])).extract(parse_reference("266l"))
    assert "FUSSNOTE" not in art.full_text


@pytest.mark.parametrize("raw", [b"", b"<not xml", b"<html></html>", b"<akomaNtoso xmlns='x'/>"])
def test_bad_or_incomplete_xml_is_rejected(raw):
    with pytest.raises(FedlexBadResponse):
        AknDocument(raw)


def test_xml_external_entities_are_blocked():
    evil = b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><akomaNtoso>&x;</akomaNtoso>'
    with pytest.raises(FedlexBadResponse):
        AknDocument(evil)


# ---- wording comparison ---------------------------------------------------------------------------------
def test_wording_normalisation_and_honest_mismatch():
    art = AknDocument(build_xml()).extract(parse_reference("273"))
    assert normalize_for_compare("«Will  eine Partei» – x") == "'Will eine Partei' - x"
    assert compare_wording("«Will eine Partei die Kündigung anfechten»", art)["status"] == "MATCHED"
    different = compare_wording("«Will eine Partei die Kündigung innert 90 Tagen anfechten»", art)
    assert different["status"] == "MISMATCH" and different["missing"]
    assert compare_wording("kein Zitat hier", art)["status"] == "NO_COMPARABLE_TEXT"


# ---- version / candidate selection -------------------------------------------------------------------------
def v(uri_id, a, b=None):
    return catalog.LawVersion(f"{ABSTRACT}/{uri_id}", a, b)


def test_version_current_historical_future():
    vs = [
        v("20270701", "2027-07-01"),
        v("20261001", "2026-10-01", "2027-06-30"),
        v("20250101", "2025-01-01", "2026-09-30"),
    ]
    assert catalog.select_version(vs, date(2026, 11, 7)).identifier == "20261001"
    assert catalog.select_version(vs, date(2026, 1, 1)).identifier == "20250101"  # historical
    assert (
        catalog.select_version(vs, date(2027, 8, 1)).identifier == "20270701"
    )  # future version, by date
    assert catalog.newer_version_exists(vs, vs[1]) is not None


def test_version_unknown_or_ambiguous_is_not_picked_silently():
    vs = [v("a", "2026-01-01"), v("b", "2026-06-01")]  # overlapping, both open ended
    with pytest.raises((catalog.VersionAmbiguous, catalog.VersionNotFound)):
        catalog.select_version(vs, date(2026, 11, 7))
    with pytest.raises(catalog.VersionNotFound):
        catalog.select_version([v("x", "2030-01-01")], date(2026, 11, 7))


def test_sr_number_reused_over_time_is_resolved_by_date_or_flagged():
    old = catalog.LawCandidate("u/old", "1874-01-01", "1999-12-31", "aBV", "alt")
    new = catalog.LawCandidate("u/new", "2000-01-01", None, "BV", "neu")
    assert catalog.select_candidate([old, new], date(2026, 11, 7)).abbreviation == "BV"
    both = [
        catalog.LawCandidate("u/1", "2000-01-01", None, "X", "a"),
        catalog.LawCandidate("u/2", "2001-01-01", None, "Y", "b"),
    ]
    with pytest.raises(catalog.VersionAmbiguous):
        catalog.select_candidate(both, date(2026, 11, 7))
    with pytest.raises(catalog.SourceNotFound):
        catalog.select_candidate([], date(2026, 11, 7))


def test_only_validated_identifiers_enter_sparql():
    fake = FakeFedlex()
    http = make_http(Settings(_env_file=None, fedlex_min_request_interval_seconds=0), fake)
    with pytest.raises(catalog.CatalogError):
        catalog.find_candidates(http, '220" } DROP', "de")
    with pytest.raises(catalog.CatalogError):
        catalog.list_versions(http, "https://evil.example/x")
    assert fake.requests == []


# ---- HTTP safety --------------------------------------------------------------------------------------------
def test_ssrf_and_host_allowlist(fsettings):
    http = make_http(fsettings, FakeFedlex())
    for url in (
        "http://fedlex.data.admin.ch/x",
        "https://evil.example/filestore/x",
        "https://user:pw@fedlex.data.admin.ch/x",
        "https://169.254.169.254/latest",
        "file:///etc/passwd",
    ):
        with pytest.raises(FedlexForbiddenUrl):
            http.request("GET", url)
    with pytest.raises(FedlexForbiddenUrl):
        http.get_document("https://fedlex.data.admin.ch/not-filestore/x.xml")


def test_redirect_to_foreign_host_is_refused(fsettings):
    fake = FakeFedlex(
        fail=lambda r: httpx.Response(302, headers={"location": "https://evil.example/x"})
    )
    with pytest.raises(FedlexForbiddenUrl):
        make_http(fsettings, fake).get_document(XML_URL)


def test_size_cap(fsettings):
    s = fsettings.model_copy(update={"fedlex_max_response_bytes": 100})
    fake = FakeFedlex(fail=lambda r: httpx.Response(200, content=b"x" * 500))
    with pytest.raises(FedlexTooLarge):
        make_http(s, fake).get_document(XML_URL)


def test_retry_with_backoff_then_success(fsettings):
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, content=b"ok")

    sleeps: list[float] = []
    assert make_http(fsettings, FakeFedlex(fail=flaky), sleeps).get_document(XML_URL) == b"ok"
    assert calls["n"] == 3 and len(sleeps) == 2 and sleeps[1] > sleeps[0]


def test_client_errors_are_not_retried(fsettings):
    calls = {"n": 0}

    def nf(req):
        calls["n"] += 1
        return httpx.Response(404)

    with pytest.raises(FedlexHttpError):
        make_http(fsettings, FakeFedlex(fail=nf)).get_document(XML_URL)
    assert calls["n"] == 1


def test_timeout_and_network_errors(fsettings):
    def boom(req):
        raise httpx.ConnectTimeout("t")

    with pytest.raises(FedlexNetworkError):
        make_http(fsettings, FakeFedlex(fail=boom)).get_document(XML_URL)


def test_bad_sparql_response(fsettings):
    fake = FakeFedlex(fail=lambda r: httpx.Response(200, content=b"<html>gateway</html>"))
    with pytest.raises(FedlexBadResponse):
        make_http(fsettings, fake).sparql("SELECT 1")


def test_disabled_makes_no_request(fsettings):
    s = fsettings.model_copy(update={"fedlex_enabled": False})
    fake = FakeFedlex()
    with pytest.raises(FedlexDisabled):
        make_http(s, fake).sparql("SELECT 1")
    assert fake.requests == []


# ---- service: sync, cache, offline, versions -------------------------------------------------------------
def test_sync_stores_snapshot_with_provenance(fsettings, sf, kb):
    fake = FakeFedlex()
    rep = make_service(fsettings, sf, kb, fake).sync(OR_IDS, REF)
    assert rep.count("RETRIEVED") == 4 and not rep.failed
    info = CachedFedlexProvider(sf, fsettings, kb, REF).info("CH_OR_266L")
    assert info.origin == "FEDLEX" and info.retrieval_status == "RETRIEVED"
    assert info.version_identifier == "20261001" and info.valid_from == "2026-10-01"
    assert info.official_document_url == XML_URL and info.official_eli_uri == VERSION
    assert info.retrieved_at and info.content_hash and info.wording_status == "MATCHED"
    assert (
        info.interpretation_status == "NOT_REVIEWED"
    )  # a retrieved text proves no legal conclusion
    assert info.official_text.startswith("1 Vermieter und Mieter")
    assert (
        fake.sparql_count == 3
    )  # candidates + versions + xml url, shared by all sources of the same law


def test_second_sync_is_idempotent_and_uses_cache(fsettings, sf, kb):
    make_service(fsettings, sf, kb, FakeFedlex()).sync(OR_IDS, REF)
    fake2 = FakeFedlex()
    rep = make_service(fsettings, sf, kb, fake2).sync(OR_IDS, REF)
    assert rep.count("CACHED") == 4 and fake2.requests == []
    with sf() as s:
        assert s.query(SourceSnapshot).filter_by(source_id="CH_OR_266L").count() == 1


def test_force_resync_same_content_does_not_duplicate(fsettings, sf, kb):
    make_service(fsettings, sf, kb, FakeFedlex()).sync(OR_IDS, REF)
    make_service(fsettings, sf, kb, FakeFedlex()).sync(OR_IDS, REF, force=True)
    with sf() as s:
        assert s.query(SourceSnapshot).filter_by(source_id="CH_OR_266L").count() == 1


def test_new_version_keeps_old_snapshot(fsettings, sf, kb):
    make_service(fsettings, sf, kb, FakeFedlex()).sync(["CH_OR_266L"], REF)
    new_uri = f"{ABSTRACT}/20270701"
    fake = FakeFedlex(
        versions=[{"cons": new_uri, "dstart": "2027-07-01"}],
        xml=build_xml(new_uri),
        xml_url=XML_URL.replace("20261001", "20270701"),
    )
    rep = make_service(fsettings, sf, kb, fake).sync(["CH_OR_266L"], date(2027, 8, 1))
    assert not rep.failed
    with sf() as s:
        versions = {
            r.version_identifier for r in s.query(SourceSnapshot).filter_by(source_id="CH_OR_266L")
        }
    assert versions == {"20261001", "20270701"}  # older wording stays reproducible


def test_changed_wording_creates_new_row_not_overwrite(fsettings, sf, kb):
    make_service(fsettings, sf, kb, FakeFedlex()).sync(["CH_OR_273_1"], REF)
    snap = dict(next(s for s in FIX if s["source_id"] == "CH_OR_273_1"))
    snap["structure"] = [
        dict(
            snap["structure"][0],
            text="Will eine Partei die Kündigung anfechten, so hat sie 31 Tage.",
        )
    ]
    make_service(fsettings, sf, kb, FakeFedlex(xml=build_xml(snaps=[snap]))).sync(
        ["CH_OR_273_1"], REF, force=True
    )
    with sf() as s:
        assert s.query(SourceSnapshot).filter_by(source_id="CH_OR_273_1").count() == 2


def test_offline_uses_cache_and_never_the_network(fsettings, sf, kb):
    make_service(fsettings, sf, kb, FakeFedlex()).sync(["CH_OR_266L"], REF)
    fake = FakeFedlex()
    rep = make_service(fsettings, sf, kb, fake).sync(
        ["CH_OR_266L", "CH_OR_266O"], REF, offline=True
    )
    assert fake.requests == []
    assert {r.source_id: r.status for r in rep.results} == {
        "CH_OR_266L": "CACHED",
        "CH_OR_266O": "NOT_RETRIEVED",
    }


def test_stale_cache_is_never_presented_as_fresh(fsettings, sf, kb):
    from datetime import UTC, datetime, timedelta

    make_service(fsettings, sf, kb, FakeFedlex()).sync(["CH_OR_266L"], REF)
    with sf() as s:
        for r in s.query(SourceSnapshot):
            r.last_checked_at = datetime.now(UTC) - timedelta(days=60)
        s.commit()
    info = CachedFedlexProvider(sf, fsettings, kb, REF).info("CH_OR_266L")
    assert info.retrieval_status == "RETRIEVED_STALE" and info.cache_age_days >= 60
    assert info.retrieval_status != "RETRIEVED"


def test_unknown_article_not_found_nothing_invented(fsettings, sf, kb):
    snaps = [s for s in FIX if s["source_id"] != "CH_OR_266O"]
    rep = make_service(fsettings, sf, kb, FakeFedlex(xml=build_xml(snaps=snaps))).sync(
        ["CH_OR_266L", "CH_OR_266O"], REF
    )
    st = {r.source_id: r.status for r in rep.results}
    assert st["CH_OR_266L"] == "RETRIEVED" and st["CH_OR_266O"] == "NOT_FOUND"
    info = CachedFedlexProvider(sf, fsettings, kb, REF).info("CH_OR_266O")
    assert info.official_text is None and info.retrieval_status != "RETRIEVED"


@pytest.mark.parametrize(
    ("kw", "status"),
    [
        (dict(candidates=[]), "NOT_FOUND"),
        (
            dict(
                candidates=[
                    {"abs": ABSTRACT, "dentry": "2000-01-01", "abbr": "A"},
                    {"abs": ABSTRACT + "2", "dentry": "2001-01-01", "abbr": "B"},
                ]
            ),
            "VERSION_AMBIGUOUS",
        ),
        (dict(versions=[]), "NOT_FOUND"),
        (dict(xml_url=None), "NOT_FOUND"),
        (dict(xml=b"<akomaNtoso xmlns='x'/>"), "ERROR"),
        (dict(xml=build_xml(f"{ABSTRACT}/20990101")), "EXTRACTION_FAILED"),
    ],
)
def test_failures_are_classified_and_leave_no_snapshot(fsettings, sf, kb, kw, status):
    rep = make_service(fsettings, sf, kb, FakeFedlex(**kw)).sync(["CH_OR_266L"], REF)
    assert rep.results[0].status == status
    with sf() as s:
        assert s.query(SourceSnapshot).count() == 0
    assert (
        CachedFedlexProvider(sf, fsettings, kb, REF).info("CH_OR_266L").retrieval_status
        != "RETRIEVED"
    )


def test_network_outage_during_sync(fsettings, sf, kb):
    def down(req):
        raise httpx.ConnectError("down")

    rep = make_service(fsettings, sf, kb, FakeFedlex(fail=down)).sync(["CH_OR_266L"], REF)
    assert rep.results[0].status == "ERROR" and rep.requests >= 1


def test_case_law_is_skipped_not_faked(fsettings, sf, kb):
    bge = next(s.id for s in kb.sources.values() if s.type == "case_law")
    rep = make_service(fsettings, sf, kb, FakeFedlex()).sync([bge], REF)
    assert rep.results[0].status == "SKIPPED"
    assert CachedFedlexProvider(sf, fsettings, kb, REF).info(bge).origin == "NONE"


def test_requests_contain_no_case_data(fsettings, sf, kb):
    fake = FakeFedlex()
    make_service(fsettings, sf, kb, fake).sync(OR_IDS, REF)
    blob = " ".join(fake.bodies) + " ".join(str(r.url) for r in fake.requests)
    for needle in ("Klient", "Zürich", "4. November", "Vermieter", "FALL-"):
        assert needle not in blob
    assert all(
        "authorization" not in r.headers and "cookie" not in r.headers for r in fake.requests
    )


def test_fedlex_package_never_uses_the_ai_layer():
    pkg = REPO_ROOT / "apps" / "api" / "app" / "services" / "sources" / "fedlex"
    for f in pkg.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert (
            "services.ai" not in text
            and "google.genai" not in text
            and "gemini" not in text.lower()
        ), f.name


# ---- fixtures + source-id mapping -----------------------------------------------------------------------------
def test_fixtures_are_labelled_and_never_verified(fsettings, sf, kb):
    assert seed_fixtures(sf, kb) == len(FIX)
    assert seed_fixtures(sf, kb) == 0  # idempotent
    info = CachedFedlexProvider(sf, fsettings, kb, REF).info("CH_OR_266L")
    assert info.origin == "FIXTURE" and "Test" in (info.retrieval_label_de + (info.message or ""))
    status, _ = CachedFedlexProvider(sf, fsettings, kb, REF).verify("CH_OR_266L")
    assert status.value != "VERIFIED"


def test_source_ids_and_aliases(kb):
    assert kb.resolve_source_id("CH_OR_266L") == "CH_OR_266L"
    assert kb.resolve_source_id("CH_OR_273_1") == "CH_OR_273_1"
    assert kb.resolve_source_id("DOES_NOT_EXIST") is None
    s = kb.sources["CH_OR_266L"]
    assert (s.sr_number, s.statute, s.article) == ("220", "OR", "266l")
    z = kb.sources["CH_ZPO_113"]
    assert (z.sr_number, z.statute) == ("272", "ZPO")


def test_legal_inputs_mapping_is_documentation_only(kb):
    from app.services.sources.fedlex.inputs import build_report, classify

    assert classify("Art. 273 Abs. 1 OR", kb)[0:2] == ("RESOLVED", ["CH_OR_273_1"])
    assert classify("Art. 8 EMRK", kb)[0] == "INTERNATIONAL"
    assert classify("Art. 266a ff. OR", kb)[0] == "UNRESOLVABLE"
    assert classify("Art. 999 OR", kb)[0] == "NOT_IN_KB"
    text, counts = build_report(kb)
    assert "keine Regeln aktiviert" in text and sum(counts.values()) > 0


# ---- API / briefing: statuses, decision independence -----------------------------------------------------------
RENT = (
    "Meine Klientin hat in Zürich eine Wohnungskündigung erhalten. Sie ist alleinige Mieterin. Die Kündigung "
    "wurde ihr am 4. November 2026 mit normaler Post zugestellt. Laut ihrer Aussage wurde kein amtliches "
    "Kündigungsformular verwendet."
)


def _briefing(client):
    cid = new_case(client)["id"]
    d = say(client, cid, RENT)["case"]["current_decision"]
    b = client.post(f"/api/cases/{cid}/briefings").json()["briefing"]
    return d, b


def test_briefing_shows_fixture_sources_with_honest_status(client, ctx):
    seed_fixtures(ctx.session_factory, ctx.kb)
    d, b = _briefing(client)
    assert d["action"] == "ESCALATE" and "TT_FORM_MISSING" in d["triggered_rule_ids"]
    src = {s["source"]["id"]: s["source"] for s in b["legal_sources"]}
    f = src["CH_OR_266L"]["fedlex"]
    assert f["origin"] == "FIXTURE" and f["retrieval_status"] == "RETRIEVED"
    assert f["interpretation_status"] == "NOT_REVIEWED"
    assert "266o" in " ".join(src).lower() or "CH_OR_266O" in src
    assert all(s["verification_status"] != "VERIFIED" for s in src.values())
    assert "Juristisch verifiziert" not in json.dumps(b, ensure_ascii=False)


def test_decision_is_identical_with_and_without_cached_sources(client, ctx, settings):
    d_without, _ = _briefing(client)
    seed_fixtures(ctx.session_factory, ctx.kb)
    d_with, _ = _briefing(client)
    keys = (
        "action",
        "triggered_rule_ids",
        "max_urgency",
        "active_issue_ids",
        "recommended_professionals",
    )
    assert {k: d_without[k] for k in keys} == {k: d_with[k] for k in keys}


def test_status_endpoint_reads_cache_only(client, ctx):
    r = client.get("/api/sources/fedlex/status", params={"issue_id": "CH_TENANCY_TERMINATION"})
    assert r.status_code == 200
    rows = {x["source_id"]: x for x in r.json()}
    assert rows["CH_OR_266L"]["info"]["retrieval_status"] == "NOT_RETRIEVED"
    assert rows["CH_OR_266L"]["info"]["official_text"] is None


def test_sync_endpoint_offline_makes_no_request(client):
    r = client.post(
        "/api/sources/fedlex/sync", json={"issue_id": "CH_TENANCY_TERMINATION", "offline": True}
    )
    assert r.status_code == 200 and r.json()["requests"] == 0 and r.json()["retrieved"] == 0
