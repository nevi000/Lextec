"""Deterministic, keyword-based mock provider for development and tests (no API key needed).

It is intentionally simple: it demonstrates the pipeline end to end and is NOT a model of
real language understanding. The real extraction is done by Gemini (see gemini.py).
"""

from __future__ import annotations

import re
from datetime import date

from app.services.ai.base import CallContext
from app.services.ai.schemas import (
    DetectedIssue,
    ExtractedFact,
    ExtractionInput,
    ExtractionResult,
    FactCatalogEntry,
    InputMessage,
    UnrecognizedIssue,
)

I = re.IGNORECASE  # noqa: E741

MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}
_MONTH_RE = "|".join(MONTHS)
DATE_PAT = rf"(?:\d{{1,2}}\.\s?(?:\d{{1,2}}\.|(?:{_MONTH_RE}))\s?\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"
DATE_RE = re.compile(DATE_PAT, I)


def to_iso(text: str) -> str | None:
    """'4. November 2026' / '04.11.2026' / '2026-11-04' -> ISO date, else None."""
    t = text.strip().casefold()
    try:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
        if m:
            return date(*map(int, m.groups())).isoformat()
        m = re.fullmatch(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})", t)
        if m:
            d, mo, y = map(int, m.groups())
            return date(y, mo, d).isoformat()
        m = re.fullmatch(rf"(\d{{1,2}})\.\s?({_MONTH_RE})\s?(\d{{4}})", t)
        if m:
            return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return None
    return None


ISSUE_PATTERNS: list[tuple[str, float, re.Pattern]] = [
    (
        "CH_TENANCY_TERMINATION",
        0.9,
        re.compile(
            r"vermieter\w*.{0,60}kündig|kündigung\s+(für|der)\s+(ihre|seine|die|unsere)?\s*wohnung"
            r"|wohnung\w*.{0,40}(gekündigt|kündigung)|kündigungsformular|mietkündigung|eigenbedarf"
            r"|wohnung\w*\s+(zurück|verlassen)",
            I,
        ),
    ),
    (
        "CH_TENANCY_TERMINATION",
        0.6,
        re.compile(
            r"wohnung\w*\s+(zu\s+)?verlier|miete\w*\s+nicht\s+mehr\s+bezahlen|mietzins|räumung", I
        ),
    ),
    (
        "tenancy_defects",
        0.85,
        re.compile(r"schimmel|mängel|mangel|heizung\w*\s+(ist\s+)?(defekt|kaputt)|feucht", I),
    ),
    (
        "employment_termination",
        0.9,
        re.compile(
            r"(arbeitgeber|arbeitsstelle|arbeitsverhältnis|arbeitsvertrag|chef).{0,60}kündig"
            r"|kündig.{0,60}(arbeitsstelle|arbeitsverhältnis|arbeitsvertrag)",
            I,
        ),
    ),
    (
        "unpaid_salary",
        0.85,
        re.compile(
            r"(lohn|gehalt)\w*.{0,50}(nicht\s+(bezahlt|erhalten|überwiesen)|ausstehend|unbezahlt|offen)"
            r"|(nicht|kein)\w*\s+(lohn|gehalt)",
            I,
        ),
    ),
]

UNSUPPORTED_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Familienrecht", re.compile(r"scheidung|sorgerecht|unterhaltsbeitr|alimente", I)),
    ("Erbrecht", re.compile(r"erbschaft|testament|erbteil", I)),
    ("Strafrecht", re.compile(r"strafverfahren|strafanzeige|polizei\w*\s+vorgeladen|vorladung", I)),
    ("Steuerrecht", re.compile(r"steuerverfahren|steuererklärung|steuerrekurs", I)),
    ("Ausländerrecht", re.compile(r"aufenthaltsbewilligung|asylverfahren|ausweisung", I)),
]

# (fact_id, value, pattern). Value "@date" = take the date captured by group 'd' / 'd2'.
FACT_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # --- demo issues ---
    (
        "employer_termination_received",
        "ja",
        re.compile(r"(arbeitgeber|chef).{0,40}gekündigt|kündigung erhalten", I),
    ),
    (
        "incapacity_for_work",
        "ja",
        re.compile(r"krankgeschrieben|arbeitsunfähig|wegen\s+krankheit|unfall", I),
    ),
    (
        "landlord_informed",
        "ja",
        re.compile(
            r"vermieter\w*\s+(ist\s+|wurde\s+)?(informiert|gemeldet|benachrichtigt)"
            r"|dem\s+vermieter\s+(gemeldet|mitgeteilt)",
            I,
        ),
    ),
    (
        "landlord_informed",
        "nein",
        re.compile(r"vermieter\w*\s+(ist\s+|wurde\s+)?(noch\s+)?nicht\s+(informiert|gemeldet)", I),
    ),
    # --- Issue 1: Kündigung durch die Vermieterschaft ---
    ("property_municipality", "Zürich", re.compile(r"\bin\s+(der\s+)?(Stadt\s+)?Zürich\b", I)),
    (
        "property_municipality",
        "Winterthur",
        re.compile(r"\bin\s+(der\s+)?(Stadt\s+)?Winterthur\b", I),
    ),
    (
        "property_in_canton_zh",
        "ja",
        re.compile(r"\bin\s+(der\s+)?(Stadt\s+)?(Zürich|Winterthur)\b|Kanton\s+Zürich", I),
    ),
    (
        "tenant_role",
        "hauptmieterin",
        re.compile(r"alleinige[rn]?\s+Mieter(in)?|Hauptmieter(in)?|selbst\s+Mieterin", I),
    ),
    (
        "tenant_role",
        "untermieterin",
        re.compile(r"\bist\s+Untermieterin\b|\bUntermieterin\s+(von|bei)\b", I),
    ),
    (
        "co_tenants_exist",
        "nein",
        re.compile(r"keine\s+(weiteren\s+)?Mitmieter|alleinige[rn]?\s+Mieter(in)?", I),
    ),
    ("object_type", "wohnung", re.compile(r"(normale|gewöhnliche)[nr]?\s+Wohnung", I)),
    ("object_type", "moebliertes_zimmer", re.compile(r"möblierte[sn]?\s+Zimmer", I)),
    (
        "object_type",
        "ferienwohnung_bis_3_monate",
        re.compile(r"(ist|handelt\s+sich\s+um)\s+eine\s+Ferienwohnung", I),
    ),
    ("contract_term_type", "unbefristet", re.compile(r"unbefristet", I)),
    ("contract_term_type", "befristet", re.compile(r"(?<!un)befristet", I)),
    (
        "delivery_method",
        "normale_post",
        re.compile(r"normale[rn]?\s+Post|gewöhnliche[rn]?\s+Brief", I),
    ),
    ("delivery_method", "eingeschrieben", re.compile(r"eingeschrieben|Einschreiben", I)),
    (
        "delivery_method",
        "persoenlich",
        re.compile(r"persönlich\s+(übergeben|erhalten|überreicht)", I),
    ),
    (
        "receipt_date",
        "@date",
        re.compile(
            rf"(?P<d>{DATE_PAT})[^.]{{0,70}}(erhalten|bekommen|zugestellt|erhielt)"
            rf"|(erhalten|bekommen|erhielt)[^.]{{0,40}}\bam\s+(?P<d2>{DATE_PAT})",
            I,
        ),
    ),
    ("termination_date", "@date", re.compile(rf"\bper\s+(?P<d>{DATE_PAT})", I)),
    (
        "official_form_used",
        "nein",
        re.compile(
            r"ohne\s+(das\s+)?amtliche[sn]?\s+Kündigungsformular"
            r"|kein(?:es|en)?\s+amtliche[sn]?\s+(Kündigungs)?[Ff]ormular|nicht\s+auf\s+(dem\s+)?amtlichen",
            I,
        ),
    ),
    (
        "already_reacted",
        "nein",
        re.compile(r"noch\s+nichts\s+unterschrieben|keine\s+Anfechtung|nicht\s+angefochten", I),
    ),
    (
        "family_home_with_spouse",
        "nein",
        re.compile(r"keine\s+Ehe\S*\s+(oder|und)\s+eingetragene|nicht\s+verheiratet", I),
    ),
    (
        "termination_kind",
        "ordentlich",
        re.compile(r"keine\s+Mietrückstände|ordentliche\s+Kündigung", I),
    ),
    (
        "termination_kind",
        "zahlungsverzug",
        re.compile(r"wegen\s+(Mietzins|Zahlungs)rückstand|Zahlungsverzug", I),
    ),
    ("stated_reason", "eigenbedarf", re.compile(r"Eigenbedarf", I)),
    ("stated_reason", "sanierung", re.compile(r"Sanierung|Umbau", I)),
    ("stated_reason", "abbruch", re.compile(r"Abbruch", I)),
    ("hardship_present", "ja", re.compile(r"Härtegründe?|alleinerziehend|mehrere\s+Kinder", I)),
    (
        "eviction_or_court_proceeding",
        "ja",
        re.compile(r"Ausweisung|Räumungsklage|Gerichtsverfahren\s+läuft", I),
    ),
    (
        "client_requests_expert",
        "ja",
        re.compile(
            r"(möchte|wünscht|will)\s+(eine[nr]?\s+)?(Anwalt|Anwältin|Fachperson|Jurist\w*)", I
        ),
    ),
]

_UNKNOWN_WORDS = re.compile(
    r"\b(weiss|weiß)\s+(ich\s+|es\s+|sie\s+)?nicht\b|keine\s+Ahnung|unbekannt", I
)


def _find(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    return m.group(0) if m else None


def _parse_answer(entry: FactCatalogEntry, text: str) -> tuple[str, bool, bool]:
    """Returns (value_text, ambiguous, unknown)."""
    low = text.casefold()
    if _UNKNOWN_WORDS.search(text):
        return "", False, True
    if entry.data_type == "boolean":
        yes = re.search(r"\b(ja|jawohl|genau|stimmt)\b", low)
        no = re.search(r"\b(nein|nicht|kein|keine|nie)\b", low)
        if yes and not no:
            return "ja", False, False
        if no and not yes:
            return "nein", False, False
        return text, True, False
    if entry.data_type == "date":
        m = DATE_RE.search(text)
        iso = to_iso(m.group(0)) if m else None
        return (iso, False, False) if iso else (text, True, False)
    if entry.data_type == "integer":
        m = re.search(r"\d[\d'’.]*", text)
        return (m.group(0), False, False) if m else (text, True, False)
    if entry.data_type == "enum":
        for ev in entry.enum_values:
            label = entry.enum_labels_de.get(ev, "").casefold()
            if ev.casefold() in low or (label and label in low):
                return ev, False, False
        return text, True, False
    return text.strip(), False, False


class MockAIProvider:
    name = "mock"
    model = "mock-keyword-v2"

    def extract(self, data: ExtractionInput, ctx: CallContext | None = None) -> ExtractionResult:
        catalog = {f.id: f for f in data.fact_catalog}
        issue_ids = {i.id for i in data.issue_catalog}
        issues: dict[str, DetectedIssue] = {}
        unsupported: dict[str, UnrecognizedIssue] = {}
        facts: dict[str, ExtractedFact] = {}

        for msg in data.new_messages:
            self._scan_message(msg, catalog, issue_ids, issues, unsupported, facts)

        first = (data.new_messages[0].content if data.new_messages else "").strip()
        summary = data.existing_summary or (first[:280] + ("…" if len(first) > 280 else ""))
        return ExtractionResult(
            detected_issues=list(issues.values()),
            facts=list(facts.values()),
            unrecognized_issues=list(unsupported.values()),
            summary_de=summary,
        )

    def _scan_message(
        self,
        msg: InputMessage,
        catalog: dict[str, FactCatalogEntry],
        issue_ids: set[str],
        issues: dict[str, DetectedIssue],
        unsupported: dict[str, UnrecognizedIssue],
        facts: dict[str, ExtractedFact],
    ) -> None:
        text = msg.content
        if msg.answers_fact_id and msg.answers_fact_id in catalog:
            value, ambiguous, unknown = _parse_answer(catalog[msg.answers_fact_id], text)
            quote = text.strip()
            facts[msg.answers_fact_id] = ExtractedFact(
                fact_id=msg.answers_fact_id,
                value=value,
                ambiguous=ambiguous,
                unknown=unknown,
                ambiguity_note="Antwort nicht eindeutig." if ambiguous else None,
                evidence_quote=quote,
                source_message_id=msg.id,
            )
            if len(quote) < 60:  # a long free-text answer may carry more facts: fall through
                return

        for issue_id, conf, pat in ISSUE_PATTERNS:
            quote = _find(pat, text)
            if quote and issue_id in issue_ids:
                prev = issues.get(issue_id)
                if prev is None or conf > prev.confidence:
                    issues[issue_id] = DetectedIssue(
                        issue_id=issue_id,
                        confidence=conf,
                        evidence_quote=quote,
                        source_message_id=msg.id,
                    )
        for label, pat in UNSUPPORTED_PATTERNS:
            quote = _find(pat, text)
            if quote and label not in unsupported:
                unsupported[label] = UnrecognizedIssue(
                    description=label, evidence_quote=quote, source_message_id=msg.id
                )
        for fact_id, value, pat in FACT_PATTERNS:
            if fact_id not in catalog or fact_id in facts:
                continue
            m = pat.search(text)
            if not m:
                continue
            quote = m.group(0)
            if value == "@date":
                raw = m.groupdict().get("d") or m.groupdict().get("d2")
                iso = to_iso(raw) if raw else None
                if not iso:
                    continue
                value = iso
            facts[fact_id] = ExtractedFact(
                fact_id=fact_id, value=value, evidence_quote=quote, source_message_id=msg.id
            )

    def rephrase_question(
        self, question_de: str, context: str, ctx: CallContext | None = None
    ) -> str:
        return question_de
