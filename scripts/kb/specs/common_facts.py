"""Fakten, die mehrere der Issues 2-7 gemeinsam nutzen (gleiche ID = gleiche Frage, wird pro Fall nur einmal gestellt)."""

from kb_common import F, eq, fact

CHILDREN = fact(
    "children_in_household", "Kinder im Haushalt", "Leben Kinder in der Wohnung?",
    "Soziale Notfallplanung bzw. Härtegrund; verändert keine Rechtsfolge, wohl aber den Unterstützungsbedarf.",
    group="social", prio="medium", esc=True, src=["PRODUKTREGEL"],
    hint="true bei Kindern im Haushalt; false bei ausdrücklich keine Kinder.")

HOUSING_SOLUTION = fact(
    "housing_solution_available", "Anschlusslösung vorhanden",
    "Gibt es eine Unterkunft nach dem Auszug (Anschlusslösung)?",
    "Ohne Anschlusslösung muss der Sozialdienst sofort eine Notunterkunft prüfen.",
    group="social", prio="high", esc=True, src=["PRODUKTREGEL"])

CHALLENGE_FILED = fact(
    "challenge_filed", "Kündigung bereits angefochten",
    "Hat die Klientin die Kündigung schon bei der Schlichtungsbehörde angefochten oder eine Erstreckung verlangt?",
    "Laufendes Verfahren (Art. 273 OR); schützt aber nicht automatisch vor der Ausweisung (BGE 141 III 262 E. 3.3).",
    group="history", prio="high", esc=True, src=["CH_OR_273_1", "BGE_141_III_262"])

LANDLORD_SELF_HELP = fact(
    "landlord_self_help", "Selbsthilfe der Vermieterschaft",
    "Hat die Vermieterschaft ohne Gericht das Schloss gewechselt, Sachen entfernt oder Strom und Wasser abgestellt?",
    "Unzulässige Selbsthilfe: eine Räumung braucht einen Gerichtsentscheid (Lehrbuch N 3025d; Art. 343 ZPO).",
    group="history", prio="high", esc=True, src=["CH_ZPO_343_1_D", "LEHRBUCH_MIETE_31"])

RENT_RECEIVED_SOCIAL = fact(
    "social_assistance_received", "Bezug von Sozialhilfe", "Bezieht die Klientin Sozialhilfe?",
    "Mietzinsgarantie, Übernahme eines Rückstands, Mietzinslimite. Daten über Sozialhilfe sind besonders schützenswert (Art. 5 lit. c Ziff. 6 DSG).",
    group="social", prio="medium", src=["CH_DSG_6_7"])

COMMON = {
    f["id"]: f for f in [CHILDREN, HOUSING_SOLUTION, CHALLENGE_FILED, LANDLORD_SELF_HELP, RENT_RECEIVED_SOCIAL]
}


def common(*ids: str) -> list[dict]:
    return [dict(COMMON[i]) for i in ids]
