"""Deterministic keyword signals per legal issue.

Two uses, both WITHOUT any AI call:

* the mock provider (development/tests) derives its issue detection from these patterns;
* the case service uses ``candidate_issue_ids`` as a cheap *pre-filter* to keep the fact catalog that is sent
  to the real model small (cost control): only facts of issues that plausibly apply are offered.

Detection by the real model stays authoritative; these patterns never decide anything legal.
"""

from __future__ import annotations

import re

I = re.IGNORECASE  # noqa: E741

ISSUE_PATTERNS: list[tuple[str, float, re.Pattern]] = [
    # --- Issue 1: Kündigung durch die Vermieterschaft ---------------------------------------------------
    (
        "CH_TENANCY_TERMINATION",
        0.9,
        re.compile(
            r"vermieter\w*.{0,60}kündig|kündigung\s+(für|der)\s+(ihre|seine|die|unsere)?\s*wohnung"
            r"|kündigung\s+(\w+\s+){0,2}wohnung|wohnung\w*.{0,40}(gekündigt|kündigung)|kündigungsformular|mietkündigung|eigenbedarf"
            r"|wohnung\w*\s+(zurück|verlassen)",
            I,
        ),
    ),
    (
        "CH_TENANCY_TERMINATION",
        0.6,
        re.compile(r"wohnung\w*\s+(zu\s+)?verlier|miete\w*\s+nicht\s+mehr\s+bezahlen", I),
    ),
    # --- Issue 2: Zahlungsaufforderung mit Kündigungsandrohung -------------------------------------------
    (
        "CH_TENANCY_PAYMENT_WARNING",
        0.9,
        re.compile(
            r"(zahlungsaufforderung|mahnung)\w*.{0,100}(kündigungsandrohung|androhung|angedroht|kündigung\s+angedroht|"
            r"mit\s+kündigung\s+gedroht|frist)"
            r"|(kündigungsandrohung|androhung\s+der\s+kündigung)"
            r"|mietrückstand\w*.{0,60}(mahnung|zahlungsfrist|frist\s+gesetzt)"
            r"|257\s?d|letzte\s+mahnung|zahlungsfrist\s+von\s+\d+\s+tagen",
            I,
        ),
    ),
    # --- Issue 3: Kündigung wegen Zahlungsverzug ---------------------------------------------------------
    (
        "CH_TENANCY_PAYMENT_DEFAULT",
        0.9,
        re.compile(
            r"gekündigt.{0,80}(zahlungsrückstand|zahlungsverzug|mietrückstand|mietzinsrückstand|nicht\s+(rechtzeitig\s+)?bezahlt)"
            r"|(zahlungsrückstand|zahlungsverzug|mietrückstand|mietzinsrückstand).{0,80}(gekündigt|kündigung\s+erhalten)"
            r"|kündigung\s+wegen\s+(zahlungs|mietzins|miet)\w*"
            r"|mahnung.{0,80}danach\s+(die\s+)?kündigung|kündigung\s+nach\s+(der\s+)?mahnung",
            I,
        ),
    ),
    # --- Issue 4: Erstreckung -----------------------------------------------------------------------------
    (
        "CH_TENANCY_EXTENSION",
        0.85,
        re.compile(
            r"erstreckung|mehr\s+zeit\s+(zum|für\s+den)\s+(auszug|umzug)|findet\s+keine\s+(neue\s+|passende\s+)?wohnung"
            r"|keine\s+(neue\s+|passende\s+|ersatz)wohnung\s+(finden|gefunden)|wohnungssuche\s+(ist\s+)?schwierig",
            I,
        ),
    ),
    # --- Issue 5: Mängel ----------------------------------------------------------------------------------
    (
        "CH_TENANCY_DEFECTS",
        0.85,
        re.compile(
            r"schimmel|mängel|mangel|heizung\w*\s+(ist\s+)?(defekt|kaputt|ausgefallen)|feucht|wasserschaden|ungeziefer"
            r"|miete\s+(gekürzt|zurückbehalten|hinterlegt)|mietzins\w*\s+(gekürzt|zurückbehalten|hinterlegt)|hinterleg"
            r"|weniger\s+miete\s+bezahlt",
            I,
        ),
    ),
    # --- Issue 6: Ausweisung und Räumung ------------------------------------------------------------------
    (
        "CH_TENANCY_EVICTION",
        0.95,
        re.compile(
            r"ausweisung|ausweis\w*\s+aus\s+(der|meiner|ihrer|seiner|unserer)\s+wohnung|aus\s+der\s+wohnung\s+ausweis\w*|räumung|räumen|ammannamt|stadtammann|gemeindeammann|einzelgericht|audienz"
            r"|schloss\s+(ausgewechselt|gewechselt)|klare[nr]?\s+fälle|ausweisungsgesuch",
            I,
        ),
    ),
    # --- Issue 7: Mietzinserhöhung ------------------------------------------------------------------------
    (
        "CH_TENANCY_RENT_INCREASE",
        0.9,
        re.compile(
            r"mietzinserhöhung|mietzins\w*\s+(.{0,30}\s+)?erhöh|\w*miete\w*\s+.{0,40}erhöht(\s+wird|\s+wurde)?"
            r"|erhöh\w*\s+(\w+\s+)?\w*(miete|mietzins)|mietzinsanpassung|neue\s+nebenkosten|referenzzins"
            r"|einseitige\s+vertragsänderung|269\s?d",
            I,
        ),
    ),
    # --- Legacy-Demo-Issues (nur für alte Fälle / Tests; nicht im produktiven Katalog) --------------------
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


def candidate_issue_ids(texts: list[str], available: set[str]) -> list[str]:
    """Issue ids (in catalog order) whose keyword signal appears in any of the texts."""
    out: list[str] = []
    for issue_id, _conf, pat in ISSUE_PATTERNS:
        if issue_id in available and issue_id not in out and any(pat.search(t) for t in texts):
            out.append(issue_id)
    return out
