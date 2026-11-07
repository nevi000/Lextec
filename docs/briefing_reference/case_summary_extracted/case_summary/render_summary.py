#!/usr/bin/env python3
"""Rendert eine Fallzusammenfassung (case_summary_v1) als PDF.

    python render_summary.py sample/case_sample.json --out output/Fallzusammenfassung.pdf

Eingabe: JSON aus der Pipeline (Fakten mit Herkunft, Regel-Ergebnisse, Verweisungen, Unterlagen).
Der Renderer berechnet nur Abgeleitetes (Dauer, Bruttomiete, Frist-Ende, Ampel) und erfindet nichts:
fehlende Werte bleiben null und erscheinen als FEHLT.

Abhaengigkeiten: jinja2, pyyaml, pypdf, playwright (Chromium/Chrome).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import mimetypes
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "knowledge_base" / "briefings" / "case_summary_v1.yaml"
TEMPLATES = ROOT / "templates"
CHROME = "/usr/bin/google-chrome"  # anpassen oder None fuer Playwright-Chromium


# ----------------------------------------------------------------- Hilfsfunktionen
def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def fmt_date(d: date) -> str:
    wd = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][d.weekday()]
    return f"{wd} {d:%d.%m.%Y}"


def chf(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"[\d'’ ]+(?:[.,]\d{1,2})?", s.replace("CHF", ""))
    if not m:
        return None
    num = m.group(0).replace("'", "").replace("’", "").replace(" ", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def fmt_chf(x: float) -> str:
    return "CHF " + f"{x:,.0f}".replace(",", "'") + ".–" if x == int(x) else "CHF " + f"{x:,.2f}".replace(",", "'")


def get_path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if cur is None:
            return None
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def test(op, actual, expected):
    if actual is None:
        return False
    if op == "eq":
        return actual == expected
    if op == "lte":
        return actual <= expected
    if op == "gte":
        return actual >= expected
    if op == "in":
        return actual in expected
    raise ValueError(f"Unbekannter Operator: {op}")


ACTION_TEXT = {"PROCEED": "kann weiterfahren", "ASK": "Angaben fehlen", "ESCALATE": "muss an eine Fachperson",
               "IMMEDIATE_SAFETY_RESPONSE": "akute Gefahr gemeldet"}
REASON_TEXT = {
    "action": lambda v: f"Fall {ACTION_TEXT.get(v, v)}",
    "urgency": lambda v: "kritische Dringlichkeit" if v == "CRITICAL" else f"Dringlichkeit {v}",
    "deadline.days_left": lambda v: f"Frist endet in {v} Tagen",
    "deadline.date_unknown_but_likely": lambda v: "Frist wahrscheinlich, Datum unbekannt",
    "liability_flag.severity": lambda v: "Haftungs- oder Menschenrechtshinweis",
    "missing_critical_count": lambda v: f"{v} wichtige Angabe fehlt" if v == 1 else f"{v} wichtige Angaben fehlen",
}


# ----------------------------------------------------------------- Ableitungen
def derive(case: dict) -> dict:
    as_of = parse_date(case["as_of"])
    t = case.setdefault("tenancy", {})

    start = parse_date((t.get("contract_start") or {}).get("v"))
    if start and as_of and not t.get("duration"):
        months = (as_of.year - start.year) * 12 + as_of.month - start.month
        t["duration"] = {"v": f"{months // 12} J. {months % 12} Mt.", "src": "derived"}

    net, nk = chf((t.get("rent_net") or {}).get("v")), chf((t.get("ancillary_costs") or {}).get("v"))
    if net is not None and nk is not None and not t.get("rent_gross"):
        t["rent_gross"] = {"v": fmt_chf(net + nk), "src": "derived"}

    dl = case.get("deadline")
    if dl:
        s = parse_date(dl.get("start_date"))
        if s and dl.get("days"):
            end = s + timedelta(days=dl["days"])
            dl["computed_end"] = fmt_date(end)
            dl["days_left"] = (end - as_of).days if as_of else None
            caveat = dl.get("caveat", "")
            if end.weekday() >= 5:
                caveat += " Ende fällt auf ein Wochenende: Verschiebung prüfen."
            dl["caveat"] = caveat.strip()
        else:
            dl.setdefault("days_left", None)
            dl.setdefault("computed_end", "unbekannt")

    case["missing_critical_count"] = len(case.get("missing_critical", []))
    return case


def traffic_light(case: dict, spec: dict) -> dict:
    """Erste zutreffende Stufe gewinnt; Treffer tieferer Stufen werden als 'zudem' mitgegeben."""
    result, seen = None, set()
    for rule in spec["traffic_light"]:
        hits = []
        for cond in rule["when_any"]:
            actual = get_path(case, cond["field"])
            if test(cond["operator"], actual, cond["value"]):
                text = REASON_TEXT.get(cond["field"], lambda v: f"{cond['field']} = {v}")(actual)
                if text not in seen:
                    seen.add(text)
                    hits.append(text)
        if hits and result is None:
            result = {"level": rule["level"], "label": rule["label"], "reasons": hits}
        elif hits and result is not None and rule["level"] != "GRUEN":
            result["reasons"] += [f"zudem: {h}" for h in hits]
    return result or {"level": "AMBER", "label": "Keine Regel traf zu – manuell einstufen", "reasons": ["Fallback"]}


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


# ----------------------------------------------------------------- Rendern
def render_html(case: dict, annex_start_page: int) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    tpl = env.get_template("case_summary.html.j2")
    logo = None
    for name in ("lextec_logo.svg", "lextec_logo.png"):
        f = ROOT / "assets" / name
        if f.exists():
            logo = data_uri(f) if f.suffix == ".png" else "data:image/svg+xml;base64," + base64.b64encode(f.read_bytes()).decode()
            break
    return tpl.render(case=case, tl=case["traffic_light"], dl=case.get("deadline"), annex_start_page=annex_start_page, logo=logo)


def html_to_pdf(html: str, case: dict) -> bytes:
    from playwright.sync_api import sync_playwright

    footer = (
        '<div style="font-family:Inter,sans-serif;font-size:6.4pt;color:#86868b;width:100%;'
        'padding:0 15mm;display:flex;justify-content:space-between;">'
        f'<span>Fall {case["case_id"]}. KI-gestützte Vorbereitung, keine Rechtsberatung. '
        'Enthält besonders schützenswerte Daten (Art. 5 lit. c nDSG).</span>'
        '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        pdf = page.pdf(format="A4", print_background=True, prefer_css_page_size=True,
                       display_header_footer=True, header_template="<div></div>", footer_template=footer)
        browser.close()
    return pdf


def build(case_path: Path, out_path: Path, html_out: Path | None = None) -> Path:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    case = json.loads(case_path.read_text(encoding="utf-8"))
    base = case_path.parent

    case = derive(case)
    case["traffic_light"] = traffic_light(case, spec)

    pdf_attachments, n_scan_pages = [], 0
    for i, d in enumerate(case.get("documents", []), start=1):
        d["annex_no"] = f"A{i}"
        d["images"] = []
        for f in d.get("files", []):
            fp = (base / f).resolve()
            if fp.suffix.lower() == ".pdf":
                pdf_attachments.append(fp)
            else:
                d["images"].append(data_uri(fp))
                n_scan_pages += 1

    # Zwei Durchgaenge: Seitenzahl des Anhangs ermitteln, dann final rendern.
    first = html_to_pdf(render_html(case, 0), case)
    total = len(PdfReader(io.BytesIO(first)).pages)
    annex_start = total - n_scan_pages  # Verzeichnis-Seite = erste Anhangseite
    html = render_html(case, annex_start)
    pdf = html_to_pdf(html, case)

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf)))
    for att in pdf_attachments:            # Original-PDFs unveraendert anhaengen
        writer.append(PdfReader(str(att)))
    writer.add_metadata({"/Title": f"Fallzusammenfassung {case['case_id']}", "/Author": "LexTec Bridge"})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fh:
        writer.write(fh)
    if html_out:
        html_out.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("case_json", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "Fallzusammenfassung.pdf")
    ap.add_argument("--html", type=Path, default=None, help="optional: gerendertes HTML speichern")
    a = ap.parse_args()
    print(build(a.case_json, a.out, a.html))
