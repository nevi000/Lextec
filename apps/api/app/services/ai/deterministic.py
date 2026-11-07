"""Deterministic parsing of SIMPLE direct answers (no AI call needed).

When the social worker answers the suggested question with just "Ja", a date, a number or one of the
offered choices, the meaning is unambiguous. Parsing it locally is free, instant and fully traceable.
Anything else (free text, several facts at once) still goes to the AI extractor.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from app.services.ai.validation import coerce_value
from app.services.knowledge.schema import FactDef

Kind = Literal["value", "ambiguous", "unknown"]

_YES = {"ja", "j", "yes", "true", "stimmt", "genau", "jawohl"}
_NO = {"nein", "n", "no", "false", "nope", "nicht"}
_UNKNOWN = {
    "weiss nicht",
    "weiss ich nicht",
    "weiß nicht",
    "weiß ich nicht",
    "keine ahnung",
    "unbekannt",
    "weiss es nicht",
    "weiß es nicht",
    "nicht bekannt",
    "k. a.",
    "ka",
}
_AMBIGUOUS = {"unklar", "vielleicht", "eventuell", "teilweise"}
_DATE = re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})$")
_INT = re.compile(r"^(chf|fr\.?)?\s*\d[\d'’ ]*(\.-|\.00)?$", re.IGNORECASE)
MAX_LEN = 60


def parse_simple_answer(fd: FactDef, text: str) -> tuple[Kind, Any] | None:
    t = text.strip()
    if not t or len(t) > MAX_LEN:
        return None
    low = t.casefold().rstrip(".!? ")
    if low in _UNKNOWN:
        return "unknown", None
    if low in _AMBIGUOUS:
        return "ambiguous", None
    try:
        if fd.data_type == "boolean":
            if low in _YES:
                return "value", True
            if low in _NO:
                return "value", False
            return None
        if fd.data_type == "date":
            return ("value", coerce_value(fd, t)) if _DATE.match(t) else None
        if fd.data_type == "integer":
            return ("value", coerce_value(fd, t)) if _INT.match(t) else None
        if fd.data_type == "enum":
            for value in fd.enum_values:
                label = fd.enum_labels_de.get(value, "").casefold()
                if low in (value.casefold(), label):
                    return "value", value
            return None
    except ValueError:
        return None
    return None  # free-text facts always go to the AI
