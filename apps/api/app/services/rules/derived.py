"""Derived values for INTERNAL urgency assessment.

Hard rule (Issue 1 dossier, section 4): the system never computes or outputs a concrete deadline
END date. A derived value is just a number of days between a documented date and "today", used by
rules such as "20 or more days since the earliest known receipt hint -> immediate legal review".
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services.knowledge.schema import DerivedDef


def _parse(value: Any) -> date | None:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def compute_derived(
    defs: list[DerivedDef], known_facts: dict[str, Any], today: date | None
) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for d in defs:
        dates = [x for fid in d.facts if (x := _parse(known_facts.get(fid))) is not None]
        if today is None or not dates:
            out[d.id] = None
            continue
        earliest = min(dates)
        out[d.id] = (
            (today - earliest).days if d.kind == "days_since_earliest" else (earliest - today).days
        )
    return out
