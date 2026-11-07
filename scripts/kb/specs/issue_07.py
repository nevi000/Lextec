"""Issue 7 - Mietzinserhöhung und einseitige Vertragsänderung (Art. 269 ff. OR, VMWG). Quelle: issue_07.docx.

Das System erkennt Formfehler-Hinweise und die Frist, sichert Unterlagen und eskaliert. Es beurteilt NIE die Missbräuchlichkeit,
rechnet nicht mit Referenzzinssatz/Teuerung und nennt keinen Referenzzinssatz-Wert. Die Formular-Vorprüfung ist nur ein Hinweis.
"""

from common_facts import common
from issue_05 import facts as F5
from kb_common import ALWAYS, D, F, all_, any_, eq, esc_rule, fact, gt, inn, legal, ne, scenario, shared_facts, unk

ID = "CH_TENANCY_RENT_INCREASE"
BOTH = ["tenancy_law_counsel", "social_counselling"]
LEGAL = ["tenancy_law_counsel"]


def _pick(src, *ids):
    by = {f["id"]: f for f in src}
    return [dict(by[i]) for i in ids]


FORM_CHECKS = [
    "form_old_new_rent_stated", "form_effective_date_stated", "form_reason_present", "form_cover_letter_reference",
    "form_appeal_notice_present", "form_page3_present", "form_signed",
]

facts = (
    shared_facts(
        ["tenant_role", "object_type", "property_municipality", "client_residence_municipality", "property_in_canton_zh", "contract_term_type", "contract_termination_dates",
         "vulnerability_present", "client_requests_expert", "consent_briefing"]
    )
    + _pick(F5, "housing_arrangement")
    + common("social_assistance_received")
    + [
        fact("increase_letter_available", "Schreiben vollständig hochgeladen", "Liegt das Schreiben der Vermieterschaft vollständig vor (alle Seiten, Umschlag)?",
             "Grundlage für alles Weitere; Formular, Begründung und Daten liest die Sozialarbeiterin daraus ab.", group="letter", req=True, prio="high",
             esc=True, src=["CH_OR_269D_1"]),
        fact("increase_delivery_method", "Zustellart des Schreibens", "Wie wurde das Schreiben zugestellt: eingeschrieben, normale Post, persönlich oder per E-Mail?",
             "Beginn der 30-Tage-Frist (Art. 270b OR; relative Empfangstheorie, BGE 137 III 208 E. 3.1.3); nicht abgeholtes Einschreiben: spätestens 7. Tag der Abholfrist.",
             type="enum", group="letter",
             enum={"persoenlich": "Persönlich übergeben", "eingeschrieben": "Eingeschrieben (Post)", "normale_post": "Normale Post", "email": "E-Mail"},
             req=True, prio="high", esc=True, src=["CH_OR_270B", "BGE_137_III_208"]),
        fact("increase_pickup_notice_date", "Abholungseinladung (Erhöhung)", "Falls nicht abgeholt: Wann lag die Abholungseinladung im Briefkasten?",
             "Konservative Schwelle: der früheste bekannte Empfangshinweis zählt für die interne Dringlichkeit.", type="date", group="letter",
             req_if=eq(F("increase_delivery_method"), "eingeschrieben"), deps=["increase_delivery_method"], esc=True, prio="medium",
             src=["CH_OR_270B"]),
        fact("increase_receipt_date", "Empfang des Schreibens", "An welchem Datum wurde das Schreiben empfangen oder auf der Post abgeholt?",
             "Beginn der 30-Tage-Frist (Art. 270b OR; relative Empfangstheorie BGE 137 III 208). Das System nennt kein Fristende.",
             type="date", group="letter", req=True, prio="high", esc=True, src=["CH_OR_270B", "BGE_137_III_208"]),
        fact("form_official_used", "Amtliches Formular", "Ist das Schreiben das amtliche Formular «Mitteilung von Mietzinserhöhungen und einseitigen Vertragsänderungen (Art. 269d OR)» (Zürich, drei Seiten) und nicht bloss ein Brief oder eine E-Mail?",
             "Mögliche Nichtigkeit (Art. 269d Abs. 2 lit. a OR; BGE 121 III 214). Nur ein Hinweis: die Rechtsperson beurteilt.", group="form", req=True,
             prio="high", esc=True, src=["CH_OR_269D_2", "BGE_121_III_214"]),
        fact("form_old_new_rent_stated", "Formular nennt bisherigen und neuen Mietzins", "Nennt das Formular den bisherigen und den neuen Mietzins?",
             "Pflichtangabe Art. 19 Abs. 1 lit. a VMWG (Hinweis, von der Sozialarbeiterin am Original bestätigt).", group="form", prio="medium",
             src=["CH_VMWG_19_1_A"]),
        fact("form_effective_date_stated", "Formular nennt den Zeitpunkt", "Nennt das Formular den Zeitpunkt, ab dem die Erhöhung gelten soll?",
             "Pflichtangabe Art. 19 VMWG (Hinweis).", group="form", prio="medium", src=["CH_VMWG_19_1_A"]),
        fact("form_reason_present", "Begründung enthalten", "Steht eine Begründung im Formular (z. B. Referenzzinssatz, Teuerung, Kostensteigerung, Renovation, ortsübliche Miete)?",
             "Nichtigkeit bei fehlender Begründung (Art. 269d Abs. 2 lit. b OR; BGE 142 III 375, BGE 137 III 362). Das System bewertet die Begründung nicht.",
             group="form", req=True, prio="high", esc=True, src=["CH_OR_269D_2", "BGE_142_III_375", "BGE_137_III_362"]),
        fact("form_cover_letter_reference", "Begleitschreiben ausdrücklich verwiesen", "Ist ein Begleitschreiben dabei, und verweist das Formular ausdrücklich darauf?",
             "Begründung im Begleitschreiben nur mit ausdrücklichem Verweis (Art. 19 Abs. 1bis VMWG).", group="form", prio="medium", src=["CH_VMWG_19_1BIS"]),
        fact("form_appeal_notice_present", "Anfechtungshinweis (Rechtsmittelbelehrung)", "Enthält das Formular den Hinweis auf die Anfechtung (Rechtsmittelbelehrung)?",
             "Pflichtangabe nach Art. 19 VMWG (Hinweis).", group="form", prio="medium", src=["CH_VMWG_19_1_A"]),
        fact("form_page3_present", "Seite 3 des Formulars vorhanden", "Ist Seite 3 (OR-Auszug/Anfechtungshinweise) vorhanden?",
             "Vollständigkeit des Formulars (Hinweis).", group="form", prio="low", src=["CH_VMWG_19_1_A"]),
        fact("form_signed", "Unterschrift der Vermieterschaft", "Ist das Formular unterschrieben (auch gedruckte/Faksimile-Unterschrift)?",
             "Seit 1.10.2025 genügt eine auf mechanischem Weg nachgebildete Unterschrift (Art. 269d Abs. 4 OR); eine gedruckte Unterschrift ist KEIN Formfehler.",
             group="form", prio="medium", src=["CH_OR_269D_4"]),
        fact("termination_threat_in_letter", "Kündigungsandrohung im Schreiben", "Droht das Schreiben mit Kündigung (z. B. «bei Nichtakzeptanz wird gekündigt»)?",
             "Nichtigkeit (Art. 269d Abs. 2 lit. c OR).", group="form", req=True, prio="high", esc=True, src=["CH_OR_269D_2"]),
        fact("letter_contains_termination", "Schreiben enthält zugleich eine Kündigung", "Enthält das Schreiben zugleich eine Kündigung?",
             "Andere Fristen: Wechsel zu Issue 1.", group="form", prio="high", esc=True, src=["CH_OR_269D_2", "CH_OR_271A_1_B_D_E"]),
        fact("change_type", "Art der Änderung", "Mietzinserhöhung, neue Nebenkosten oder weniger Leistungen (z. B. Waschküche, Parkplatz)?",
             "Gleich behandeln wie eine Mietzinserhöhung (Art. 269d Abs. 3, 270b Abs. 2 OR).", type="enum", group="content",
             enum={"mietzinserhoehung": "Mietzinserhöhung", "neue_nebenkosten": "Neue Nebenkosten", "leistungsabbau": "Weniger Leistungen",
                   "andere": "Andere einseitige Änderung"},
             req=True, prio="high", src=["CH_OR_269D_3", "CH_OR_270B"]),
        fact("old_rent_chf", "Bisheriger Mietzins (CHF)", "Wie hoch ist die bisherige Miete?", "Grundlage der Prüfung durch die Rechtsperson (keine Berechnung durch das System).",
             type="integer", group="content", req=True, prio="medium", src=["CH_VMWG_19_1_A"]),
        fact("new_rent_chf", "Neuer Mietzins (CHF)", "Wie hoch ist die neue Miete laut Schreiben?", "Grundlage der Prüfung durch die Rechtsperson.",
             type="integer", group="content", req=True, prio="medium", src=["CH_VMWG_19_1_A"]),
        fact("effective_date_in_letter", "Datum laut Schreiben", "Ab welchem Datum soll die Änderung gelten?", "Fristprüfung durch die Rechtsperson (Art. 269d Abs. 1 OR); das System nennt kein Datum, ab dem die Erhöhung gilt.",
             type="date", group="content", req=True, prio="medium", src=["CH_OR_269D_1"]),
        fact("rent_model", "Index- oder Staffelmiete", "Ist eine Index- oder Staffelmiete vereinbart?", "Art. 269b, 269c, 270c, 270d OR: Staffelerhöhungen nicht anfechtbar.",
             type="enum", group="content",
             enum={"keine": "Weder Index- noch Staffelmiete", "indexmiete": "Indexmiete", "staffelmiete": "Staffelmiete"},
             req=True, prio="high", esc=True, src=["CH_OR_269B_269C", "CH_OR_270C_270D"]),
        fact("luxury_or_large_house", "Luxuswohnung oder Einfamilienhaus ab 6 Zimmern", "Handelt es sich um eine Luxuswohnung oder ein Einfamilienhaus mit sechs oder mehr Wohnräumen?",
             "Missbrauchsschutz gilt dafür nicht (Art. 253b Abs. 2 OR).", group="content", req=True, prio="medium", esc=True, src=["CH_OR_253B_2_3"]),
        fact("increase_already_paying", "Zahlt schon den neuen Betrag", "Zahlt die Klientin schon den neuen Betrag?",
             "Rückforderung bei Nichtigkeit; kein Verzicht ohne Rechtsprüfung.", group="history", req=True, prio="medium", src=["CH_OR_269D_2"]),
        fact("increase_already_reacted", "Bereits zugestimmt, unterschrieben, angefochten oder gekündigt",
             "Hat die Klientin schon zugestimmt, unterschrieben, angefochten oder gekündigt?", "G9 Unterschrift; laufendes Verfahren.", group="history",
             req=True, prio="high", esc=True, src=["CH_OR_270B"]),
        fact("asked_to_sign", "Klientin soll etwas unterschreiben", "Soll die Klientin etwas unterschreiben (Zustimmung, neuer Vertrag)?",
             "Global G9: nicht unterschreiben, bevor die Rechtsperson geprüft hat.", group="history", prio="high", esc=True, src=["PRODUKTREGEL"]),
        fact("last_rent_adjustment", "Letzte Anpassung", "Wann wurde die Miete zuletzt angepasst, und gab es damals einen Vorbehalt?", "Relative Methode (Rechtsperson).",
             type="string", group="history", prio="low", src=["CH_OR_269A"]),
        fact("renovation_before", "Renovationsarbeiten vorher", "Gab es vorher Renovationsarbeiten?", "Mehrleistung (Art. 269a lit. b OR); Bezug Issue 5 während der Bauarbeiten.",
             group="history", prio="low", src=["CH_OR_269A", "CH_VMWG_14_1"]),
        fact("wants_to_terminate_instead", "Klientin will lieber kündigen", "Möchte die Klientin lieber kündigen als anfechten?",
             "Die Bedenkfrist von zehn Tagen bezweckt genau diese Wahl; Wohnungsverlust abwägen.", group="history", prio="medium", esc=True, src=["CH_OR_269D_1"]),
        fact("rent_affordable", "Neue Miete finanzierbar", "Kann die Klientin die neue Miete bezahlen?",
             "Route SOZIAL; Daten über Sozialhilfe sind besonders schützenswert (Art. 5 lit. c Ziff. 6 DSG).", group="social", req=True, prio="high",
             esc=True, src=["CH_DSG_6_7"]),
    ]
)

DERIVED = [
    {"id": "days_since_increase_receipt", "kind": "days_since_earliest", "facts": ["increase_pickup_notice_date", "increase_receipt_date"],
     "description": "Tage seit dem frühesten bekannten Empfangshinweis der Mitteilung (INTERNE Schwelle, kein Fristende)."},
]

form_defect = any_(
    eq(F("form_official_used"), False), eq(F("form_reason_present"), False),
    *[eq(F(x), False) for x in ("form_old_new_rent_stated", "form_effective_date_stated", "form_appeal_notice_present", "form_page3_present")],
)

escalation = [
    esc_rule("RI_OUT_OF_SCOPE", "Untermiete/Geschäftsraum/Notunterkunft: ausserhalb des Moduls.",
             any_(inn(F("tenant_role"), ["untermieterin", "andere"]), inn(F("object_type"), ["notwohnung_heim", "ferienwohnung_bis_3_monate", "andere"])),
             "MEDIUM", "OUT_OF_SCOPE_OBJECT",
             "Das Mietverhältnis fällt nicht unter die gewöhnliche Wohnraummiete dieses Moduls (z. B. Untermiete, Geschäftsraum, Notunterkunft). Es werden keine Standardaussagen gemacht. Eine unabhängige Rechtsperson muss prüfen.",
             ["lawyer_general"], suppress=True),
    esc_rule("RI_FRIST_20_ODER_UNBEKANNT", "PRODUKTSCHWELLE (Teamentscheid 7.11.2026): 20+ Tage seit Empfang oder Empfang unbekannt.",
             any_(unk(F("increase_receipt_date")), unk(F("increase_delivery_method")), unk(F("increase_pickup_notice_date")),
                  gt(D("days_since_increase_receipt"), 19)),
             "HIGH", "INCREASE_30_DAY_DEADLINE_TIGHT",
             "Der Empfang der Mitteilung ist unbekannt oder liegt 20 oder mehr Tage zurück. Die Anfechtungsfrist von 30 Tagen (Art. 270b OR) ist knapp oder unbestimmbar (Produktschwelle, kein Fristende). Rechtsperson sofort.",
             LEGAL),
    esc_rule("RI_KEIN_FORMULAR", "Kein amtliches Formular oder keine Begründung: mögliche Nichtigkeit (Hinweis).",
             any_(eq(F("form_official_used"), False), eq(F("form_reason_present"), False)), "MEDIUM", "INCREASE_POSSIBLY_VOID_FORM",
             "Es fehlt laut Angabe das amtliche Formular oder die Begründung. Das kann zur Nichtigkeit führen; das ist nur ein Hinweis, die Rechtsperson beurteilt (bald). Trotzdem vorsorglich die Frist wahren.",
             LEGAL),
    esc_rule("RI_KUENDIGUNGSDROHUNG", "Kündigungsandrohung im Schreiben: mögliche Nichtigkeit.", eq(F("termination_threat_in_letter"), True), "HIGH",
             "INCREASE_WITH_TERMINATION_THREAT",
             "Das Schreiben droht mit Kündigung. Das kann zur Nichtigkeit führen; die Rechtsperson prüft sofort. Prüfen, ob zugleich eine Kündigung vorliegt.",
             LEGAL),
    esc_rule("RI_KUENDIGUNG_IM_SCHREIBEN", "Schreiben enthält zugleich eine Kündigung -> Issue 1.", eq(F("letter_contains_termination"), True), "HIGH",
             "INCREASE_LETTER_CONTAINS_TERMINATION",
             "Das Schreiben enthält zugleich eine Kündigung. Dafür gelten andere Fristen (Issue 1); sofortige juristische Prüfung.",
             LEGAL, route="CH_TENANCY_TERMINATION"),
    esc_rule("RI_PRUEFUNG_GRUNDREGEL", "Formgültige Erhöhung (nicht Staffelmiete): Missbräuchlichkeit nur durch eine Fachperson.",
             ne(F("rent_model"), "staffelmiete"), "MEDIUM", "INCREASE_LEGAL_REVIEW_STANDARD",
             "Ob eine Mietzinserhöhung missbräuchlich ist, beurteilt nur eine Fachperson; das System rechnet nicht mit Referenzzinssatz oder Teuerung. Rechtsperson bald, Unterlagen sichern.",
             LEGAL),
    esc_rule("RI_SUBVENTIONIERT_GENOSSENSCHAFT", "Subventionierte Wohnung oder Genossenschaft.",
             inn(F("housing_arrangement"), ["subventioniert", "genossenschaft", "gemeindewohnung", "zugewiesene_unterkunft"]), "MEDIUM",
             "INCREASE_SUBSIDISED_OR_COOPERATIVE",
             "Bei subventionierten Wohnungen mit kontrolliertem Mietzins, Genossenschaften oder Gemeindewohnungen können besondere Regeln gelten (Art. 253b Abs. 3 OR, Statuten). Zuständige Stelle klären; Rechtsperson bald.",
             LEGAL),
    esc_rule("RI_LUXUS", "Luxuswohnung/grosses Einfamilienhaus: Missbrauchsschutz gilt nicht.", eq(F("luxury_or_large_house"), True), "MEDIUM",
             "INCREASE_LUXURY_EXCLUSION", "Bei Luxuswohnungen und Einfamilienhäusern ab sechs Wohnräumen gilt der Missbrauchsschutz nicht (Art. 253b Abs. 2 OR). Rechtsperson bald.", LEGAL),
    esc_rule("RI_UNTERSCHRIFT", "Klientin soll unterschreiben oder hat zugestimmt (G9).",
             any_(eq(F("asked_to_sign"), True), eq(F("increase_already_reacted"), True)), "HIGH", "INCREASE_SIGNATURE_OR_CONSENT",
             "Die Klientin soll etwas unterschreiben oder hat schon zugestimmt. Das kann die Anfechtung ausschliessen: nicht unterschreiben, bevor die Rechtsperson geprüft hat. Rechtsperson sofort.",
             LEGAL),
    esc_rule("RI_NICHT_FINANZIERBAR", "Erhöhung nicht finanzierbar oder über der Mietzinslimite der Sozialhilfe: SOZIAL (+ RECHT).",
             eq(F("rent_affordable"), False), "MEDIUM", "INCREASE_NOT_AFFORDABLE",
             "Die erhöhte Miete ist nicht finanzierbar oder liegt über der Mietzinslimite. Die Sozialarbeiterin klärt Finanzierung bzw. Mietzinslimite, um Wohnungsverlust zu vermeiden; Rechtsperson parallel (bald).",
             ["social_counselling", "tenancy_law_counsel"]),
    esc_rule("RI_BEFRISTET", "Befristeter Vertrag ohne Index-/Staffelklausel: Erhöhung grundsätzlich ausgeschlossen.",
             all_(eq(F("contract_term_type"), "befristet"), eq(F("rent_model"), "keine")), "MEDIUM", "INCREASE_FIXED_TERM_CONTRACT",
             "Bei einem echt befristeten Vertrag ohne Index- oder Staffelklausel ist eine Erhöhung grundsätzlich ausgeschlossen. Die Rechtsperson prüft (bald).", LEGAL),
    esc_rule("RI_WILL_KUENDIGEN", "Klientin will lieber kündigen statt anfechten.", eq(F("wants_to_terminate_instead"), True), "MEDIUM",
             "INCREASE_TENANT_WANTS_TO_TERMINATE",
             "Die Klientin möchte lieber kündigen. Der Wohnungsverlust ist abzuwägen; Rechtsperson und Sozialarbeiterin besprechen das (bald).", BOTH),
    esc_rule("RI_VULNERABILITY", "Besondere Belastungssituation: ausserhalb des Moduls.", eq(F("vulnerability_present"), True), "MEDIUM",
             "OUTSIDE_MODULE_VULNERABILITY",
             "Es liegt eine besondere Belastungssituation vor. Das liegt ausserhalb dieses Moduls und gehört in menschliche Hände.", BOTH),
    esc_rule("RI_EXPERT_REQUESTED", "Fachperson ausdrücklich gewünscht.", eq(F("client_requests_expert"), True), "LOW", "EXPERT_REQUESTED",
             "Es wurde ausdrücklich eine Fachperson gewünscht. Dieser Wunsch wird immer respektiert.", LEGAL),
]

legal_rules = [
    legal("RI_HINT_FORM", "Formular und Begründung.", ALWAYS, "HINT_FORM_AND_REASON",
          "Eine Mietzinserhöhung muss auf einem amtlichen Formular mitgeteilt und begründet werden. Ob das hier erfüllt ist, prüft eine Fachperson.",
          ["CH_OR_269D_1", "CH_OR_269D_2"]),
    legal("RI_HINT_ANFECHTUNG", "Anfechtung 30 Tage.", ALWAYS, "HINT_CONTEST_30_DAYS",
          "Wer eine Erhöhung für missbräuchlich hält, kann sie innert 30 Tagen nach Empfang bei der Schlichtungsbehörde anfechten. Wird die Frist verpasst, gilt die Erhöhung.",
          ["CH_OR_270B", "BGE_131_III_566"]),
    legal("RI_HINT_ALTER_MIETZINS", "Während der Anfechtung gilt der bisherige Mietzins.", ALWAYS, "HINT_OLD_RENT_DURING_CONTEST",
          "Während der Anfechtung muss nur die bisherige Miete bezahlt werden. Es lohnt sich aber, die Differenz zur Seite zu legen, falls die Erhöhung bestätigt wird.",
          ["CH_OR_270E", "LEHRBUCH_MIETE_31"]),
    legal("RI_HINT_KOSTENLOS", "Schlichtungsverfahren kostenlos.", ALWAYS, "HINT_NO_COURT_COSTS",
          "Das Verfahren vor der Schlichtungsbehörde kostet keine Gerichtskosten.", ["CH_ZPO_113_2_C"]),
    legal("RI_HINT_KUENDIGUNG_NACH_ANFECHTUNG", "Kündigung wegen Anfechtung ist anfechtbar.", ALWAYS, "HINT_TERMINATION_AFTER_CONTEST",
          "Eine Kündigung, die erfolgt, weil jemand eine Erhöhung anficht, kann ihrerseits angefochten werden.", ["CH_OR_271A_1_B_D_E"]),
    legal("RI_HINT_NEBENKOSTEN", "Neue Nebenkosten und Leistungsabbau.", inn(F("change_type"), ["neue_nebenkosten", "leistungsabbau", "andere"]),
          "HINT_OTHER_CHANGES_LIKE_INCREASE", "Dasselbe gilt für neue Nebenkosten oder wenn Leistungen gestrichen werden.",
          ["CH_OR_269D_3", "CH_OR_270B"]),
    legal("RI_HINT_ZAHLEN_VERLANGEN", "Zahlen offenlegen lassen, Frist läuft weiter.", ALWAYS, "HINT_REQUEST_FIGURES_DEADLINE_RUNS",
          "Bei Erhöhungen wegen Kostensteigerungen oder Renovationen kann man verlangen, dass die Vermieterschaft die Zahlen offenlegt. Die 30-Tage-Frist läuft dabei aber weiter.",
          ["CH_VMWG_20_1"]),
    legal("RI_HINT_BERATUNG", "Schlichtungsbehörde berät auch ohne Verfahren.", ALWAYS, "HINT_CONCILIATION_ADVICE",
          "Die Schlichtungsbehörde berät auch ohne Verfahren und hilft einzuschätzen, ob eine Erhöhung missbräuchlich ist.", ["CH_VMWG_21_2"]),
    legal("RI_REVIEW_FORMHINWEIS", "Formular-Vorprüfung: nur ein Hinweis.", form_defect, "REVIEW_FORM_PRECHECK",
          "Formular-Vorprüfung (nur ein Hinweis, keine rechtliche Bewertung): Mindestens eine Pflichtangabe des Formulars scheint zu fehlen. Die Sozialarbeiterin bestätigt am Original; ob die Erhöhung nichtig ist, beurteilt die Rechtsperson.",
          ["CH_VMWG_19_1_A", "CH_OR_269D_2"], kind="REVIEW_POINT"),
    legal("RI_REVIEW_FAKSIMILE", "Gedruckte Unterschrift ist zulässig.", eq(F("form_signed"), True), "REVIEW_PRINTED_SIGNATURE_VALID",
          "Prüfhinweis: Seit 1.10.2025 genügt eine auf mechanischem Weg nachgebildete (gedruckte) Unterschrift; ein Fehlen der Originalunterschrift ist kein Formfehler.",
          ["CH_OR_269D_4"], kind="REVIEW_POINT"),
    legal("RI_REVIEW_STAFFEL", "Staffelmiete: Erhöhungen nicht anfechtbar.", eq(F("rent_model"), "staffelmiete"), "REVIEW_GRADUATED_RENT",
          "Prüfhinweis: Bei einer Staffelmiete sind die vereinbarten Erhöhungen nicht anfechtbar; für die Mitteilung genügt die Schriftform.",
          ["CH_OR_270C_270D", "CH_OR_269D_4"], kind="REVIEW_POINT"),
    legal("RI_REVIEW_INDEX", "Indexmiete: nur Einwand zur Indexänderung.", eq(F("rent_model"), "indexmiete"), "REVIEW_INDEXED_RENT",
          "Prüfhinweis: Bei einer Indexmiete ist nur der Einwand möglich, die Indexänderung rechtfertige die Erhöhung nicht.",
          ["CH_OR_270C_270D"], kind="REVIEW_POINT"),
    legal("RI_REVIEW_KURZFRISTIG", "Zu kurzfristig: Wirkung erst auf den nächsten Termin.", ALWAYS, "REVIEW_SHORT_NOTICE_NEXT_TERM",
          "Prüfhinweis: Wird eine Erhöhung zu kurzfristig mitgeteilt, ist sie nicht ungültig, sondern wirkt erst auf den nächstfolgenden Termin. Das System nennt kein Datum.",
          ["CH_OR_269D_1", "BGE_131_III_566"], kind="REVIEW_POINT"),
    legal("RI_REVIEW_BEGRUENDUNG_BEGLEITSCHREIBEN", "Begründung nur im Begleitschreiben.", eq(F("form_cover_letter_reference"), False),
          "REVIEW_REASON_IN_COVER_LETTER", "Prüfhinweis: Eine Begründung nur im Begleitschreiben ist nur zulässig, wenn das Formular ausdrücklich darauf verweist (Art. 19 Abs. 1bis VMWG).",
          ["CH_VMWG_19_1BIS", "BGE_137_III_362"], kind="REVIEW_POINT"),
    legal("RI_REVIEW_FRIST_VERPASST", "Frist verpasst: Erhöhung wirksam, Formnichtigkeit bleibt prüfbar.", gt(D("days_since_increase_receipt"), 29),
          "REVIEW_DEADLINE_MISSED", "Prüfhinweis: Nach Ablauf von 30 Tagen wird die Erhöhung wirksam, auch wenn sie missbräuchlich wäre; Formnichtigkeit kann aber weiterhin geltend gemacht werden. Herabsetzungsbegehren für die Zukunft prüfen.",
          ["CH_OR_270B", "BGE_131_III_566", "BGE_124_III_67", "CH_OR_270A"], kind="REVIEW_POINT"),
    legal("RI_REVIEW_ORTSUEBLICH", "Kein Referenzzinssatz-Wert im System.", ALWAYS, "REVIEW_NO_REFERENCE_RATE_VALUE",
          "Prüfhinweis: Das System nennt keinen aktuellen Referenzzinssatz und rechnet nicht mit Teuerung oder Kosten. Den aktuellen Satz veröffentlicht das Bundesamt für Wohnungswesen (BWO).",
          ["CH_VMWG_12A"], kind="REVIEW_POINT"),
]

SPEC = {
    "id": ID,
    "issue": "rent_increase",
    "dossier": "issue_07.docx",
    "title_de": "Mietzinserhöhung und einseitige Vertragsänderung (Issue 7)",
    "description": "Mietzinserhöhung und andere einseitige Vertragsänderungen während eines unbefristeten Mietverhältnisses (Art. 269 ff. OR, VMWG; Änderungen seit 1.10.2025). Das System erkennt Formfehler-Hinweise und die 30-Tage-Frist, beurteilt die Missbräuchlichkeit nie.",
    "provenance_de": "Law-Dossier Issue 7 vom 7.11.2026; Teamentscheide: Eskalation ab 20 Tagen oder bei unbekanntem Empfang, Formular-Vorprüfung nur als Hinweis.",
    "derived": DERIVED,
    "classification": {
        "description": "Passt bei Mietzinserhöhung, neuen Nebenkosten oder einseitigem Leistungsabbau (Waschküche, Parkplatz) durch die Vermieterschaft während eines laufenden Mietverhältnisses, auch wenn nur die Mitteilung / das Formular vorliegt. NICHT passend: Kündigung (Issue 1), Mängel (Issue 5).",
        "typical_situations": [
            "Der Vermieter hat die Miete erhöht.",
            "Meine Klientin hat eine Mietzinserhöhung erhalten.",
            "Die Verwaltung verlangt neu Nebenkosten für die Hauswartung.",
            "Mitteilung einer Mietzinsanpassung wegen Referenzzinssatz.",
        ],
        "related_issues": [],
    },
    "facts": facts,
    "escalation": escalation,
    "legal": legal_rules,
    "default_professionals": ["tenancy_law_counsel"],
    "briefing": {
        "intro_de": "Mietzinserhöhung / einseitige Vertragsänderung (Art. 269 ff. OR) – Kanton Zürich",
        "groups": [
            {"id": "letter", "title_de": "Schreiben, Empfang und Zustellart",
             "fact_ids": ["increase_letter_available", "increase_delivery_method", "increase_pickup_notice_date", "increase_receipt_date"]},
            {"id": "form", "title_de": "Formular-Vorprüfung (nur Hinweis, am Original bestätigt)",
             "fact_ids": ["form_official_used", "form_reason_present", "form_old_new_rent_stated", "form_effective_date_stated",
                          "form_cover_letter_reference", "form_appeal_notice_present", "form_page3_present", "form_signed",
                          "termination_threat_in_letter", "letter_contains_termination"]},
            {"id": "content", "title_de": "Inhalt: Art der Änderung, Beträge, Vertragsart, Wohnform",
             "fact_ids": ["change_type", "old_rent_chf", "new_rent_chf", "effective_date_in_letter", "contract_term_type", "contract_termination_dates",
                          "rent_model", "housing_arrangement", "luxury_or_large_house"]},
            {"id": "history", "title_de": "Bisherige Reaktion und Hintergründe",
             "fact_ids": ["increase_already_paying", "increase_already_reacted", "asked_to_sign", "last_rent_adjustment", "renovation_before",
                          "wants_to_terminate_instead"]},
            {"id": "social", "title_de": "Finanzierbarkeit (Sozialhilfe nur mit Einwilligung)",
             "fact_ids": ["rent_affordable", "social_assistance_received", "consent_briefing", "vulnerability_present", "client_requests_expert"]},
            {"id": "situation", "title_de": "Vorprüfung", "fact_ids": ["tenant_role", "object_type", "property_municipality", "property_in_canton_zh"]},
        ],
        "review_points": [
            {"text_de": "Fristbeginn: relative Empfangstheorie (tatsächlicher Empfang, spätestens 7. Tag der Abholfrist); 30 Tage Anfechtung.",
             "source_ids": ["CH_OR_270B", "BGE_137_III_208"]},
            {"text_de": "Form (Nichtigkeit): amtliches Formular, Begründung, keine Kündigungsandrohung; Begründung im Begleitschreiben nur mit ausdrücklichem Verweis.",
             "source_ids": ["CH_OR_269D_2", "CH_VMWG_19_1BIS", "BGE_142_III_375", "BGE_137_III_362"]},
            {"text_de": "Missbräuchlichkeit (Art. 269, 269a OR) beurteilt allein die Rechtsperson; das System rechnet nicht.",
             "source_ids": ["CH_OR_269", "CH_OR_269A"]},
            {"text_de": "Wohnform: subventioniert / Genossenschaft / Luxus; Vertragsart: befristet, Index, Staffel.",
             "source_ids": ["CH_OR_253B_2_3", "CH_OR_269B_269C", "CH_OR_270C_270D"]},
        ],
        "documents_to_request": [
            "Schreiben bzw. Formular der Vermieterschaft (alle Seiten, Umschlag)", "Begleitschreiben", "Mietvertrag (Kündigungsfrist und Termine)",
            "Letzte Mietzinsanpassung", "Nachweis der Zahlungen seit der Mitteilung",
        ],
        "authority_ids": ["SCHLICHTUNGSBEHOERDE_MIETE_ZH", "MIETERVERBAND_ZH", "RECHTSAUSKUNFT_SCHLICHTUNGSBEHOERDE_ZH", "MIETGERICHT_ZH",
                          "SOZIALDIENST_WOHNGEMEINDE", "BWO_REFERENZZINSSATZ", "KONTROLLBEHOERDE_SUBVENTIONIERT"],
    },
}

_BASE = {
    "tenant_role": "hauptmieterin", "object_type": "wohnung", "property_municipality": "Zürich", "property_in_canton_zh": True,
    "contract_term_type": "unbefristet", "housing_arrangement": "privat", "increase_letter_available": True, "increase_delivery_method": "persoenlich",
    "increase_receipt_date": "2026-11-02", "form_official_used": True, "form_reason_present": True, "termination_threat_in_letter": False,
    "change_type": "mietzinserhoehung", "old_rent_chf": 1500, "new_rent_chf": 1600, "effective_date_in_letter": "2027-04-01",
    "rent_model": "keine", "luxury_or_large_house": False, "increase_already_paying": False, "increase_already_reacted": False,
    "rent_affordable": True,
}


def _f(**kw):
    d = dict(_BASE)
    d.update(kw)
    return d


SPEC["scenarios"] = [
    scenario("SC_RI_T701", "T7-01 Formular mit Begründung, vor 5 Tagen erhalten: Recht bald", "ESCALATE", issues=[ID], facts=_f(), urgency="MEDIUM",
             rules=["RI_PRUEFUNG_GRUNDREGEL"], not_rules=["RI_FRIST_20_ODER_UNBEKANNT"], today="2026-11-07"),
    scenario("SC_RI_T702", "T7-02 wie T7-01, vor 25 Tagen erhalten: sofort", "ESCALATE", issues=[ID], facts=_f(increase_receipt_date="2026-10-13"),
             urgency="HIGH", rules=["RI_FRIST_20_ODER_UNBEKANNT"], today="2026-11-07"),
    scenario("SC_RI_T703", "T7-03 Erhöhung per E-Mail ohne Formular: mögliche Nichtigkeit (Hinweis), bald", "ESCALATE", issues=[ID],
             facts=_f(form_official_used=False, increase_delivery_method="email"), urgency="MEDIUM", rules=["RI_KEIN_FORMULAR"], today="2026-11-07"),
    scenario("SC_RI_T704", "T7-04 Formular mit Satz 'bei Nichtakzeptanz wird gekündigt': sofort", "ESCALATE", issues=[ID],
             facts=_f(termination_threat_in_letter=True), urgency="HIGH", rules=["RI_KUENDIGUNGSDROHUNG"], today="2026-11-07"),
    scenario("SC_RI_T705", "T7-05 Gedruckte Unterschrift: kein Formfehler", "ESCALATE", issues=[ID], facts=_f(form_signed=True),
             urgency="MEDIUM", not_rules=["RI_KEIN_FORMULAR"], today="2026-11-07"),
    scenario("SC_RI_T706", "T7-06 Staffelmiete laut Vertrag, formgerecht: KI_WEITER", "PROCEED", issues=[ID], facts=_f(rent_model="staffelmiete"),
             today="2026-11-07"),
    scenario("SC_RI_T707", "T7-07 Subventionierte städtische Wohnung: Recht bald", "ESCALATE", issues=[ID],
             facts=_f(housing_arrangement="subventioniert"), urgency="MEDIUM", rules=["RI_SUBVENTIONIERT_GENOSSENSCHAFT"], today="2026-11-07"),
    scenario("SC_RI_T708", "T7-08 Erhöhung CHF 200, Sozialhilfe, über Limite: SOZIAL + RECHT bald", "ESCALATE", issues=[ID],
             facts=_f(rent_affordable=False, new_rent_chf=1700), urgency="MEDIUM", rules=["RI_NICHT_FINANZIERBAR"], today="2026-11-07"),
    scenario("SC_RI_T709", "T7-09 Empfangsdatum unbekannt: sofort", "ESCALATE", issues=[ID],
             facts={k: v for k, v in _f().items() if k != "increase_receipt_date"}, unknown=["increase_receipt_date"], urgency="HIGH",
             rules=["RI_FRIST_20_ODER_UNBEKANNT"], today="2026-11-07"),
    scenario("SC_RI_T710", "T7-10 Neue Nebenkosten (Hauswartung): wie Erhöhung", "ESCALATE", issues=[ID],
             facts=_f(change_type="neue_nebenkosten"), urgency="MEDIUM", rules=["RI_PRUEFUNG_GRUNDREGEL"], today="2026-11-07"),
    scenario("SC_RI_11_KUENDIGUNG", "Schreiben enthält zugleich eine Kündigung -> Issue 1", "ESCALATE", issues=[ID],
             facts=_f(letter_contains_termination=True), urgency="HIGH", rules=["RI_KUENDIGUNG_IM_SCHREIBEN"], routes=["CH_TENANCY_TERMINATION"],
             today="2026-11-07"),
    scenario("SC_RI_12_UNTERSCHRIFT", "Klientin soll unterschreiben (G9)", "ESCALATE", issues=[ID], facts=_f(asked_to_sign=True), urgency="HIGH",
             rules=["RI_UNTERSCHRIFT"], today="2026-11-07"),
]
