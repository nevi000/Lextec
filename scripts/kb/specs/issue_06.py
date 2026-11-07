"""Issue 6 - Ausweisung und Räumung (Art. 257, 343 ZPO u. a.). Quelle: issue_06.docx.

Bewusste Ausnahme von G7 (Teamentscheid 7.11.2026): KEINE Rückfrage-Runden vor der Eskalation. Die Grundregel
EV_GRUNDREGEL eskaliert immer sofort; fehlende Angaben werden parallel erhoben. Fristen aus Gerichts-/Ammannamtsschreiben
werden nur wörtlich übergeben (deadline_quoted_text), NIE berechnet.
"""

from common_facts import common
from issue_02 import facts as F2
from issue_04 import facts as F4
from kb_common import ALWAYS, F, all_, any_, eq, esc_rule, fact, inn, legal, scenario, shared_facts, unk

ID = "CH_TENANCY_EVICTION"
BOTH = ["tenancy_law_counsel", "social_counselling"]
SOCIAL_FIRST = ["social_counselling", "tenancy_law_counsel"]
LEGAL = ["tenancy_law_counsel"]


def _pick(src, *ids):
    by = {f["id"]: f for f in src}
    return [dict(by[i]) for i in ids]


facts = (
    shared_facts(
        ["tenant_role", "object_type", "property_municipality", "client_residence_municipality", "property_in_canton_zh", "family_home_with_spouse",
         "spouse_still_lives_there", "separate_delivery_to_spouse", "vulnerability_present", "client_requests_expert",
         "consent_briefing"]
    )
    + common("challenge_filed", "housing_solution_available", "children_in_household", "landlord_self_help", "social_assistance_received")
    + _pick(F2, "third_party_payment", "payment_returned_by_landlord")
    + _pick(F4, "household_description")
    + [
        fact("eviction_stage", "Stadium des Verfahrens",
             "Was liegt derzeit vor?",
             "Bestimmt Frist und Dringlichkeit. Blockierend, aber die Eskalation wartet nicht auf die Antwort.", type="enum", group="stage",
             enum={"nur_kuendigung": "Nur Kündigung oder Drohung", "gesuch_oder_vorladung": "Gesuch oder Vorladung des Gerichts",
                   "gerichtsentscheid": "Entscheid des Gerichts", "ammannamt_raeumungstermin": "Schreiben des Gemeinde-/Stadtammannamts mit Räumungstermin",
                   "raeumung_heute_oder_schloss": "Räumung findet heute statt oder das Schloss wurde gewechselt"},
             req=True, prio="high", esc=True, src=["CH_ZPO_257", "CH_ZPO_343_1_D"],
             hint="Nur setzen, wenn das Stadium aus dem Text klar hervorgeht (Gericht, Ammannamt, Räumungstermin). Bei 'muss raus' ohne Dokument NICHT raten."),
        fact("eviction_document_available", "Schreiben hochgeladen", "Liegt das Schreiben vollständig vor (alle Seiten, mit Umschlag)?",
             "Frist, Gericht, Geschäftsnummer.", group="stage", req=True, prio="high", src=["PRODUKTREGEL"]),
        fact("court_reference", "Gericht und Geschäftsnummer", "Welches Gericht bzw. Amt und welche Geschäftsnummer steht im Schreiben?",
             "Gehört ins Briefing der Rechtsperson.", type="string", group="stage", prio="medium", src=["PRODUKTREGEL"]),
        fact("document_receipt_date", "Zustelldatum des Schreibens", "An welchem Datum wurde das Schreiben empfangen oder auf der Post abgeholt?",
             "Fristbeginn; die Rechtsperson rechnet, das System rechnet nicht.", type="date", group="stage", req=True, prio="high",
             esc=True, src=["CH_ZPO_239_2", "CH_ZPO_314_1"]),
        fact("deadline_quoted_text", "Frist im Schreiben (wörtlich)", "Welche Frist (Stellungnahme, Auszug, Räumungstermin) steht im Schreiben? Bitte wörtlich wiedergeben, oder «keine Frist» angeben.",
             "Wird wörtlich ans Briefing übergeben, nicht berechnet.", type="string", group="stage", req=True, prio="high", esc=True,
             src=["CH_ZPO_252_254"]),
        fact("eviction_termination_reason", "Grund der Kündigung", "Zahlungsverzug, ordentliche Kündigung, Vertragsende oder anderes?",
             "Vorfrage; bei Zahlungsverzug keine Erstreckung.", type="enum", group="history",
             enum={"zahlungsverzug": "Zahlungsverzug", "ordentlich": "Ordentliche Kündigung", "vertragsende": "Vertragsende (befristet)", "andere": "Anderes"},
             req=True, prio="high", esc=True, src=["CH_OR_257D_2", "CH_OR_272A_1_A"]),
        fact("arrears_paid_timing", "Rückstand bezahlt", "Wurde der Mietzinsrückstand bezahlt? Wenn ja: vor oder nach Ablauf der Zahlungsfrist?",
             "Nachzahlung nach Fristablauf heilt nicht (OG ZH LF260018 E. 4.2).", type="enum", group="history",
             enum={"nicht_bezahlt": "Nicht bezahlt", "vor_fristablauf": "Vollständig vor Fristablauf bezahlt", "nach_fristablauf": "Erst nach Fristablauf bezahlt"},
             req=True, prio="high", esc=True, src=["OGZH_LF260018"]),
        fact("post_termination_agreement", "Abmachung nach der Kündigung",
             "Gibt es eine Abmachung mit der Vermieterschaft (Stundung, Ratenzahlung, neuer Vertrag, Auszugstermin)?",
             "Einwand gegen Ausweisung oder Vollstreckung (Art. 341 Abs. 3 ZPO); möglicher neuer Mietvertrag.", group="history", req=True,
             prio="high", esc=True, src=["CH_ZPO_337_338_341"]),
        fact("client_wants_to_sign_move_out", "Klientin will Auszugstermin unterschreiben", "Will die Klientin «freiwillig» einen Auszugstermin oder eine Vereinbarung unterschreiben?",
             "Global G9: Unterschriften vor der Rechtsprüfung vermeiden.", group="history", prio="high", esc=True, src=["PRODUKTREGEL"]),
        fact("belongings_plan", "Hab und Gut", "Wo kommen Möbel und Sachen bei der Räumung hin (Einlagerung)?", "Soziale Notfallplanung.",
             type="string", group="social", prio="low", src=["PRODUKTREGEL"]),
    ]
)
for _f in facts:
    if _f["id"] in ("housing_solution_available", "challenge_filed", "landlord_self_help", "third_party_payment", "household_description",
                    "family_home_with_spouse"):
        _f["required"] = True

# Issue 6: alle Fakten werden parallel zur Eskalation erhoben; die Eskalation hängt von keinem Faktum ab.
escalation = [
    esc_rule("EV_OUT_OF_SCOPE_OBJECT", "Geschäftsraum, Pacht, Zimmer in Heim oder Notwohnung: andere Regeln / ausserhalb des Moduls (G5).",
             inn(F("object_type"), ["notwohnung_heim", "ferienwohnung_bis_3_monate", "andere"]), "MEDIUM", "OUT_OF_SCOPE_OBJECT",
             "Das Objekt fällt nicht unter die gewöhnliche Wohnraummiete dieses Moduls (z. B. Geschäftsraum, Heim, Notwohnung). Es werden keine Standardaussagen gemacht; Rechtsperson und Sozialarbeiterin prüfen sofort.",
             BOTH, suppress=True),
    esc_rule("EV_RAEUMUNG_STEHT", "Räumungstermin steht oder Räumung findet statt: SOZIAL + RECHT.",
             inn(F("eviction_stage"), ["ammannamt_raeumungstermin", "raeumung_heute_oder_schloss"]), "HIGH", "EVICTION_DATE_SET_OR_TODAY",
             "Ein Räumungstermin steht oder die Räumung findet statt. Sofort Unterkunft, Kinder und Hab und Gut sichern (Sozialarbeiterin) und restliche Einwände prüfen (Rechtsperson). Das Datum steht im Schreiben; das System rechnet nichts.",
             SOCIAL_FIRST),
    esc_rule("EV_GRUNDREGEL", "Ausweisung/Räumung: IMMER sofort Rechtsperson + Sozialarbeiterin, keine Rückfrage-Runden, kein KI_WEITER.",
             ALWAYS, "HIGH", "EVICTION_ALWAYS_IMMEDIATE",
             "Hinweis auf ein Ausweisungs- oder Räumungsverfahren: Der Wohnungsverlust ist konkret. Rechtsperson und Sozialarbeiterin handeln sofort und parallel (Frist prüfen, Unterkunft sichern). Das System stellt keine Rückfragen vor der Eskalation und macht keine Erfolgsprognose.",
             BOTH),
    esc_rule("EV_SELBSTHILFE", "Vermieterschaft räumt ohne Gericht: unzulässige Selbsthilfe.", eq(F("landlord_self_help"), True), "HIGH",
             "LANDLORD_SELF_HELP",
             "Die Vermieterschaft hat ohne Gericht das Schloss gewechselt, Sachen entfernt oder Leistungen abgestellt. Das ist unzulässig und kann strafbar sein; das System bewertet das nicht. Rechtsperson und Sozialarbeiterin sofort, nötigenfalls Polizei.",
             BOTH),
    esc_rule("EV_STADIUM_UNKLAR", "Stadium unklar: sofort, keine Rückfrage-Schleife.", unk(F("eviction_stage")), "HIGH", "EVICTION_STAGE_UNCLEAR",
             "Das Stadium des Verfahrens ist unklar. Es wird so gehandelt, als laufe bereits eine Frist: Rechtsperson und Sozialarbeiterin sofort.", BOTH),
    esc_rule("EV_NUR_KUENDIGUNG_ZAHLUNGSVERZUG", "Nur Kündigung wegen Zahlungsverzug, noch kein Verfahren: Issue 3.",
             all_(eq(F("eviction_stage"), "nur_kuendigung"), eq(F("eviction_termination_reason"), "zahlungsverzug")), "HIGH",
             "EVICTION_NOT_YET_STARTED_PAYMENT_DEFAULT",
             "Es liegt bisher nur eine Kündigung wegen Zahlungsverzug vor; ein Ausweisungsverfahren ist noch nicht eingeleitet. Die Regeln von Issue 3 gelten; sofortige Prüfung bleibt.",
             BOTH, route="CH_TENANCY_PAYMENT_DEFAULT"),
    esc_rule("EV_NUR_KUENDIGUNG_ANDERE", "Nur Kündigung (nicht Zahlungsverzug), noch kein Verfahren: Issue 1.",
             all_(eq(F("eviction_stage"), "nur_kuendigung"), inn(F("eviction_termination_reason"), ["ordentlich", "vertragsende", "andere"])),
             "HIGH", "EVICTION_NOT_YET_STARTED_TERMINATION",
             "Es liegt bisher nur eine Kündigung vor; ein Ausweisungsverfahren ist noch nicht eingeleitet. Die Regeln von Issue 1 gelten; sofortige Prüfung bleibt.",
             BOTH, route="CH_TENANCY_TERMINATION"),
    esc_rule("EV_UNTERSCHRIFT_AUSZUG", "Klientin will 'freiwillig' einen Auszugstermin unterschreiben (G9).",
             eq(F("client_wants_to_sign_move_out"), True), "HIGH", "EVICTION_SIGNATURE_RISK",
             "Die Klientin möchte einen Auszugstermin oder eine Vereinbarung unterschreiben. Das kann nicht rückgängig zu machende Folgen haben: nicht unterschreiben, bevor die Rechtsperson geprüft hat.", LEGAL),
    esc_rule("EV_ANFECHTUNG_HAENGIG", "Anfechtung der Kündigung läuft: schützt nicht automatisch vor Ausweisung.", eq(F("challenge_filed"), True),
             "HIGH", "EVICTION_CHALLENGE_PENDING",
             "Die Kündigung ist angefochten oder eine Erstreckung verlangt. Das schützt nicht automatisch vor einer Ausweisung. Gericht und Geschäftsnummer der Anfechtung ins Briefing; auf jedes Schreiben reagieren.", LEGAL),
    esc_rule("EV_NACHZAHLUNG", "Rückstand nach Ablauf der Zahlungsfrist bezahlt: heilt die Kündigung nicht.",
             eq(F("arrears_paid_timing"), "nach_fristablauf"), "HIGH", "EVICTION_LATE_PAYMENT_NOT_HEALING",
             "Der Rückstand wurde erst nach Ablauf der Zahlungsfrist bezahlt. Das heilt die Kündigung nicht; eine Einigung mit der Vermieterschaft kann aber möglich sein, das klärt die Rechtsperson.", LEGAL),
    esc_rule("EV_DRITTZAHLUNG", "Sozialdienst oder Dritte haben während der Zahlungsfrist gezahlt (Art. 68 OR).",
             any_(eq(F("third_party_payment"), True), eq(F("payment_returned_by_landlord"), True)), "HIGH", "EVICTION_THIRD_PARTY_PAYMENT",
             "Dritte (z. B. der Sozialdienst) haben gezahlt oder die Vermieterschaft hat Geld zurückgeschickt. Das kann den klaren Fall ausschliessen. Zahlungsbelege mit Datum und Zahlungszweck sofort beschaffen und der Rechtsperson geben.", LEGAL),
    esc_rule("EV_ABMACHUNG", "Abmachung/neuer Vertrag nach der Kündigung.", eq(F("post_termination_agreement"), True), "HIGH",
             "EVICTION_AGREEMENT_PRESENT",
             "Es gibt eine Abmachung mit der Vermieterschaft (Stundung, Ratenzahlung, neuer Vertrag, Auszugstermin). Schriftliche Bestätigung sichern; Einwände im Vollstreckungsverfahren nur mit Urkunden. Rechtsperson sofort.", LEGAL),
    esc_rule("EV_FAMILIENWOHNUNG", "Familienwohnung, Partnerperson nicht separat bedient: starker Einwand.",
             all_(eq(F("family_home_with_spouse"), True), eq(F("spouse_still_lives_there"), True), eq(F("separate_delivery_to_spouse"), False)),
             "HIGH", "EVICTION_FAMILY_HOME_NOT_SEPARATE",
             "Bei einer Familienwohnung wurde die Partnerperson laut Angabe nicht separat bedient (Mahnung/Kündigung). Das kann ein starker Einwand sein. Rechtsperson sofort.", LEGAL),
    esc_rule("EV_KEINE_ANSCHLUSSLOESUNG", "Keine Anschlusslösung nach dem Auszug: Notunterkunft.",
             any_(eq(F("housing_solution_available"), False), unk(F("housing_solution_available"))), "HIGH", "NO_HOUSING_SOLUTION",
             "Es gibt keine Anschlusslösung (oder sie ist unbekannt). Die Sozialarbeiterin prüft sofort Notunterkunft, Mietzinsgarantie und Einlagerung.", ["social_counselling"]),
    esc_rule("EV_GERICHTSENTSCHEID", "Entscheid des Gerichts eröffnet: sehr kurze Rechtsmittelfristen.",
             eq(F("eviction_stage"), "gerichtsentscheid"), "HIGH", "EVICTION_COURT_DECISION",
             "Ein Gerichtsentscheid liegt vor. Rechtsmittelfristen sind sehr kurz (dem Schreiben zu entnehmen, vom System nicht berechnet): das Schreiben heute noch einer Rechtsperson zeigen.", LEGAL),
    esc_rule("EV_VULNERABILITY", "Besondere Belastungssituation: ausserhalb des Moduls.", eq(F("vulnerability_present"), True), "MEDIUM",
             "OUTSIDE_MODULE_VULNERABILITY",
             "Es liegt eine besondere Belastungssituation vor. Das liegt ausserhalb dieses Moduls und gehört in menschliche Hände.", BOTH),
    esc_rule("EV_EXPERT_REQUESTED", "Fachperson ausdrücklich gewünscht.", eq(F("client_requests_expert"), True), "LOW", "EXPERT_REQUESTED",
             "Es wurde ausdrücklich eine Fachperson gewünscht. Dieser Wunsch wird immer respektiert.", LEGAL),
]

legal_rules = [
    legal("EV_HINT_KEINE_SELBSTHILFE", "Räumung nur durch Gerichtsentscheid.", ALWAYS, "HINT_NO_SELF_EVICTION",
          "Die Vermieterschaft darf die Wohnung nicht selbst räumen. Dafür braucht es einen Entscheid eines Gerichts.",
          ["CH_ZPO_343_1_D", "LEHRBUCH_MIETE_31"]),
    legal("EV_HINT_BEHOERDENFRIST", "Kurze Behördenfristen.", ALWAYS, "HINT_SHORT_AUTHORITY_DEADLINES",
          "Schreiben von Gericht oder Ammannamt enthalten oft sehr kurze Fristen. Bitte heute noch einer Rechtsfachperson zeigen.",
          ["CH_ZPO_239_2", "CH_ZPO_314_1", "CH_ZPO_321_2"]),
    legal("EV_HINT_ANFECHTUNG", "Anfechtung schützt nicht automatisch.", ALWAYS, "HINT_CHALLENGE_NO_PROTECTION",
          "Auch wenn die Kündigung angefochten ist, kann ein Ausweisungsverfahren laufen. Reagieren Sie deshalb auf jedes Schreiben.",
          ["BGE_141_III_262"]),
    legal("EV_HINT_NACHZAHLUNG", "Nachzahlung nach Fristablauf.", eq(F("arrears_paid_timing"), "nach_fristablauf"), "HINT_LATE_PAYMENT_NOT_HEALING",
          "Wer nach Ablauf der Zahlungsfrist bezahlt, macht die Kündigung dadurch nicht ungültig. Eine Einigung mit der Vermieterschaft kann aber trotzdem möglich sein; das klärt eine Fachperson.",
          ["OGZH_LF260018"]),
    legal("EV_HINT_UNTERKUNFT", "Parallel Unterkunft suchen.", ALWAYS, "HINT_SEARCH_ACCOMMODATION_NOW",
          "Parallel zur rechtlichen Prüfung sollte jetzt eine Unterkunft gesucht werden.", ["PRODUKTREGEL"]),
    legal("EV_HINT_UNTERLAGEN", "Schreiben aufbewahren.", ALWAYS, "HINT_KEEP_DOCUMENTS",
          "Bewahren Sie alle Schreiben mit Umschlag und Abholungseinladung auf.", ["PRODUKTREGEL"]),
    legal("EV_HINT_DRITTZAHLUNG", "Zahlungen Dritter sichern.", any_(eq(F("third_party_payment"), True), eq(F("payment_returned_by_landlord"), True)),
          "HINT_THIRD_PARTY_PAYMENT_EVIDENCE",
          "Hat der Sozialdienst oder eine andere Person während der Zahlungsfrist für die Klientin bezahlt, kann das entscheidend sein. Bitte alle Zahlungsbelege mit Datum und Zahlungszweck sofort der Rechtsperson geben.",
          ["BGER_4A_68_2014"]),
    legal("EV_REVIEW_KLARER_FALL", "Einwände verhindern den klaren Fall.", ALWAYS, "REVIEW_CLEAR_CASE_OBJECTIONS",
          "Prüfhinweis: Im Verfahren für klare Fälle tritt das Gericht nicht ein, wenn Sachverhalt oder Rechtslage nicht klar sind (Art. 257 Abs. 3 ZPO); substanziierte und schlüssige Einwände genügen. Die Vermieterschaft kann dann den ordentlichen Weg gehen (kein endgültiger Sieg).",
          ["CH_ZPO_257", "BGE_138_III_620", "BGE_138_III_123", "BGE_140_III_315"], kind="REVIEW_POINT"),
    legal("EV_REVIEW_STREITWERT", "Berufung/Beschwerde, Aufschub.", ALWAYS, "REVIEW_APPEAL_SUSPENSIVE_EFFECT",
          "Prüfhinweis: Berufung ab CHF 10 000 Streitwert hemmt die Vollstreckbarkeit; die Beschwerde darunter nicht automatisch. Die Rechtsperson muss ggf. Aufschub beantragen.",
          ["CH_ZPO_308_2", "CH_ZPO_315_1", "CH_ZPO_325"], kind="REVIEW_POINT"),
    legal("EV_REVIEW_KINDER", "Kinder, Krankheit, Alter: kein Hindernis bei Zahlungsverzug.", eq(F("children_in_household"), True),
          "REVIEW_CHILDREN_NO_BAR", "Prüfhinweis: Kinder, Krankheit oder hohes Alter sind bei Zahlungsverzug kein rechtliches Hindernis der Ausweisung; im Vordergrund steht die soziale Notfallplanung.",
          ["CH_OR_272A_1_A", "BGER_4A_391_2013", "OGZH_LF260018"], kind="REVIEW_POINT"),
]

SPEC = {
    "id": ID,
    "issue": "eviction",
    "dossier": "issue_06.docx",
    "title_de": "Ausweisung und Räumung (Issue 6)",
    "description": "Ausweisungsverfahren und Räumung nach Kündigung oder Vertragsende (u. a. Art. 257, 343 ZPO). Dringendstes Issue: immer sofortige, parallele Eskalation; keine Rückfrage-Runden (bewusste Ausnahme von G7); Fristen werden nur wörtlich zitiert.",
    "provenance_de": "Law-Dossier Issue 6 vom 7.11.2026; Teamentscheide: keine Rückfrage-Runden (Ausnahme zu G7), Unterlagenliste für die Sozialarbeiterin.",
    "classification": {
        "description": "Passt bei Ausweisungsgesuch, Vorladung des Gerichts, Entscheid, Schreiben des Gemeinde-/Stadtammannamts, Räumungstermin, Schlossauswechslung oder Räumung durch die Vermieterschaft. Stichworte: Ausweisung, Räumung, Stadtammann, Gemeindeammann, Einzelgericht, Audienz, klare Fälle, Schloss ausgewechselt, 'morgen kommt das Stadtammannamt'. NICHT passend: blosse Kündigung ohne Verfahren (Issue 1/3).",
        "typical_situations": [
            "Morgen kommt das Stadtammannamt.",
            "Meine Klientin hat ein Ausweisungsgesuch des Gerichts bekommen.",
            "Der Vermieter hat das Schloss ausgewechselt.",
            "Das Gericht hat die Ausweisung angeordnet, der Räumungstermin steht.",
        ],
        "related_issues": [],
    },
    "facts": facts,
    "escalation": escalation,
    "legal": legal_rules,
    "default_professionals": ["tenancy_law_counsel", "social_counselling"],
    "briefing": {
        "intro_de": "Ausweisung und Räumung – sofortige Weitergabe (Stadium und Dokument zuerst)",
        "groups": [
            {"id": "stage", "title_de": "Stadium, Dokument, Geschäftsnummer, Frist (wörtlich)",
             "fact_ids": ["eviction_stage", "eviction_document_available", "court_reference", "document_receipt_date", "deadline_quoted_text"]},
            {"id": "history", "title_de": "Kündigung, Zahlungen, Abmachungen",
             "fact_ids": ["eviction_termination_reason", "family_home_with_spouse", "spouse_still_lives_there", "separate_delivery_to_spouse",
                          "arrears_paid_timing", "third_party_payment", "payment_returned_by_landlord", "post_termination_agreement",
                          "challenge_filed", "client_wants_to_sign_move_out", "landlord_self_help"]},
            {"id": "social", "title_de": "Haushalt, Kinder, Gesundheit, Anschlusslösung",
             "fact_ids": ["household_description", "children_in_household", "housing_solution_available", "social_assistance_received", "belongings_plan"]},
            {"id": "situation", "title_de": "Vorprüfung",
             "fact_ids": ["tenant_role", "object_type", "property_municipality", "property_in_canton_zh", "vulnerability_present",
                          "client_requests_expert", "consent_briefing"]},
        ],
        "review_points": [
            {"text_de": "Stadium, Gericht/Amt, Geschäftsnummer und die wörtlich zitierte Frist aus dem Schreiben (nicht berechnet).",
             "source_ids": ["CH_ZPO_239_2", "CH_ZPO_314_1", "CH_ZPO_321_2"]},
            {"text_de": "Vorfrage Gültigkeit der Kündigung (Mahnung, Zahlung innert Frist, Form, Familienwohnung) und mögliche Einwände gegen den klaren Fall.",
             "source_ids": ["BGE_141_III_262", "BGE_138_III_620", "CH_ZPO_257"]},
            {"text_de": "Zahlungen Dritter (Sozialdienst) mit Datum und Zahlungszweck; Rücküberweisungen.",
             "source_ids": ["BGER_4A_68_2014"]},
            {"text_de": "Vollstreckung durch das Gemeinde-/Stadtammannamt, Einwände nur nach Art. 341 Abs. 3 ZPO.",
             "source_ids": ["CH_ZPO_343_1_D", "CH_ZPO_337_338_341", "ZH_GOG_147"]},
        ],
        "documents_to_request": [
            "Mietvertrag", "Kündigung mit Couvert", "Mahnung", "Zahlungsbelege inkl. Zahlungen des Sozialdienstes",
            "Gesuch und Vorladung des Gerichts", "Schreiben des Gemeinde- oder Stadtammannamts",
        ],
        "authority_ids": ["EINZELGERICHT_BEZIRKSGERICHT_ZH", "MIETGERICHT_ZH", "OBERGERICHT_ZH_ZIVILKAMMER", "STADTAMMANNAMT_ZH",
                          "SOZIALDIENST_WOHNGEMEINDE", "NOTUNTERKUNFT_FAMILIEN_STADT_ZH", "NOTSCHLAFSTELLE_ZH", "MIETERVERBAND_ZH"],
    },
}

_BASE = {
    "tenant_role": "hauptmieterin", "object_type": "wohnung", "property_municipality": "Zürich", "property_in_canton_zh": True,
    "family_home_with_spouse": False, "eviction_stage": "gesuch_oder_vorladung", "eviction_document_available": True,
    "document_receipt_date": "2026-11-05", "deadline_quoted_text": "Stellungnahme innert 10 Tagen",
    "eviction_termination_reason": "zahlungsverzug", "arrears_paid_timing": "nicht_bezahlt", "post_termination_agreement": False,
    "challenge_filed": False, "housing_solution_available": True, "landlord_self_help": False, "third_party_payment": False,
    "household_description": "Alleinstehend",
}


def _f(**kw):
    d = dict(_BASE)
    d.update(kw)
    return d


SPEC["scenarios"] = [
    scenario("SC_EV_T601", "T6-01 Verfügung des Einzelgerichts mit Frist zur Stellungnahme", "ESCALATE", issues=[ID], facts=_f(), urgency="HIGH",
             rules=["EV_GRUNDREGEL"]),
    scenario("SC_EV_T602", "T6-02 Stadtammannamt: Räumung am Dienstag", "ESCALATE", issues=[ID],
             facts=_f(eviction_stage="ammannamt_raeumungstermin"), urgency="HIGH", rules=["EV_RAEUMUNG_STEHT"]),
    scenario("SC_EV_T603", "T6-03 Schloss gewechselt, kein Gericht", "ESCALATE", issues=[ID],
             facts=_f(eviction_stage="raeumung_heute_oder_schloss", landlord_self_help=True), urgency="HIGH", rules=["EV_SELBSTHILFE"]),
    scenario("SC_EV_T604", "T6-04 Rückstand nach Fristablauf bezahlt, Gesuch liegt vor", "ESCALATE", issues=[ID],
             facts=_f(arrears_paid_timing="nach_fristablauf"), urgency="HIGH", rules=["EV_NACHZAHLUNG"]),
    scenario("SC_EV_T605", "T6-05 Anfechtung hängig, nun Ausweisungsgesuch", "ESCALATE", issues=[ID], facts=_f(challenge_filed=True),
             urgency="HIGH", rules=["EV_ANFECHTUNG_HAENGIG"]),
    scenario("SC_EV_T606", "T6-06 Nur 'Klientin muss raus', kein Dokument: Stadium unklar, sofort", "ESCALATE", issues=[ID],
             facts={}, unknown=["eviction_stage"], urgency="HIGH", rules=["EV_STADIUM_UNKLAR", "EV_GRUNDREGEL"]),
    scenario("SC_EV_T607", "T6-07 Nur Kündigung wegen Zahlungsverzug -> Issue 3", "ESCALATE", issues=[ID],
             facts=_f(eviction_stage="nur_kuendigung"), urgency="HIGH", rules=["EV_NUR_KUENDIGUNG_ZAHLUNGSVERZUG"],
             routes=["CH_TENANCY_PAYMENT_DEFAULT"]),
    scenario("SC_EV_08_DRITTZAHLUNG", "Sozialdienst hat innert Frist gezahlt", "ESCALATE", issues=[ID], facts=_f(third_party_payment=True),
             urgency="HIGH", rules=["EV_DRITTZAHLUNG"]),
    scenario("SC_EV_09_UNTERSCHRIFT", "Klientin will Auszugstermin unterschreiben", "ESCALATE", issues=[ID],
             facts=_f(client_wants_to_sign_move_out=True), urgency="HIGH", rules=["EV_UNTERSCHRIFT_AUSZUG"]),
    scenario("SC_EV_10_KEINE_RUECKFRAGE_RUNDE", "Fehlende Angaben: Eskalation wartet nicht (keine Rückfrage-Schleife)", "ESCALATE", issues=[ID],
             facts={"eviction_stage": "gesuch_oder_vorladung"}, urgency="HIGH", rules=["EV_GRUNDREGEL"]),
]
