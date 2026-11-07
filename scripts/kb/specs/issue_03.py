"""Issue 3 - Kündigung wegen Zahlungsverzug (Art. 257d Abs. 2 OR). Quelle: issue_03.docx."""

from common_facts import common
from issue_02 import facts as F2
from kb_common import (
    ALWAYS, D, F, all_, any_, eq, esc_rule, fact, gt, inn, known, legal, lt, scenario, shared_facts, unk,
)

ID = "CH_TENANCY_PAYMENT_DEFAULT"
BOTH = ["tenancy_law_counsel", "social_counselling"]
LEGAL = ["tenancy_law_counsel"]


def _from2(*ids):
    by = {f["id"]: f for f in F2}
    return [dict(by[i]) for i in ids]


facts = (
    shared_facts(
        [
            "tenant_role", "object_type", "property_municipality", "client_residence_municipality", "property_in_canton_zh", "co_tenants_exist",
            "co_tenants_all_notified", "delivery_method", "pickup_notice_date", "receipt_date", "official_form_used",
            "family_home_with_spouse", "spouse_still_lives_there", "separate_delivery_to_spouse", "termination_date",
            "eviction_or_court_proceeding", "rent_payer", "vulnerability_present", "client_requests_expert", "consent_briefing",
        ]
    )
    + _from2(
        "warning_written", "warning_threat_present", "warning_amount_clear", "warning_deadline_days", "warning_delivery_method",
        "warning_receipt_date", "warning_pickup_notice_date", "payment_path", "third_party_payment", "payment_returned_by_landlord",
        "social_payment_failed", "rent_withheld_for_defects", "payment_agreement_present", "amount_disputed",
    )
    + [
        # --- Prüffrage 2: Zahlung -----------------------------------------------------------
        fact("paid_in_time", "Zahlung innert Frist",
             "Wurde der ganze Betrag innert der Zahlungsfrist bezahlt?",
             "Rechtzeitige vollständige Zahlung macht die Kündigung unwirksam (BGE 124 III 145 E. 2b).",
             type="enum", group="payment",
             enum={"vollstaendig_rechtzeitig": "Vollständig und rechtzeitig bezahlt", "teilweise": "Nur teilweise bezahlt",
                   "nicht_bezahlt": "Nicht bezahlt", "nur_nach_fristablauf": "Erst nach Fristablauf bezahlt"},
             req=True, prio="high", esc=True, src=["BGE_124_III_145", "BGE_119_II_232"]),
        fact("partial_payment_with_notice", "Teilzahlung mit Hinweis an die Vermieterschaft",
             "Wurde nur ein Teil bezahlt und die Vermieterschaft dabei schriftlich darauf hingewiesen?",
             "Wer den nach eigenem Wissen geschuldeten Betrag zahlt und informiert, wird geschützt (4A_332/2025 E. 3.5.2).",
             group="payment", req_if=eq(F("paid_in_time"), "teilweise"), esc=True, deps=["paid_in_time"],
             src=["BGER_4A_332_2025", "BGE_140_III_591"]),
        fact("setoff_or_deposit_done", "Verrechnet oder hinterlegt",
             "Wurde verrechnet oder hinterlegt?",
             "Verrechnung nur innert Frist und gegenüber der Vermieterschaft; Hinterlegung bereits fälliger Mietzinse tilgt nicht (BGE 147 III 218).",
             group="payment", req=True, prio="high", esc=True, src=["BGE_147_III_218", "OGZH_LF250009"]),
        fact("payment_after_deadline_accepted", "Zahlung nach Fristablauf von der Vermieterschaft angenommen",
             "Hat die Vermieterschaft eine Zahlung angenommen, die nach Fristablauf erfolgte?",
             "Heilt die Kündigung nicht (BGE 119 II 232 E. 3).", group="payment", prio="medium", esc=True,
             src=["BGE_119_II_232"]),
        # --- Prüffrage 3: Kündigung ---------------------------------------------------------
        fact("termination_before_deadline_end", "Kündigung vor Ablauf der Zahlungsfrist",
             "Wurde die Kündigung vor Ablauf der Zahlungsfrist ausgesprochen oder zugestellt?",
             "Neuere Praxis: unwirksam (4A_585/2010 E. 3.1); älter anfechtbar (BGE 119 II 147 E. 4). Ausnahme bei Zugang nach Fristablauf.",
             group="termination", req=True, prio="high", esc=True, src=["BGER_4A_585_2010", "BGE_119_II_147"]),
        fact("days_between_deadline_and_termination", "Tage zwischen Fristablauf und Kündigung",
             "Wie lange wartete die Vermieterschaft nach Fristablauf bis zur Kündigung (ungefähr in Tagen)?",
             "Zu langes Zuwarten kann als Verzicht gedeutet werden; ab 14 Tagen gibt das System einen Prüfhinweis (Teamentscheid). Keine feste gesetzliche Grenze.",
             type="integer", group="termination", prio="low", src=["BGER_4A_366_2008", "LEHRBUCH_MIETE_31"]),
        fact("special_circumstances", "Besondere Umstände",
             "Gab es Absprachen, einen Ratenplan, ein vereinbartes Gespräch, einen falschen Betrag oder einen sehr kleinen Rest?",
             "Treu und Glauben, sehr eng (BGE 140 III 591 E. 1; BGE 120 II 31).", group="termination", prio="medium", esc=True,
             src=["BGE_140_III_591", "BGE_120_II_31"]),
        # --- Lage danach --------------------------------------------------------------------
    ]
    + common("challenge_filed", "housing_solution_available", "children_in_household", "landlord_self_help")
)
# Pflichtangaben der Lage danach laut Dossier
for _f in facts:
    if _f["id"] in ("challenge_filed", "housing_solution_available"):
        _f["required"] = True

DERIVED = [
    {"id": "days_since_earliest_receipt", "kind": "days_since_earliest", "facts": ["pickup_notice_date", "receipt_date"],
     "description": "Tage seit dem frühesten bekannten Empfangshinweis der Kündigung (INTERNE Schwelle, kein Fristende)."},
]

escalation = [
    esc_rule("PD_OUT_OF_SCOPE_ROLE", "Klientin nicht Hauptmieterin: ausserhalb des Moduls.",
             inn(F("tenant_role"), ["untermieterin", "andere"]), "MEDIUM", "OUT_OF_SCOPE_NOT_MAIN_TENANT",
             "Die Klientin ist nicht selbst Hauptmieterin (z. B. Untermiete). Dieses Modul gilt dafür nicht; es werden keine Standardaussagen gemacht. Eine unabhängige Rechtsperson muss prüfen.",
             ["lawyer_general"], suppress=True),
    esc_rule("PD_OUT_OF_SCOPE_OBJECT", "Geschäftsraum/Ferienwohnung/Notunterkunft: ausserhalb des Moduls.",
             inn(F("object_type"), ["notwohnung_heim", "ferienwohnung_bis_3_monate", "andere"]), "MEDIUM", "OUT_OF_SCOPE_OBJECT",
             "Das Objekt fällt nicht unter die gewöhnliche Wohnraummiete dieses Moduls. Es werden keine Standardaussagen gemacht. Eine unabhängige Rechtsperson muss prüfen.",
             ["lawyer_general"], suppress=True),
    esc_rule("PD_NOT_ZH", "Wohnung nicht im Kanton Zürich.", eq(F("property_in_canton_zh"), False), "MEDIUM",
             "AUTHORITY_NOT_DETERMINABLE",
             "Die Wohnung liegt nicht im Kanton Zürich. Die Zürcher Stellenangaben gelten nicht; die zuständigen Stellen müssen separat bestimmt werden.", LEGAL),
    # Grundregel: jede Kündigung wegen Zahlungsverzug eskaliert sofort, rechtlich UND sozial (kein Erfolgsprognose)
    esc_rule("PD_GRUNDREGEL", "Jede Kündigung wegen Zahlungsverzug: sofort Rechtsperson + Sozialarbeiterin.", ALWAYS, "HIGH",
             "PAYMENT_DEFAULT_TERMINATION_IMMEDIATE",
             "Kündigung wegen Zahlungsverzug: Die Anfechtungsfrist von 30 Tagen kann laufen, eine Erstreckung ist ausgeschlossen und eine schnelle Ausweisung ist möglich. Rechtsperson und Sozialarbeiterin handeln sofort und parallel (Unterkunft sichern). Das System macht keine Erfolgsprognose.",
             BOTH),
    esc_rule("PD_EMPFANG_UNBEKANNT_ODER_GE20", "Empfang der Kündigung unbekannt oder 20+ Tage seit Empfang: höchste Priorität.",
             any_(unk(F("receipt_date")), unk(F("delivery_method")), unk(F("pickup_notice_date")),
                  gt(D("days_since_earliest_receipt"), 19)),
             "HIGH", "TERMINATION_RECEIPT_UNKNOWN_OR_20_DAYS",
             "Das Empfangsdatum der Kündigung ist unbekannt oder es sind seit dem frühesten Empfangshinweis 20 oder mehr Tage vergangen. Die Anfechtungsfrist (30 Tage) ist knapp oder unbestimmbar: höchste Priorität (Produktschwelle, keine Gesetzesfrist).",
             LEGAL),
    esc_rule("PD_PRUEFFRAGE1_MAHNUNG", "Keine Mahnung, fehlerhafte Mahnung oder zu kurze Frist (Prüffrage 1).",
             any_(eq(F("warning_written"), False), eq(F("warning_threat_present"), False), eq(F("warning_amount_clear"), False),
                  lt(F("warning_deadline_days"), 30)),
             "HIGH", "WARNING_DEFECT_POSSIBLE",
             "Die vorausgehende Mahnung fehlt oder ist möglicherweise fehlerhaft (Schriftlichkeit, Androhung, Betrag, Frist unter 30 Tagen). Eine Kündigung wegen Zahlungsverzug setzt eine gültige Mahnung voraus; keine Entwarnung, da die Vermieterschaft neu mahnen oder ordentlich kündigen kann. Rechtsperson sofort.",
             LEGAL),
    esc_rule("PD_PRUEFFRAGE2_ZAHLUNG", "Angabe 'innert Frist bezahlt', Teilzahlung mit Hinweis, Verrechnung/Hinterlegung (Prüffrage 2).",
             any_(eq(F("paid_in_time"), "vollstaendig_rechtzeitig"),
                  all_(eq(F("paid_in_time"), "teilweise"), eq(F("partial_payment_with_notice"), True)),
                  eq(F("setoff_or_deposit_done"), True), eq(F("third_party_payment"), True)),
             "HIGH", "PAYMENT_IN_TIME_OR_SETOFF_CLAIMED",
             "Es wird geltend gemacht, dass innert Frist gezahlt, verrechnet, hinterlegt oder durch Dritte bezahlt wurde. Alle Belege mit Datum (Auftrag und Gutschrift) sichern. Rechtsperson sofort.",
             LEGAL),
    esc_rule("PD_PRUEFFRAGE3_FORM", "Kündigung vor Fristablauf, kein Formular, Familienwohnung/Mitmieter nicht separat (Prüffrage 3).",
             any_(eq(F("termination_before_deadline_end"), True), eq(F("official_form_used"), False),
                  all_(eq(F("family_home_with_spouse"), True), eq(F("spouse_still_lives_there"), True),
                       eq(F("separate_delivery_to_spouse"), False)),
                  eq(F("co_tenants_all_notified"), False)),
             "HIGH", "TERMINATION_FORM_OR_TIMING_DEFECT_POSSIBLE",
             "Mögliche Mängel der Kündigung: vor Ablauf der Zahlungsfrist ausgesprochen, ohne amtliches Formular oder nicht separat/allen zugestellt. Keine Entwarnung; Rechtsperson sofort.",
             LEGAL),
    esc_rule("PD_GERICHT", "Gesuch ans Gericht, Vorladung oder Räumungstermin: Wechsel zu Issue 6.",
             eq(F("eviction_or_court_proceeding"), True), "HIGH", "COURT_OR_EVICTION_PROCEEDING",
             "Es liegt ein Gesuch, eine Vorladung oder ein Räumungstermin vor. Dafür gilt Issue 6 (Ausweisung und Räumung). Sofortige rechtliche und soziale Prüfung.",
             BOTH, route="CH_TENANCY_EVICTION"),
    esc_rule("PD_SELBSTHILFE", "Vermieterschaft räumt selbst oder sperrt aus: unzulässige Selbsthilfe.",
             eq(F("landlord_self_help"), True), "HIGH", "LANDLORD_SELF_HELP",
             "Die Vermieterschaft hat ohne Gericht geräumt, das Schloss gewechselt oder Leistungen abgestellt. Das ist unzulässig und kann strafbar sein; das System bewertet das nicht. Rechtsperson und Sozialarbeiterin sofort, nötigenfalls Polizei.",
             BOTH, route="CH_TENANCY_EVICTION"),
    esc_rule("PD_SOZIALDIENST_ZAHLT", "Sozialdienst zahlt direkt: Interessenkonflikt, unabhängige Beratung.",
             eq(F("rent_payer"), "sozialdienst"), "HIGH", "SOCIAL_SERVICE_IS_PAYER",
             "Der Sozialdienst zahlt die Miete direkt und ist selbst beteiligt. Eine unabhängige Rechtsperson muss prüfen.",
             ["independent_legal_body", "social_counselling"]),
    esc_rule("PD_KEINE_ANSCHLUSSLOESUNG", "Kinder, Gesundheit oder keine Anschlusslösung: Unterkunft sofort sichern.",
             any_(eq(F("housing_solution_available"), False), unk(F("housing_solution_available"))), "HIGH",
             "NO_HOUSING_SOLUTION",
             "Es gibt keine Anschlusslösung (oder sie ist unbekannt). Weil keine Erstreckung möglich ist, muss die Sozialarbeiterin sofort Unterkunft und Notunterkunft prüfen.",
             ["social_counselling"]),
    esc_rule("PD_BESONDERE_UMSTAENDE", "Absprachen, Ratenplan, falscher Betrag: Treu und Glauben.",
             any_(eq(F("special_circumstances"), True), eq(F("payment_agreement_present"), True)), "HIGH",
             "SPECIAL_CIRCUMSTANCES_PRESENT",
             "Es gibt besondere Umstände (Absprache, Ratenplan, falscher Betrag). Treuwidrigkeit kommt nur sehr ausnahmsweise in Frage; die Rechtsperson prüft sofort.", LEGAL),
    esc_rule("PD_VULNERABILITY", "Besondere Belastungssituation: ausserhalb des Moduls.", eq(F("vulnerability_present"), True), "MEDIUM",
             "OUTSIDE_MODULE_VULNERABILITY",
             "Es liegt eine besondere Belastungssituation vor. Das liegt ausserhalb dieses Moduls und gehört in menschliche Hände.", BOTH),
    esc_rule("PD_EXPERT_REQUESTED", "Fachperson ausdrücklich gewünscht.", eq(F("client_requests_expert"), True), "LOW",
             "EXPERT_REQUESTED", "Es wurde ausdrücklich eine Fachperson gewünscht. Dieser Wunsch wird immer respektiert.", LEGAL),
]

legal_rules = [
    legal("PD_HINT_ANFECHTUNG", "Anfechtung 30 Tage, kostenlos.", ALWAYS, "HINT_CONTEST_30_DAYS_FREE",
          "Eine Kündigung kann innert 30 Tagen nach Empfang bei der Schlichtungsbehörde angefochten werden; das Verfahren kostet keine Gerichtskosten.",
          ["CH_OR_273_1", "CH_ZPO_113_2_C"]),
    legal("PD_HINT_KEINE_ERSTRECKUNG", "Erstreckung ausgeschlossen.", ALWAYS, "HINT_NO_EXTENSION",
          "Bei einer Kündigung wegen Zahlungsverzug ist eine Erstreckung ausgeschlossen. Die Suche nach einer Unterkunft sollte deshalb sofort beginnen.",
          ["CH_OR_272A_1_A"]),
    legal("PD_HINT_MAHNUNG", "Gültige Mahnung ist Voraussetzung.", ALWAYS, "HINT_VALID_WARNING_REQUIRED",
          "Eine solche Kündigung setzt eine gültige schriftliche Mahnung mit Frist und ausdrücklicher Kündigungsandrohung voraus. Ob das erfüllt ist, prüft eine Fachperson.",
          ["CH_OR_257D_1", "LEHRBUCH_MIETE_31"]),
    legal("PD_HINT_RECHTZEITIG", "Rechtzeitige Zahlung.", any_(eq(F("paid_in_time"), "vollstaendig_rechtzeitig"), eq(F("third_party_payment"), True)),
          "HINT_PAID_IN_TIME",
          "Wurde der ganze Betrag rechtzeitig bezahlt, kann die Kündigung unwirksam sein. Bitte alle Belege mit Datum sichern.",
          ["BGE_124_III_145"]),
    legal("PD_HINT_NACH_FRIST", "Zahlung nach Fristablauf heilt nicht automatisch.",
          any_(eq(F("paid_in_time"), "nur_nach_fristablauf"), eq(F("payment_after_deadline_accepted"), True)), "HINT_LATE_PAYMENT",
          "Eine Zahlung nach Fristablauf macht die Kündigung nicht automatisch unwirksam, auch wenn die Vermieterschaft das Geld annimmt.",
          ["BGE_119_II_232"]),
    legal("PD_HINT_FORM", "Formular und separate Zustellung.", ALWAYS, "HINT_FORM_REQUIRED",
          "Auch bei einer Kündigung muss die Vermieterschaft das amtliche Formular verwenden und bei einer Familienwohnung beiden Ehegatten separat zustellen.",
          ["CH_OR_266L", "CH_OR_266N", "CH_OR_266O"]),
    legal("PD_HINT_SELBSTHILFE", "Keine Selbsthilfe.", eq(F("landlord_self_help"), True), "HINT_NO_SELF_HELP",
          "Die Vermieterschaft darf die Wohnung nicht selbst räumen; dafür braucht es einen Entscheid einer Behörde oder eines Gerichts.",
          ["CH_ZPO_343_1_D", "LEHRBUCH_MIETE_31"]),
    legal("PD_HINT_ANFECHTUNG_SCHUETZT_NICHT", "Anfechtung schützt nicht sicher vor schneller Ausweisung.",
          any_(eq(F("challenge_filed"), True), eq(F("eviction_or_court_proceeding"), True)), "HINT_CHALLENGE_NO_SAFE_PROTECTION",
          "Eine Anfechtung schützt nicht sicher vor einem schnellen Ausweisungsverfahren.", ["BGE_141_III_262"]),
    legal("PD_REVIEW_WARTEZEIT", "Wartezeit nach Fristablauf (Verzicht?).", gt(F("days_between_deadline_and_termination"), 13),
          "REVIEW_WAITING_TIME",
          "Prüfhinweis: Zwischen Fristablauf und Kündigung liegen 14 oder mehr Tage. Zu langes Zuwarten kann als Verzicht gedeutet werden; knapp drei Wochen gelten als Grenze. Keine Entwarnung.",
          ["BGER_4A_366_2008", "LEHRBUCH_MIETE_31"], kind="REVIEW_POINT"),
    legal("PD_REVIEW_VOR_FRIST", "Kündigung vor Fristablauf.", eq(F("termination_before_deadline_end"), True), "REVIEW_TERMINATION_BEFORE_DEADLINE",
          "Prüfhinweis: Eine Kündigung vor Ablauf der Zahlungsfrist ist nach neuerer Praxis unwirksam (ältere Praxis: anfechtbar); der Zeitpunkt des Zugangs entscheidet. Anfechtungsfrist vorsorglich wahren.",
          ["BGER_4A_585_2010", "BGE_119_II_147"], kind="REVIEW_POINT"),
    legal("PD_REVIEW_SPERRFRIST", "Laufendes Verfahren: keine Sperrfrist.", ALWAYS, "REVIEW_NO_BLOCKING_PERIOD",
          "Prüfhinweis: Bei einer Kündigung wegen Zahlungsverzug gelten die Sperrfristen nach einem Schlichtungs- oder Gerichtsverfahren nicht; ein laufendes Verfahren bietet hier keinen Schutz.",
          ["CH_OR_271A_3_B", "LEHRBUCH_MIETE_31"], kind="REVIEW_POINT"),
    legal("PD_REVIEW_KAUTION", "Kaution verhindert die Kündigung nicht.", ALWAYS, "REVIEW_DEPOSIT_NO_PAYMENT",
          "Prüfhinweis: Eine Kaution ist keine Vorauszahlung und verhindert die Kündigung nicht.", ["LEHRBUCH_MIETE_31"], kind="REVIEW_POINT"),
    legal("PD_REVIEW_UMDEUTUNG", "Keine Umdeutung in ordentliche Kündigung.", eq(F("warning_written"), False), "REVIEW_NO_CONVERSION",
          "Prüfhinweis: Ohne gültige Mahnung ist die Zahlungsverzugskündigung unwirksam; eine Umdeutung in eine ordentliche Kündigung ist ausgeschlossen. Die Vermieterschaft kann aber neu mahnen oder ordentlich kündigen.",
          ["BGE_135_III_441", "LEHRBUCH_MIETE_31"], kind="REVIEW_POINT"),
    legal("PD_REVIEW_FALSCHER_TERMIN", "Falscher Termin/zu kurze Frist.", known(F("termination_date")), "REVIEW_WRONG_TERM",
          "Prüfhinweis: Ein falscher Termin oder eine zu kurze Kündigungsfrist macht die Kündigung nicht ungültig; sie gilt auf den nächstmöglichen Termin.",
          ["CH_OR_266A_2", "LEHRBUCH_MIETE_31"], kind="REVIEW_POINT"),
]

SPEC = {
    "id": ID,
    "issue": "payment_default",
    "dossier": "issue_03.docx",
    "title_de": "Kündigung wegen Zahlungsverzug (Issue 3)",
    "description": "Kündigung nach unbenütztem Ablauf der Zahlungsfrist (Art. 257d Abs. 2 OR). Immer sofortige, parallele Eskalation an Rechtsperson und Sozialarbeiterin; Erstreckung ausgeschlossen; keine Erfolgsprognose.",
    "provenance_de": "Law-Dossier Issue 3 vom 7.11.2026; Teamentscheide: Wartezeit-Prüfhinweis ab 14 Tagen, Anfechtungsempfehlung bleibt bei der Rechtsperson, Übertragbarkeit BGE 141 III 262 / 4A_585/2010 auf Wohnungen.",
    "derived": DERIVED,
    "classification": {
        "description": "Passt, wenn die Vermieterschaft wegen Mietzinsrückstand gekündigt hat (Kündigung nach Mahnung, fristlose oder 30-Tage-Kündigung wegen Zahlungsverzug). NICHT passend: Kündigung ohne Zahlungsverzug (Issue 1), Mahnung ohne Kündigung (Issue 2), Gerichtsschreiben (Issue 6).",
        "typical_situations": [
            "Der Vermieter hat wegen Mietrückstand gekündigt.",
            "Meine Klientin hat die Kündigung wegen Zahlungsverzug erhalten.",
            "Nach der Mahnung kam die Kündigung nach Art. 257d.",
            "Die Verwaltung hat gekündigt, weil die Miete nicht rechtzeitig bezahlt wurde.",
        ],
        "related_issues": [],
    },
    "facts": facts,
    "escalation": escalation,
    "legal": legal_rules,
    "default_professionals": ["tenancy_law_counsel", "social_counselling"],
    "briefing": {
        "intro_de": "Kündigung wegen Zahlungsverzug (Art. 257d Abs. 2 OR) – drei Prüffragen",
        "groups": [
            {"id": "q1_warning", "title_de": "Prüffrage 1 – Mahnung",
             "fact_ids": ["warning_written", "warning_threat_present", "warning_amount_clear", "warning_deadline_days",
                          "warning_delivery_method", "warning_receipt_date", "warning_pickup_notice_date"]},
            {"id": "q2_payment", "title_de": "Prüffrage 2 – Zahlung",
             "fact_ids": ["paid_in_time", "payment_path", "partial_payment_with_notice", "setoff_or_deposit_done",
                          "payment_after_deadline_accepted", "third_party_payment", "payment_returned_by_landlord", "rent_payer",
                          "social_payment_failed", "rent_withheld_for_defects", "amount_disputed"]},
            {"id": "q3_termination", "title_de": "Prüffrage 3 – Kündigung",
             "fact_ids": ["receipt_date", "pickup_notice_date", "delivery_method", "termination_before_deadline_end", "official_form_used",
                          "family_home_with_spouse", "spouse_still_lives_there", "separate_delivery_to_spouse", "co_tenants_exist",
                          "co_tenants_all_notified", "termination_date", "days_between_deadline_and_termination",
                          "special_circumstances", "payment_agreement_present"]},
            {"id": "situation", "title_de": "Lage danach und Vorprüfung",
             "fact_ids": ["challenge_filed", "eviction_or_court_proceeding", "landlord_self_help", "housing_solution_available",
                          "children_in_household", "tenant_role", "object_type", "property_municipality", "property_in_canton_zh",
                          "vulnerability_present", "client_requests_expert", "consent_briefing"]},
        ],
        "review_points": [
            {"text_de": "Prüffrage 1: War die Mahnung gültig (Frist ≥ 30 Tage, Androhung, bestimmbarer Betrag, Zustellung)? Details in Issue 2.",
             "source_ids": ["CH_OR_257D_1", "BGER_4A_332_2025"]},
            {"text_de": "Prüffrage 2: Innert Frist vollständig bezahlt (Einzahlungsschein, Gutschrift, Dritte) oder verrechnet?",
             "source_ids": ["BGE_124_III_145", "BGE_119_II_232", "BGER_4A_68_2014"]},
            {"text_de": "Prüffrage 3: Formgültigkeit der Kündigung (Formular, Familienwohnung, Mitmieter), Zeitpunkt zur Zahlungsfrist, Termin, Treu und Glauben.",
             "source_ids": ["CH_OR_266L", "CH_OR_266N", "CH_OR_266O", "BGER_4A_585_2010", "BGE_140_III_591"]},
            {"text_de": "Anfechtung bei der Schlichtungsbehörde innert 30 Tagen ab Empfang (absolute Empfangstheorie); der Entscheid über die Anfechtung liegt immer bei der Rechtsperson.",
             "source_ids": ["CH_OR_273_1", "BGE_143_III_15"]},
            {"text_de": "Ausweisung im Verfahren für klare Fälle möglich; Anfechtung schützt nicht sicher.",
             "source_ids": ["BGE_141_III_262", "CH_ZPO_257"]},
        ],
        "documents_to_request": [
            "Mahnung und Kündigungsformular (alle Seiten, beide Ehegatten)",
            "Umschläge bzw. Abholungseinladungen oder Sendungsverfolgung",
            "Zahlungsbelege mit Datum (Auftrag und Gutschrift)",
            "Korrespondenz mit der Vermieterschaft", "Mietvertrag",
        ],
        "authority_ids": ["SCHLICHTUNGSBEHOERDE_MIETE_ZH", "MIETERVERBAND_ZH", "RECHTSAUSKUNFT_BEZIRKSGERICHT_ZUERICH",
                          "SOZIALDIENST_WOHNGEMEINDE", "SCHULDENBERATUNG_ZH"],
    },
}

_BASE = {
    "tenant_role": "hauptmieterin", "object_type": "wohnung", "property_municipality": "Zürich", "property_in_canton_zh": True,
    "co_tenants_exist": False, "delivery_method": "persoenlich", "receipt_date": "2026-11-01", "official_form_used": True,
    "family_home_with_spouse": False, "eviction_or_court_proceeding": False, "warning_written": True, "warning_threat_present": True,
    "warning_amount_clear": True, "warning_deadline_days": 30, "warning_delivery_method": "persoenlich",
    "warning_receipt_date": "2026-09-01", "paid_in_time": "nicht_bezahlt", "setoff_or_deposit_done": False,
    "third_party_payment": False, "termination_before_deadline_end": False, "challenge_filed": False,
    "housing_solution_available": True, "rent_payer": "klientin", "rent_withheld_for_defects": False,
}


def _f(**kw):
    d = dict(_BASE)
    d.update(kw)
    return d


SPEC["scenarios"] = [
    scenario("SC_PD_01_GRUNDREGEL", "Jede Zahlungsverzugskündigung: sofort, Recht + Soziales", "ESCALATE", issues=[ID],
             facts=_f(), urgency="HIGH", rules=["PD_GRUNDREGEL"], reasons=["PAYMENT_DEFAULT_TERMINATION_IMMEDIATE"]),
    scenario("SC_PD_02_FEHLENDES_FAKTUM", "Zwingendes Faktum fehlt: Grundregel eskaliert trotzdem", "ESCALATE", issues=[ID],
             facts={k: v for k, v in _f().items() if k != "paid_in_time"}, urgency="HIGH", rules=["PD_GRUNDREGEL"],
             missing=["paid_in_time"]),
    scenario("SC_PD_03_EMPFANG_UNBEKANNT", "Empfangsdatum der Kündigung unbekannt", "ESCALATE", issues=[ID],
             facts={k: v for k, v in _f().items() if k != "receipt_date"}, unknown=["receipt_date"], urgency="HIGH",
             rules=["PD_EMPFANG_UNBEKANNT_ODER_GE20"]),
    scenario("SC_PD_04_GE_20_TAGE", "21 Tage seit Empfang", "ESCALATE", issues=[ID], facts=_f(receipt_date="2026-10-17"),
             urgency="HIGH", rules=["PD_EMPFANG_UNBEKANNT_ODER_GE20"], today="2026-11-07"),
    scenario("SC_PD_05_UNTER_20_TAGE", "5 Tage seit Empfang: Schwelle nicht erreicht", "ESCALATE", issues=[ID],
             facts=_f(receipt_date="2026-11-02"), urgency="HIGH", not_rules=["PD_EMPFANG_UNBEKANNT_ODER_GE20"], today="2026-11-07"),
    scenario("SC_PD_06_MAHNUNG_FEHLT", "Keine Mahnung", "ESCALATE", issues=[ID], facts=_f(warning_written=False),
             urgency="HIGH", rules=["PD_PRUEFFRAGE1_MAHNUNG"]),
    scenario("SC_PD_07_RECHTZEITIG_BEZAHLT", "Angabe: innert Frist bezahlt", "ESCALATE", issues=[ID],
             facts=_f(paid_in_time="vollstaendig_rechtzeitig"), urgency="HIGH", rules=["PD_PRUEFFRAGE2_ZAHLUNG"]),
    scenario("SC_PD_08_VOR_FRIST", "Kündigung vor Fristablauf", "ESCALATE", issues=[ID],
             facts=_f(termination_before_deadline_end=True), urgency="HIGH", rules=["PD_PRUEFFRAGE3_FORM"]),
    scenario("SC_PD_09_KEIN_FORMULAR", "Kein amtliches Formular", "ESCALATE", issues=[ID], facts=_f(official_form_used=False),
             urgency="HIGH", rules=["PD_PRUEFFRAGE3_FORM"]),
    scenario("SC_PD_10_GERICHT", "Gesuch ans Gericht -> Issue 6", "ESCALATE", issues=[ID], facts=_f(eviction_or_court_proceeding=True),
             urgency="HIGH", rules=["PD_GERICHT"], routes=["CH_TENANCY_EVICTION"]),
    scenario("SC_PD_11_SELBSTHILFE", "Vermieter wechselt das Schloss", "ESCALATE", issues=[ID], facts=_f(landlord_self_help=True),
             urgency="HIGH", rules=["PD_SELBSTHILFE"]),
    scenario("SC_PD_12_SOZIALDIENST_ZAHLT", "Sozialdienst zahlt direkt", "ESCALATE", issues=[ID], facts=_f(rent_payer="sozialdienst"),
             urgency="HIGH", rules=["PD_SOZIALDIENST_ZAHLT"]),
    scenario("SC_PD_13_KEINE_ANSCHLUSSLOESUNG", "Keine Anschlusslösung, Kinder", "ESCALATE", issues=[ID],
             facts=_f(housing_solution_available=False, children_in_household=True), urgency="HIGH", rules=["PD_KEINE_ANSCHLUSSLOESUNG"]),
    scenario("SC_PD_14_WARTEZEIT", "Kündigung 20 Tage nach Fristablauf: Prüfhinweis (Verzicht?)", "ESCALATE", issues=[ID],
             facts=_f(days_between_deadline_and_termination=20), urgency="HIGH"),
    scenario("SC_PD_15_UNTERMIETE", "Untermiete: ausserhalb des Moduls", "ESCALATE", issues=[ID], facts=_f(tenant_role="untermieterin"),
             urgency="HIGH", rules=["PD_OUT_OF_SCOPE_ROLE"]),
]
