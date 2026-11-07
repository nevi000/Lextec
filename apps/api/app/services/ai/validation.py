"""Validation of untrusted model output against stored messages and the knowledge base."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.ai.schemas import ExtractionResult
from app.services.knowledge.loader import KnowledgeBase
from app.services.knowledge.schema import FactDef

_WS = re.compile(r"\s+")
_TRUE = {"ja", "true", "yes", "wahr", "1", "j"}
_FALSE = {"nein", "false", "no", "falsch", "0", "n"}


def normalize(text: str) -> str:
    return _WS.sub(" ", text).strip().casefold()


def quote_in_message(quote: str, content: str) -> bool:
    q = normalize(quote).strip(" \"'«»„“”")
    return bool(q) and q in normalize(content)


def coerce_value(fact: FactDef, raw: str) -> Any:
    """Convert model text to a typed value; raises ValueError if it does not fit the fact type."""
    text = str(raw).strip()
    if not text:
        raise ValueError("leerer Wert")
    t = fact.data_type
    if t == "boolean":
        low = text.casefold().rstrip(".!")
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise ValueError(f"kein boolescher Wert: {text!r}")
    if t == "date":
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
        if m:
            y, mo, d = map(int, m.groups())
        else:
            m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
            if not m:
                raise ValueError(f"kein Datum: {text!r}")
            d, mo, y = map(int, m.groups())
        return date(y, mo, d).isoformat()  # raises ValueError for impossible dates
    if t == "integer":
        digits = re.sub(r"(?i)chf|fr\.?|[\s'’.,-]", "", text)
        if not digits.isdigit():
            raise ValueError(f"keine ganze Zahl: {text!r}")
        return int(digits)
    if t == "enum":
        for ev in fact.enum_values:
            if ev.casefold() == text.casefold():
                return ev
        raise ValueError(f"{text!r} nicht in {fact.enum_values}")
    return text


@dataclass
class ValidatedExtraction:
    issues: list = field(default_factory=list)  # DetectedIssue
    unsupported: list = field(default_factory=list)  # UnrecognizedIssue
    facts: list = field(default_factory=list)  # (ExtractedFact, typed_value|None)
    contradictions: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    warnings: list[str] = field(default_factory=list)


def validate_extraction(
    result: ExtractionResult,
    kb: KnowledgeBase,
    messages: dict[str, str],  # message_id -> content (messages that were sent to the model)
    allowed_issue_ids: set[str]
    | None = None,  # ids that were offered in the catalog (None = all of the KB)
) -> ValidatedExtraction:
    """Drop everything that references unknown ids or has fabricated evidence."""
    out = ValidatedExtraction(summary=result.summary_de.strip())
    fact_defs: dict[str, FactDef] = {}
    for issue in kb.issues.values():
        for f in issue.facts:
            fact_defs.setdefault(f.id, f)

    seen_issue: set[str] = set()
    for di in result.detected_issues:
        if di.issue_id not in kb.issues or (
            allowed_issue_ids is not None and di.issue_id not in allowed_issue_ids
        ):
            out.warnings.append(f"Unbekannte Issue-ID verworfen: {di.issue_id!r}.")
            continue
        content = messages.get(di.source_message_id)
        if content is None or not quote_in_message(di.evidence_quote, content):
            out.warnings.append(
                f"Issue {di.issue_id}: Beleg nicht in Nachricht gefunden, verworfen."
            )
            continue
        if di.issue_id in seen_issue:
            continue
        seen_issue.add(di.issue_id)
        out.issues.append(di)

    for ui in result.unrecognized_issues:
        content = messages.get(ui.source_message_id)
        if content is None or not quote_in_message(ui.evidence_quote, content):
            out.warnings.append("Nicht abgedecktes Rechtsproblem ohne gültigen Beleg verworfen.")
            continue
        out.unsupported.append(ui)

    for ef in result.facts:
        fd = fact_defs.get(ef.fact_id)
        if fd is None:
            out.warnings.append(f"Unbekannte Fakt-ID verworfen: {ef.fact_id!r}.")
            continue
        content = messages.get(ef.source_message_id)
        if content is None or not quote_in_message(ef.evidence_quote, content):
            out.warnings.append(f"Fakt {ef.fact_id}: Beleg nicht in Nachricht gefunden, verworfen.")
            continue
        if ef.ambiguous or ef.unknown:
            out.facts.append((ef, None))
            continue
        try:
            out.facts.append((ef, coerce_value(fd, ef.value)))
        except ValueError as exc:
            out.warnings.append(
                f"Fakt {ef.fact_id}: Wert unbrauchbar ({exc}); als unklar markiert."
            )
            ef = ef.model_copy(update={"ambiguous": True, "ambiguity_note": str(exc)})
            out.facts.append((ef, None))

    for cc in result.contradiction_candidates:
        if cc.fact_id in fact_defs:
            out.contradictions[cc.fact_id] = cc.note
    return out
