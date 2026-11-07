"""Generic document-based case summary (reference template case_summary.html.j2, input like sample/case_sample.json).

NOT used for real cases (LexTec Bridge has no document upload yet); kept to verify the law team's generic template
and as the route for document-based issues later. Differences to the reference renderer (see docs):
  * the deadline END DATE and days left are never computed (product decision for tenancy termination),
  * the traffic light maps the backend's action/urgency fields; it is not a second rule engine.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.services.report.render import _env, logo_uri


def _parse_date(s: str | None):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s or "", fmt).date()
        except ValueError:
            continue
    return None


def _chf(s: str | None) -> float | None:
    m = re.search(r"[\d'’ ]+(?:[.,]\d{1,2})?", (s or "").replace("CHF", ""))
    if not m:
        return None
    try:
        return float(
            m.group(0).replace("'", "").replace("’", "").replace(" ", "").replace(",", ".")
        )
    except ValueError:
        return None


def derive(case: dict[str, Any]) -> dict[str, Any]:
    as_of = _parse_date(case.get("as_of"))
    t = case.setdefault("tenancy", {})
    start = _parse_date((t.get("contract_start") or {}).get("v"))
    if start and as_of and not t.get("duration"):
        months = (as_of.year - start.year) * 12 + as_of.month - start.month
        t["duration"] = {"v": f"{months // 12} J. {months % 12} Mt.", "src": "derived"}
    net, nk = (
        _chf((t.get("rent_net") or {}).get("v")),
        _chf((t.get("ancillary_costs") or {}).get("v")),
    )
    if net is not None and nk is not None and not t.get("rent_gross"):
        total = net + nk
        t["rent_gross"] = {"v": "CHF " + f"{total:,.0f}".replace(",", "'") + ".–", "src": "derived"}
    case["missing_critical_count"] = len(case.get("missing_critical", []))
    return case


def traffic_light(case: dict[str, Any]) -> dict[str, Any]:
    action, urgency = case.get("action"), case.get("urgency")
    level = {"CRITICAL": "ROT", "HIGH": "ROT", "MEDIUM": "AMBER", "LOW": "GRUEN"}.get(
        urgency or "", "AMBER"
    )
    if action == "IMMEDIATE_SAFETY_RESPONSE":
        level = "ROT"
    elif action in ("ESCALATE", "ASK") and level == "GRUEN":
        level = "AMBER"
    label = {
        "ROT": "Sofort bearbeiten",
        "AMBER": "Bald bearbeiten",
        "GRUEN": "Ordentlich bearbeiten",
    }[level]
    return {
        "level": level,
        "label": label,
        "reasons": [f"Entscheid {action}", f"Dringlichkeit {urgency}"],
    }


def render_generic_summary_html(case: dict[str, Any], annex_start_page: int = 0) -> str:
    case = derive(case)
    dl = case.get("deadline")
    return (
        _env()
        .get_template("case_summary.html.j2")
        .render(
            case=case,
            tl=traffic_light(case),
            dl=dl,
            annex_start_page=annex_start_page,
            logo=logo_uri(),
        )
    )
