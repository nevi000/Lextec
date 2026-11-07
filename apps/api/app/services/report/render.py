"""HTML rendering of the case report (Jinja2, sandboxed, autoescaped, no external resources)."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
ASSETS = HERE / "assets"


@lru_cache(maxsize=1)
def _env() -> SandboxedEnvironment:
    # user data is only ever a *value* in the context, never template source; everything is HTML-escaped
    return SandboxedEnvironment(loader=FileSystemLoader(TEMPLATES), autoescape=True)


@lru_cache(maxsize=1)
def logo_uri() -> str | None:
    f = ASSETS / "lextec_logo.png"
    return (
        "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode() if f.exists() else None
    )


@lru_cache(maxsize=1)
def fonts_css() -> str:
    """Inter (OFL, already a project dependency) embedded: the PDF looks the same on every machine, nothing is fetched."""
    f = ASSETS / "inter-latin-wght-normal.woff2"
    if not f.exists():
        return ""
    b64 = base64.b64encode(f.read_bytes()).decode()
    src = f"url(data:font/woff2;base64,{b64}) format('woff2')"
    return "".join(
        f"@font-face{{font-family:'{name}';font-style:normal;font-weight:100 900;font-display:block;src:{src};}}"
        for name in ("Inter",)
    )


def render_report_html(view: dict[str, Any]) -> str:
    return (
        _env()
        .get_template("expert_briefing.html.j2")
        .render(b=view, logo=logo_uri(), fonts_css=fonts_css())
    )
