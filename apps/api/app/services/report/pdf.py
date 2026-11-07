"""HTML -> PDF with a headless Chromium-based browser (Playwright driver).

No hard-coded Linux path: the browser is discovered (env LEXTEC_PDF_BROWSER, PATH, standard Windows/macOS/Linux
install locations incl. Microsoft Edge, then Playwright's own Chromium cache). Network access of the page is blocked
(the report is fully self-contained), and no AI is involved.
"""

from __future__ import annotations

import glob
import io
import os
import shutil
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from app.core.errors import AppError


class PdfUnavailable(AppError):
    status_code = 503
    code = "pdf_unavailable"


def _candidates() -> list[str]:
    out: list[str] = []
    env = os.environ.get("LEXTEC_PDF_BROWSER")
    if env:
        out.append(env)
    for name in (
        "chrome",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "msedge",
        "microsoft-edge",
    ):
        p = shutil.which(name)
        if p:
            out.append(p)
    if sys.platform == "win32":
        roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        for r in filter(None, roots):
            out += [
                str(Path(r) / "Google/Chrome/Application/chrome.exe"),
                str(Path(r) / "Microsoft/Edge/Application/msedge.exe"),
            ]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            out += sorted(
                glob.glob(str(Path(local) / "ms-playwright/chromium-*/chrome-win*/chrome.exe")),
                reverse=True,
            )
    elif sys.platform == "darwin":
        out += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:
        out += [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
        ]
        out += sorted(
            glob.glob(str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux*/chrome")),
            reverse=True,
        )
    return out


def find_browser() -> str | None:
    for c in _candidates():
        if c and Path(c).is_file():
            return c
    return None


def footer_html(case_id: str) -> str:
    safe = "".join(ch for ch in case_id if ch.isalnum() or ch in "-_ ")
    return (
        '<div style="font-family:Inter,Segoe UI,Arial,sans-serif;font-size:6.4pt;color:#8e8e8e;width:100%;'
        'padding:0 15mm;display:flex;justify-content:space-between;">'
        f"<span>Fall {safe}. KI-gestützte Vorbereitung, keine Rechtsberatung. "
        "Enthält besonders schützenswerte Daten (Art. 5 lit. c nDSG).</span>"
        '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
    )


def html_to_pdf(html: str, case_id: str, *, timeout_ms: int = 60_000) -> bytes:
    from playwright.sync_api import sync_playwright

    exe = find_browser()
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception as exc:  # no browser at all
            raise PdfUnavailable(
                "Für den PDF-Export wird Chrome oder Edge benötigt (oder LEXTEC_PDF_BROWSER setzen). "
                "Der Browserdruck der Vorschau funktioniert weiterhin."
            ) from exc
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            # the report is self-contained: block every network request
            page.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if not route.request.url.startswith(("data:", "about:"))
                    else route.continue_()
                ),
            )
            page.set_content(html, wait_until="load")
            pdf = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=footer_html(case_id),
            )
        finally:
            browser.close()
    return _with_metadata(pdf, case_id)


def _with_metadata(pdf: bytes, case_id: str) -> bytes:
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf)))
    writer.add_metadata(
        {
            "/Title": f"Fallbericht {case_id}",
            "/Author": "LexTec Bridge",
            "/Subject": "Expert Briefing",
        }
    )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
