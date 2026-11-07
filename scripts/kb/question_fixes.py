"""Question quality audit corrections (Fragequalität, 7 Mietrechts-Issues).

Only the wording of ``question_de`` changes. Fact IDs, data types, enum values, conditions, rules and sources are untouched,
so stored answers, history, briefings and the rule engine behave exactly as before.

kind: U = Upload-Formulierung entfernt · T = Fragetext korrigiert (versteckte Teilfrage entfernt / Frage passt zum Antworttyp)
Details that were part of a removed sub-question are captured by an existing fact (named in ``note``) or can be added in
the free text «Weitere Informationen ergänzen»; open points for the law team are in docs/QUESTION_QUALITY_AUDIT.md.
"""

# fact_id: (kind, new question, note)
FIXES: dict[str, tuple[str, str, str]] = {
    "client_residence_municipality": (
        "T",
        "In welcher Gemeinde wohnt die Klientin? Nur nötig, wenn der Wohnsitz nicht in der Gemeinde der Wohnung liegt; sonst bitte überspringen.",
        "Textfrage statt versteckter Ja/Nein-Vorfrage",
    ),
    "vulnerability_present": (
        "T",
        "Trifft mindestens eines davon zu: Gewalt, Trennungsstreit, Sprachbarriere oder akute Krise?",
        "klare Ja/Nein-Formulierung",
    ),
    "defect_description": ("T", "Was genau ist kaputt oder stört?", "«Seit wann?» → defect_since (Datum)"),
    "defect_at_move_in": ("T", "Bestand der Mangel schon beim Einzug?", "Einzugsprotokoll → evidence_available / Fallbericht; Law-Team prüfen"),
    "landlord_informed": (
        "U",
        "Weiss die Vermieterschaft oder Verwaltung von dem Mangel?",
        "«Wie/wann/schriftlich» → landlord_informed_in_writing, landlord_informed_date; Upload entfernt",
    ),
    "landlord_informed_date": ("T", "An welchem Datum wurde der Mangel der Vermieterschaft gemeldet?", "Datumstyp"),
    "rent_payment_status": ("T", "Wie wird die Miete derzeit bezahlt?", "Auswahlfrage statt Ja/Nein-Anmutung"),
    "rent_deposit_started": (
        "T",
        "Hat die Klientin schon Miete hinterlegt?",
        "Fälligkeit des ersten hinterlegten Mietzinses nicht separat erfasst; Law-Team prüfen",
    ),
    "termination_after_report": (
        "T",
        "Hat die Vermieterschaft gekündigt oder damit gedroht, seit die Mängel gemeldet wurden?",
        "«Schlichtungsverfahren?» → authority_letter_received",
    ),
    "reported_extent": (
        "U",
        "Wie zeigt sich der Schimmel: nur als Geruch, als kleine Stelle oder als grössere Fläche?",
        "Optionen passen jetzt zur Frage; Ort → affected_rooms, Beginn → defect_since; Foto-Upload entfernt",
    ),
    "children_exposed": ("T", "Nutzen die Kinder, die in der Wohnung leben, die betroffenen Räume?", "Kinder im Haushalt → children_in_household"),
    "challenge_filed": (
        "T",
        "Hat die Klientin die Kündigung schon bei der Schlichtungsbehörde angefochten oder eine Erstreckung verlangt?",
        "«Wann, wo?» nicht separat erfasst",
    ),
    "social_assistance_received": (
        "T",
        "Bezieht die Klientin Sozialhilfe?",
        "«Sozialdienst informiert?» nicht separat erfasst; Law-Team prüfen",
    ),
    "third_party_payment": (
        "T",
        "Hat jemand anderes für die Klientin gezahlt (Sozialdienst, Angehörige, Stiftung)?",
        "Zeitpunkt, Betrag, Zahlungszweck als Ergänzung im Freitext",
    ),
    "payment_returned_by_landlord": (
        "T",
        "Hat die Vermieterschaft eine Zahlung zurückgeschickt oder abgelehnt?",
        "Zeitpunkt (vor/nach Fristende) als Ergänzung im Freitext",
    ),
    "eviction_stage": ("T", "Was liegt derzeit vor?", "Buchstaben (a)–(e) im Text entfernt; Auswahloptionen zeigen die Stufen"),
    "eviction_document_available": (
        "U",
        "Liegt das Schreiben vollständig vor (alle Seiten, mit Umschlag)?",
        "Upload entfernt; Hinweis «für die Fachperson bereithalten» im Warum-Text",
    ),
    "document_receipt_date": (
        "T",
        "An welchem Datum wurde das Schreiben empfangen oder auf der Post abgeholt?",
        "Datumstyp; Abholungseinladung → pickup-Fakten der Issues",
    ),
    "deadline_quoted_text": (
        "T",
        "Welche Frist (Stellungnahme, Auszug, Räumungstermin) steht im Schreiben? Bitte wörtlich wiedergeben, oder «keine Frist» angeben.",
        "Textfrage statt Ja/Nein-Anmutung",
    ),
    "arrears_paid_timing": (
        "U",
        "Wurde der Mietzinsrückstand bezahlt? Wenn ja: vor oder nach Ablauf der Zahlungsfrist?",
        "Auswahl deckt beide Teile ab; «Belege?» entfernt",
    ),
    "post_termination_agreement": (
        "T",
        "Gibt es eine Abmachung mit der Vermieterschaft (Stundung, Ratenzahlung, neuer Vertrag, Auszugstermin)?",
        "«Schriftlich?» nicht separat erfasst; Law-Team prüfen",
    ),
    "pickup_notice_date": ("T", "An welchem Datum lag der gelbe Zettel (Abholungseinladung) im Briefkasten?", "Datumstyp"),
    "receipt_date": ("T", "An welchem Datum hatte die Klientin die Kündigung tatsächlich in den Händen?", "Datumstyp"),
    "stated_reason": (
        "T",
        "Welcher Kündigungsgrund steht im Schreiben (Eigenbedarf, Sanierung, Abbruch, anderer Grund) oder steht keiner darin?",
        "Auswahlfrage",
    ),
    "previous_extension": (
        "T",
        "Wurde das Mietverhältnis schon einmal erstreckt (Entscheid oder Vereinbarung)?",
        "«Bis wann?» → previous_extension_end_date; «Verzicht?» → settlement_with_waiver_offered",
    ),
    "previous_extension_end_date": ("T", "Bis zu welchem Datum läuft die erste Erstreckung?", "Datumstyp"),
    "tenancy_start_date": ("T", "Ab welchem Datum wohnt die Klientin dort (Mietbeginn, ungefähr genügt)?", "Datumstyp"),
    "school_change_needed": ("T", "Wäre für schulpflichtige Kinder ein Schulwechsel nötig?", "Kinder im Haushalt → children_in_household"),
    "cohabitant_partner": (
        "T",
        "Wohnt eine Lebenspartnerin oder ein Lebenspartner ohne Heirat oder Eintragung mit?",
        "«Seit wann / wer unterschrieb?» nicht separat erfasst; Law-Team prüfen",
    ),
    "search_efforts": (
        "T",
        "Sucht die Klientin bereits eine neue Wohnung, und sind die Suchbemühungen dokumentiert?",
        "Auswahl deckt beide Teile ab",
    ),
    "warning_written": ("U", "Liegt die Mahnung schriftlich vor?", "«(Foto)» entfernt"),
    "warning_amount_clear": (
        "T",
        "Ist in der Mahnung klar bezeichnet, welcher Betrag für welche Monate verlangt wird?",
        "Ja/Nein statt Betragsfrage",
    ),
    "warning_deadline_days": ("T", "Wie viele Tage Zahlungsfrist setzt das Schreiben (Anzahl Tage)?", "Zahlentyp; nur Datum angegeben → Differenz selbst bilden"),
    "warning_receipt_date": ("T", "An welchem Datum hat die Klientin das Schreiben erhalten oder auf der Post abgeholt?", "Datumstyp"),
    "payment_path": (
        "T",
        "Über welchen Weg soll bezahlt werden (Einzahlungsschein, Überweisung, bar oder anderes)?",
        "Auswahlfrage; «Beiliegender Einzahlungsschein» ist eine Option",
    ),
    "social_payment_failed": (
        "T",
        "Ist eine Mietzahlung des Sozialdienstes an die Vermieterschaft ausgeblieben?",
        "«Zahlt der Sozialdienst?» → rent_payer",
    ),
    "paid_in_time": ("T", "Wurde der ganze Betrag innert der Zahlungsfrist bezahlt?", "«Wann, wie, Belege?» entfernt"),
    "partial_payment_with_notice": (
        "T",
        "Wurde nur ein Teil bezahlt und die Vermieterschaft dabei schriftlich darauf hingewiesen?",
        "klare gemeinsame Tatsache",
    ),
    "setoff_or_deposit_done": ("T", "Wurde verrechnet oder hinterlegt?", "«Wann, gegenüber wem?» als Ergänzung im Freitext"),
    "payment_after_deadline_accepted": (
        "T",
        "Hat die Vermieterschaft eine Zahlung angenommen, die nach Fristablauf erfolgte?",
        "Eine Tatsache; «nein» gilt auch, wenn nicht nach Fristablauf gezahlt wurde",
    ),
    "payment_status": ("T", "Was wurde seit der Mahnung bezahlt: nichts, einen Teil oder alles?", "Auswahlfrage"),
    "increase_letter_available": (
        "U",
        "Liegt das Schreiben der Vermieterschaft vollständig vor (alle Seiten, Umschlag)?",
        "Upload entfernt",
    ),
    "increase_receipt_date": ("T", "An welchem Datum wurde das Schreiben empfangen oder auf der Post abgeholt?", "Datumstyp"),
    "form_official_used": (
        "T",
        "Ist das Schreiben das amtliche Formular «Mitteilung von Mietzinserhöhungen und einseitigen Vertragsänderungen (Art. 269d OR)» (Zürich, drei Seiten) und nicht bloss ein Brief oder eine E-Mail?",
        "eindeutige Ja/Nein-Frage",
    ),
    "effective_date_in_letter": ("T", "Ab welchem Datum soll die Änderung gelten?", "Datumstyp"),
    "increase_already_paying": ("T", "Zahlt die Klientin schon den neuen Betrag?", "«Seit wann?» als Ergänzung im Freitext"),
    "rent_affordable": (
        "T",
        "Kann die Klientin die neue Miete bezahlen?",
        "Sozialhilfe-Mietzinslimite bleibt im Erklärtext; Law-Team prüfen",
    ),
    "form_photo_available": (
        "U",
        "Liegt das Kündigungsformular vollständig vor (beide Seiten)?",
        "Foto-/Upload-Anmutung entfernt",
    ),
}

# why_needed_de texts that mention a photo/upload (fact_id: (old fragment, new fragment))
WHY_FIXES: dict[str, tuple[str, str]] = {
    "form_photo_available": ("Das Foto ermöglicht der Fachperson die Formprüfung.", "Mit dem vollständigen Formular kann die Fachperson die Form prüfen."),
}
