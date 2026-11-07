"""Fallbericht (Expert Briefing, new law-team template): view model, HTML preview, PDF. MOCK AI only.

The reference data comes from docs/briefing_reference (delivered by the law team)."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pymupdf
import pytest

from app.core.config import REPO_ROOT
from app.services.knowledge.loader import load_knowledge_base
from app.services.report.generic import render_generic_summary_html
from app.services.report.pdf import find_browser, html_to_pdf
from app.services.report.render import render_report_html
from app.services.report.sample_adapter import view_from_bridge_sample
from tests.conftest import new_case, say

REF = REPO_ROOT / "docs" / "briefing_reference"
SAMPLE = REF / "case_summary_extracted" / "case_summary" / "sample"
REF_PDF = REF / "Expert_Briefing_FALL-0011.pdf"
needs_browser = pytest.mark.skipif(
    find_browser() is None, reason="no Chrome/Edge for PDF rendering"
)

RENT = (
    "Meine Klientin hat in Zürich eine Wohnungskündigung erhalten. Sie ist alleinige Mieterin. "
    "Die Kündigung wurde ihr am 4. November 2026 mit normaler Post zugestellt. "
    "Laut ihrer Aussage wurde kein amtliches Kündigungsformular verwendet. "
    "Der Vertrag ist unbefristet, es ist eine normale Wohnung, keine Untermiete."
)


def make_report(client, text: str):
    cid = new_case(client)["id"]
    say(client, cid, text)
    b = client.post(f"/api/cases/{cid}/briefings").json()
    return cid, b["id"]


def preview(client, cid, bid) -> str:
    r = client.get(f"/api/cases/{cid}/briefings/{bid}/preview")
    assert r.status_code == 200
    return r.text


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


@pytest.fixture(scope="module")
def kb():
    k = load_knowledge_base(REPO_ROOT / "knowledge_base")
    assert k.valid, k.errors
    return k


# ---- C: real database case -> report --------------------------------------------------------------------------
def test_report_from_a_real_stored_case(client):
    cid, bid = make_report(client, RENT)
    t = plain(preview(client, cid, bid))
    assert "Kündigung durch die Vermieterschaft" in t and "Fachperson nötig" in t
    assert "Version 1" in t and "Fallstand v" in t and "Wissensbasis kb-" in t
    assert "TT_FORM_MISSING" in t  # rule trace from the backend, not recomputed
    assert "Schlichtungsbehörde" in t and "058 111 70 30" in t  # referral from the knowledge base
    assert "Chronologie" in t and "04.11.2026" in t  # derived from stored facts, not invented
    assert "Gesprächsinformationen" in t and "Meine Klientin hat in Zürich" in t
    assert "Interpretation noch nicht freigegeben" in t  # never claims a verified interpretation


def test_preview_is_self_contained_and_script_free(client):
    cid, bid = make_report(client, RENT)
    r = client.get(f"/api/cases/{cid}/briefings/{bid}/preview")
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert "<script" not in r.text.lower()
    assert not re.search(r'(src|href)="https?://[^"]*\.(js|css|png|woff2?)"', r.text)


def test_unknown_briefing_is_404_and_cases_are_isolated(client):
    cid, bid = make_report(client, RENT)
    other = new_case(client)["id"]
    assert client.get(f"/api/cases/{other}/briefings/{bid}/preview").status_code == 404
    assert client.get(f"/api/cases/{cid}/briefings/nope/preview").status_code == 404


# ---- D: few data, nothing invented ------------------------------------------------------------------------------
def test_sparse_case_marks_missing_data_and_invents_nothing(client):
    cid, bid = make_report(client, "Meine Klientin hat eine Wohnungskündigung erhalten.")
    t = plain(preview(client, cid, bid))
    assert "Nicht erfasst:" in t and "Name nicht erfasst" in t and "Kontaktangaben fehlen" in t
    assert "Keine Unterlagen im System" in t
    for invented in ("Mustermann", "Meier", "@example", "044 000"):
        assert invented not in t
    assert "Keine hochgeladenen Originaldokumente" in t  # no upload support: documented, not faked


# ---- E: safety first -----------------------------------------------------------------------------------------------
def test_acute_danger_is_prominent_and_the_traffic_light_is_never_lower(client):
    cid, bid = make_report(client, RENT + " Ihr Vermieter droht, sie zu schlagen.")
    html = preview(client, cid, bid)
    t = plain(html)
    assert (
        t.index("Akute Gefahr erkannt")
        < t.index("Kurzsachverhalt")
        < t.index("Fristen und Unterlagen")
    )
    assert "Sofort handeln" in t and "117" in t
    assert "Dieser Bericht ersetzt die Kontaktaufnahme mit der Notrufstelle nicht" in t
    assert "Jetzt Notfallhilfe kontaktieren" in t
    assert 'class="signal ROT"' in html


# ---- F: several issues -------------------------------------------------------------------------------------------------
def test_multiple_issues_render_without_breaking(client):
    cid, bid = make_report(
        client,
        "Mein Arbeitgeber hat mir gekündigt. Der Vermieter hat der Klientin ausserdem gekündigt, sie ist alleinerziehend.",
    )
    t = plain(preview(client, cid, bid))
    assert "Arbeitskündigung" in t and "Kündigung durch die Vermieterschaft" in t
    assert "Rechtliche Prüfung" in t and "Erfasste Angaben" in t


def test_unsupported_issue_is_flagged_not_hidden(client):
    cid, bid = make_report(client, "Ich brauche Hilfe bei meiner Scheidung.")
    assert "nicht abgedeckt" in plain(preview(client, cid, bid))


# ---- deadlines ----------------------------------------------------------------------------------------------------------
def test_no_binding_deadline_end_is_ever_printed(client):
    cid, bid = make_report(client, RENT)
    t = plain(preview(client, cid, bid))
    for end in ("04.12.2026", "4. Dezember 2026", "Frist endet", "Fristende:"):
        assert end not in t
    assert "Das Fristende prüft und berechnet die Fachperson" in t
    assert "Hinweis, kein Fristende" in t


# ---- H: versioning ---------------------------------------------------------------------------------------------------
def test_new_version_keeps_the_old_one(client):
    cid, b1 = make_report(client, RENT)
    first = preview(client, cid, b1)
    say(client, cid, "Die Klientin hat keine Mietrückstände und noch nichts unterschrieben.")
    assert client.get(f"/api/cases/{cid}").json()["briefing_stale"] is True
    b2 = client.post(f"/api/cases/{cid}/briefings").json()["id"]
    versions = client.get(f"/api/cases/{cid}/briefings").json()
    assert [v["version"] for v in versions] == [2, 1]
    assert preview(client, cid, b1) == first  # the old version renders exactly as before
    second = plain(preview(client, cid, b2))
    assert "Version 2" in second and "keine Mietrückstände" in second


# ---- escaping / template safety -------------------------------------------------------------------------------------------
def test_user_text_is_escaped_and_never_executed(client):
    evil = RENT + " <script>alert(1)</script> {{ 7*7 }} <img src=x onerror=alert(1)>"
    cid, bid = make_report(client, evil)
    html = preview(client, cid, bid)
    assert "<script>alert(1)</script>" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "{{ 7*7 }}" in html and ">49<" not in html


# ---- traffic light: a mapping of the backend decision, never lower than safety ---------------------------------------------
def test_traffic_light_mapping_follows_the_backend():
    from app.schemas.briefing import CaseBriefing, ReportExtras
    from app.schemas.safety import SafetyAssessment
    from app.services.report.view import traffic_light

    def mk(action, urgency, safety="NONE"):
        decision = type(
            "D", (), {"action": type("A", (), {"value": action})(), "max_urgency": urgency}
        )()
        b = CaseBriefing.model_construct(
            decision=decision,
            extras=ReportExtras(safety=SafetyAssessment(state=safety)),
            missing_information=[],
        )
        return traffic_light(b)

    assert mk("PROCEED", None)["level"] == "GRUEN"
    assert (
        mk("ESCALATE", "LOW")["level"] == "AMBER" and mk("ESCALATE", "MEDIUM")["level"] == "AMBER"
    )
    assert mk("ESCALATE", "HIGH")["level"] == "ROT"
    assert (
        mk("PROCEED", "LOW", safety="IMMEDIATE")["level"] == "ROT"
    )  # never lower than the safety decision
    assert mk("PROCEED", None, safety="HUMAN_CHECK")["level"] == "AMBER"
    assert mk("PROCEED", None, safety="IMMEDIATE")["label"] == "Sofort handeln"


# ---- A: generic template with the delivered sample --------------------------------------------------------------------------
def test_generic_summary_renders_the_delivered_sample_without_a_computed_deadline():
    case = json.loads((SAMPLE / "case_sample.json").read_text(encoding="utf-8"))
    t = plain(render_generic_summary_html(case))
    assert case["case_id"] in t and "Fehlt" in t
    # the renderer adds no end date: the only occurrences are the law team's own sample sentences (input data)
    assert t.count("12.11.2026") == json.dumps(case, ensure_ascii=False).count("12.11.2026")
    assert "Resttage" not in t and "bis <b>" not in render_generic_summary_html(
        json.loads(json.dumps(case))
    )
    assert "Das Fristende prüft die Fachperson" in t


# ---- B: Bridge sample vs. delivered reference PDF -----------------------------------------------------------------------------
def test_bridge_sample_matches_the_reference_pdf(kb):
    data = json.loads((SAMPLE / "bridge_fall_0011.json").read_text(encoding="utf-8"))
    ours = plain(render_report_html(view_from_bridge_sample(data, kb.referral_network)))
    ref = re.sub(r"\s+", " ", " ".join(p.get_text() for p in pymupdf.open(REF_PDF)))
    must = [
        data["case_id"],
        data["kb_version"],
        data["decision"]["label"],
        data["decision"]["code"],
        data["handover"]["to"],
        "Bald bearbeiten",
        "Kontaktangaben fehlen",
    ]
    must += [s["id"] for s in data["sources"]]
    must += [b["label"] for b in data["bodies"][:3]]
    for m in must:
        norm = re.sub(r"\s+", " ", m)
        assert norm in ref, f"reference PDF lacks {norm!r}"
        assert norm in ours, f"integrated report lacks {norm!r}"
    assert len(data["sources"]) == 15 and ours.count("Im Law-Dossier geprüft") >= 15


# ---- G: real PDFs ----------------------------------------------------------------------------------------------------------------
@needs_browser
def test_pdf_layout_pages_footer_links_and_umlauts(client):
    cid, bid = make_report(client, RENT)
    r = client.get(f"/api/cases/{cid}/briefings/{bid}/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert 'filename="Fallbericht_FALL-' in r.headers["content-disposition"]
    doc = pymupdf.open(stream=io.BytesIO(r.content), filetype="pdf")
    n = len(doc)
    assert 5 <= n <= 14  # dynamic page count, no fixed layout
    for i, page in enumerate(doc):
        assert abs(page.rect.width - 595) < 2 and abs(page.rect.height - 842) < 2  # A4
        text = page.get_text()
        assert len(text.strip()) > 120, f"page {i + 1} is (almost) empty"
        assert f"{i + 1} / {n}" in text  # footer with page numbers
        assert "KI-gestützte Vorbereitung, keine Rechtsberatung" in text
    full = " ".join(p.get_text() for p in doc)
    for word in ("Kündigung", "Zürich", "Prüfpunkte", "Einschätzung", "Rechtsquellen"):
        assert word in full
    assert any(page.get_images() for page in doc[:1])  # logo
    uris = [lnk["uri"] for p in doc for lnk in p.get_links() if lnk.get("uri")]
    assert any(u.startswith("https://") for u in uris)
    assert doc.metadata["title"].startswith("Fallbericht FALL-")


@needs_browser
def test_pdf_of_a_long_report_stays_readable(client):
    filler = " ".join(
        f"Zusatzinformation {i}: Die Klientin schildert ausführlich ihre Wohnsituation."
        for i in range(60)
    )
    cid, bid = make_report(client, RENT + " " + filler)
    doc = pymupdf.open(
        stream=io.BytesIO(client.get(f"/api/cases/{cid}/briefings/{bid}/pdf").content),
        filetype="pdf",
    )
    assert all(len(p.get_text().strip()) > 120 for p in doc)


@needs_browser
def test_pdf_has_no_network_dependency():
    data = json.loads((SAMPLE / "bridge_fall_0011.json").read_text(encoding="utf-8"))
    html = render_report_html(view_from_bridge_sample(data))
    html = html.replace("</body>", '<img src="https://example.invalid/x.png"></body>')
    assert html_to_pdf(html, "FALL-TEST").startswith(
        b"%PDF"
    )  # the external image is blocked, rendering still succeeds


def test_report_package_never_uses_the_ai_layer():
    pkg = REPO_ROOT / "apps" / "api" / "app" / "services" / "report"
    for f in pkg.glob("*.py"):
        t = f.read_text(encoding="utf-8").lower()
        assert "services.ai" not in t and "gemini" not in t and "genai" not in t, f.name


def test_pdf_browser_discovery_has_no_hardcoded_platform_path(monkeypatch):
    src = (REPO_ROOT / "apps/api/app/services/report/pdf.py").read_text(encoding="utf-8")
    assert (
        "LEXTEC_PDF_BROWSER" in src and "/usr/bin/google-chrome" in src
    )  # only one candidate among many
    monkeypatch.setenv("LEXTEC_PDF_BROWSER", str(Path(__file__)))
    assert find_browser() == str(Path(__file__))
