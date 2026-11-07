"""Static question quality audit (Fragequalität).

Two severities, deliberately kept apart:

* ``error``  - technical/product inconsistencies that can be decided mechanically:
    - a question asks for an upload of a document (LexTec Bridge has no document upload, only the case-description PDF import)
    - the question's wording cannot be answered by the configured answer type (an open «Wann/Wie/Welche …» question on a
      Ja/Nein fact, a date/number type whose question does not ask for a date/number)
* ``hint``   - linguistic hints for the law team (several question marks, «falls ja …» follow-ups). Never automatically wrong:
  a question like «Liegen Mietvertrag und Nachträge vollständig vor?» is a legitimate single yes/no.

Used by the knowledge-base CLI and the tests. It does NOT make a knowledge base invalid at load time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.knowledge.loader import KnowledgeBase

UPLOAD = re.compile(
    r"hochlad|\bupload|hoch\s*laden|laden\s+sie\b.*\bhoch\b|\(foto\)|foto\s+hoch", re.IGNORECASE
)
OPEN_START = re.compile(
    r"^\s*(wann|wie\s+viele?|wieviel\w*|wie|welche[rsmn]?|wo|was|wer|warum|weshalb|wozu|wohin|woher)\b",
    re.IGNORECASE,
)
DATE_WORDS = re.compile(
    r"\bwann\b|datum|seit\s+wann|bis\s+wann|ab\s+wann|bis\s+zu\s+welchem|ab\s+welchem|seit\s+welchem|auf\s+welches",
    re.IGNORECASE,
)
NUMBER_WORDS = re.compile(
    r"wie\s+hoch|wie\s+viele?|wie\s+lange|anzahl|chf|\btage\b|betrag|wieviel", re.IGNORECASE
)
FOLLOW_UP = re.compile(
    r"\b(falls|wenn)\s+(ja|nein)\b|\bund\s+(wann|wie|weshalb|warum)\b", re.IGNORECASE
)

# Facts whose wording is intentionally compound (one fact in the law team's dossier); reviewed in the audit document.
ALLOW_COMPOUND: set[str] = {
    "arrears_paid_timing"
}  # one choice covers both parts (nicht bezahlt / vor / nach Fristablauf)


@dataclass(frozen=True)
class Finding:
    severity: str  # "error" | "hint"
    issue_id: str
    fact_id: str
    rule: str
    text: str


def audit(kb: KnowledgeBase) -> list[Finding]:
    out: list[Finding] = []
    for iid, issue in kb.issues.items():
        if issue.content_status == "DEMO_SYNTHETIC":
            continue
        for f in issue.facts:
            q = f.question_de or ""

            def add(sev: str, rule: str, f=f, iid=iid, q=q) -> None:
                out.append(Finding(sev, iid, f.id, rule, q))

            for field in (q, f.why_needed_de or ""):
                if UPLOAD.search(field):
                    out.append(Finding("error", iid, f.id, "upload_requested", field))
            t = f.data_type
            if t == "boolean" and OPEN_START.match(q):
                add("error", "open_question_on_yes_no_fact")
            if t == "date" and not DATE_WORDS.search(q):
                add("error", "date_fact_without_date_question")
            if t == "integer" and not NUMBER_WORDS.search(q):
                add("error", "number_fact_without_number_question")
            if t == "enum" and not f.enum_values:
                add("error", "choice_without_options")
            if f.id not in ALLOW_COMPOUND:
                if q.count("?") >= 2 and t != "string":
                    add("hint", "several_question_marks")
                if t != "string" and FOLLOW_UP.search(q):
                    add("hint", "follow_up_inside_question")
    return out
