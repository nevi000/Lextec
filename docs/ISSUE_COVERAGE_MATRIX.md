# Issue-Abdeckungsmatrix (Issues 1–7)

> GENERIERT durch `scripts/kb/build_coverage_matrix.py` aus den Law-Dossiers (`docs/legal_inputs/issues_extracted/*.json`) und der geladenen Wissensbasis. Nicht von Hand ändern.
> Stand der Dossiers: 7.11.2026. **Kein Issue ist juristisch freigegeben** (`content_status: DRAFT`).

Statuswerte: `IMPLEMENTED` (in KB/Engine abgebildet und getestet) · `PARTIAL` (teilweise oder nur als Faktum/Hinweis) · `PENDING_LEGAL_REVIEW` (umgesetzt, aber fachlich/juristisch noch zu bestätigen) · `NOT_APPLICABLE` (bewusst nicht umgesetzt, Dossier verbietet es) · `BLOCKED` (Zulieferung fehlt).

## Übersicht

| Issue | KB-ID | Fakten | Eskalationsregeln | Rechtsregeln (HINT / REVIEW) | Szenarien | Dossier-Eskalationszeilen abgedeckt |
|---|---|---:|---:|---:|---:|---|
| 1 Kündigung durch die Vermieterschaft | `CH_TENANCY_TERMINATION` | 35 | 23 | 10 / 7 | 38 | 14 / 14 |
| 2 Zahlungsaufforderung mit Kündigungsandrohung | `CH_TENANCY_PAYMENT_WARNING` | 36 | 20 | 12 / 4 | 15 | 14 / 14 |
| 3 Kündigung wegen Zahlungsverzug | `CH_TENANCY_PAYMENT_DEFAULT` | 44 | 15 | 8 / 6 | 15 | 10 / 10 |
| 4 Erstreckung des Mietverhältnisses | `CH_TENANCY_EXTENSION` | 37 | 15 | 9 / 5 | 12 | 9 / 9 |
| 5 Mängel an der Mietsache | `CH_TENANCY_DEFECTS` | 43 | 25 | 11 / 4 | 16 | 13 / 13 |
| 6 Ausweisung und Räumung | `CH_TENANCY_EVICTION` | 28 | 17 | 7 / 3 | 10 | 6 / 6 |
| 7 Mietzinserhöhung | `CH_TENANCY_RENT_INCREASE` | 38 | 14 | 8 / 8 | 12 | 9 / 9 |

Insgesamt 75 Eskalationszeilen aus den Dossiers; jede ist einer oder mehreren Regel-IDs zugeordnet (siehe unten).

## Issue 1 – Kündigung durch die Vermieterschaft (`CH_TENANCY_TERMINATION`)

### Elemente

| Dossier-Element | Status | Umsetzung |
|---|---|---|
| Gesetzesartikel (25) | `IMPLEMENTED` | Alle als Quellen in `sources.yaml` (Wortlaut `text_de`, `valid_as_of`, PDF-Seite); Fedlex-Verifikation steht aus (`UNVERIFIED`). |
| Leitentscheide (8) | `PENDING_LEGAL_REVIEW` | Alle als Quellen mit Kernaussage/Fundstelle; Prüfstand «Volltext» laut Dossier, nicht systemseitig verifiziert. |
| Benötigte Informationen | `IMPLEMENTED` | 35 Fakten inkl. gemeinsam genutzter Vorprüfung; bedingte Pflicht über `required_if`; gleiche Frage nur einmal pro Fall. |
| Grenzen und Ausnahmefälle | `IMPLEMENTED` | Als Eskalationsregeln, Prüfhinweise (REVIEW_POINT) und Aussagenfilter; nicht 1:1 abgebildete Randfälle siehe «Lücken». |
| Verfahren und Fristen | `IMPLEMENTED` | Nur als Aussage/Hinweis und Produktschwelle; **kein berechnetes Fristende**. |
| Stellen und Behörden | `PENDING_LEGAL_REVIEW` | `authorities.yaml` (`contact_verified: false`) und `referral_network.yaml` (Signale); keine erfundenen Kontakte. |
| Eskalationsregeln | `IMPLEMENTED` | Tabelle unten. |
| Erlaubte/verbotene Aussagen | `IMPLEMENTED` | Tabellen unten; Policy-Muster in `forbidden_statements.yaml`. |
| Briefing für die Fachperson | `IMPLEMENTED` | `briefing_profile` (Gruppen, Prüfpunkte, Dokumente, Stellen) im gemeinsamen Fallbericht; Template nicht dupliziert. |
| Teamentscheide (7.11.2026) | `IMPLEMENTED` | Siehe Eskalations- und Aussagen-Tabellen; Einwilligung `consent_briefing`; G7 pro Fakt (max. 2 Nachfragen, danach UNKNOWN → Eskalation). |

### Eskalationsregeln des Dossiers

| # | Wenn (Dossier) | Route / Dringlichkeit (Dossier) | Regel-ID(s) | Status |
|---:|---|---|---|---|
| 1 | Ein zwingendes Faktum ist noch nicht erhoben | Rückfrage · – | Engine (ASK) | `IMPLEMENTED` |
| 2 | Empfangsdatum oder Zustellart nach Rückfrage unbekannt | Rechtsperson · sofort | `TT_UNKNOWN_DELIVERY_OR_RECEIPT` | `IMPLEMENTED` |
| 3 | 20 oder mehr Tage seit dem frühesten bekannten Datum (Abholungseinladung oder Empfang) | Rechtsperson · sofort | `TT_DAYS_GE_20` | `IMPLEMENTED` |
| 4 | Mehr als 30 Tage | Rechtsperson · sofort | `TT_DAYS_GT_30` | `IMPLEMENTED` |
| 5 | Weniger als 20 Tage, alles bekannt | Rechtsperson · bald | `TT_DAYS_LT_20_ALL_KNOWN` | `IMPLEMENTED` |
| 6 | Kein Formular oder Familienwohnung nicht separat zugestellt | Rechtsperson · bald | `TT_FORM_MISSING`, `TT_FAMILY_HOME_NOT_SEPARATE`, `TT_CO_TENANT_NOT_NOTIFIED` | `IMPLEMENTED` |
| 7 | Streit oder Verfahren mit Vermieterschaft in den letzten 3 Jahren | Rechtsperson · bald | `TT_PRIOR_DISPUTE`, `TT_FAMILY_CHANGE` | `IMPLEMENTED` |
| 8 | Grund: Sanierung, Abbruch, Eigenbedarf | Rechtsperson · bald | `TT_REASON_SPECIAL` | `IMPLEMENTED` |
| 9 | Kinder, Krankheit, lange Mietdauer | + Sozialarbeiter:in, Issue 4 · bald | `TT_HARDSHIP` | `IMPLEMENTED` |
| 10 | Auszug in weniger als 60 Tagen | + Sozialarbeiter:in · bald | `TT_MOVE_OUT_LT_60` | `IMPLEMENTED` |
| 11 | Kündigung wegen Zahlungsverzug | Wechsel zu Issue 3 · sofort | `TT_PAYMENT_DEFAULT` | `IMPLEMENTED` |
| 12 | Aufhebungsvereinbarung unterschrieben oder vorgelegt | Rechtsperson · sofort | `TT_AGREEMENT` | `IMPLEMENTED` |
| 13 | Klientin ist nicht Mieterin, Notwohnung, Untermiete | Rechtsperson (unabhängig) · bald | `TT_OUT_OF_SCOPE_ROLE`, `TT_OUT_OF_SCOPE_OBJECT`, `TT_FURNISHED_ROOM` | `IMPLEMENTED` |
| 14 | Klientin oder Sozialarbeiterin wünscht Fachperson | Rechtsperson · normal | `TT_EXPERT_REQUESTED` | `IMPLEMENTED` |

Zusätzlich aus den Teamentscheiden: `TT_FIXED_TERM_LE_75` (befristet, ≤ 75 Tage bis Vertragsende → sofort).

### Erlaubte Aussagen (8)

| Aussage (Dossier, gekürzt) | Status | HINT-ID |
|---|---|---|
| Eine Kündigung kann innert 30 Tagen nach Empfang bei der Schlichtungsbehörde angefochten werden. | `IMPLEMENTED` | `TT_HINT_30_DAYS` |
| Beim Einschreiben gilt die Kündigung in der Regel am Tag nach dem Einwurf der Abholungseinladung als empfangen… | `IMPLEMENTED` | `TT_HINT_REGISTERED_MAIL` |
| Die Vermieterschaft muss auf dem amtlichen Formular kündigen. Ob hier ein Mangel vorliegt, soll eine Fachperso… | `IMPLEMENTED` | `TT_HINT_OFFICIAL_FORM` |
| Die Klientin kann verlangen, dass die Kündigung begründet wird. Die Begründung ist aber keine Gültigkeitsvorau… | `IMPLEMENTED` | `TT_HINT_REASON_ON_REQUEST` |
| Eine besondere Härte macht die Kündigung nicht ungültig, kann aber eine Erstreckung rechtfertigen, bei Wohnung… | `IMPLEMENTED` | `TT_HINT_HARDSHIP` |
| Ist der Kündigungstermin falsch, gilt die Kündigung auf den nächstmöglichen Termin. | `IMPLEMENTED` | `TT_HINT_WRONG_TERMIN` |
| Zuständig ist die Schlichtungsbehörde im Bezirk, in dem die Wohnung liegt. Das Schlichtungsverfahren kostet ke… | `IMPLEMENTED` | `TT_HINT_VENUE_COSTS` |
| Lehnt eine Partei einen Entscheidvorschlag der Schlichtungsbehörde ab, muss sie selbst innert 30 Tagen klagen. | `IMPLEMENTED` | `TT_HINT_PROPOSAL` |

### Verbotene Aussagen (8)

Alle 8 Dossier-Punkte sind über `policies/forbidden_statements.yaml` (Muster, beim Laden und zur Laufzeit geprüft) bzw. als Systemregel (keine Fristberechnung, keine Prognose, keine Prozentzahl, kein Referenzzinssatz) umgesetzt; die konkreten Beispielsätze sind in `apps/api/tests/test_issues_2_7.py::test_forbidden_statements_from_the_dossiers_are_blocked` bzw. `test_issue01.py` getestet. Abstrakte Punkte wie «Jedes berechnete Fristende» sind durch `FB_DEADLINE_END_DATE` und Textprüfungen der KB abgedeckt.

### Lücken und offene Zulieferungen

| Punkt | Status | Anmerkung |
|---|---|---|
| Ortsübliche Kündigungstermine (Art. 266c OR) | `PENDING_LEGAL_REVIEW` | Nicht hart kodiert (Teamvorgabe): Prüfhinweis TT_HINT_LOCAL_TERMS. Amtliche Quelle der Termine für Zürcher Gemeinden fehlt (Law-Team). |

### Offene Prüfpunkte laut Dossier (☐) – juristische Bestätigung

- ☐ Reserve-Entscheide bei Bedarf im Volltext lesen (BGE 137 III 208, 148 III 215, 136 III 257, 145 III 281)  → `PENDING_LEGAL_REVIEW`
- ☐ Amtliche Quelle für die konkreten ortsüblichen Kündigungstermine der Wohnungsmiete in Zürcher Gemeinden beschaffen (Schlichtungsbehörde oder Mieterverband; die Obergerichtsseite «Ordentliche Kündigung» nennt keine Daten). Nicht verwenden: Merkblatt der Baudirektion vom Juli 2024, es betrifft die landwirtschaftliche Pacht (Art. 16 Abs. 3 LPG)  → `PENDING_LEGAL_REVIEW`
- ☐ Aktuelles amtliches Kündigungsformular des Kantons Zürich beschaffen (Muster für die Formprüfung im Upload)  → `PENDING_LEGAL_REVIEW`
- ☐ Möbliertes Zimmer: Welche Formvorschriften gelten genau?  → `PENDING_LEGAL_REVIEW`
- ☐ Kontaktdaten und Kosten der Stellen in Abschnitt 5 auf den offiziellen Seiten bestätigen  → `PENDING_LEGAL_REVIEW`
- ☐ Kantonale Praxis (Obergericht ZH) ergänzen, falls Zeit bleibt (entscheidsuche.ch, Filter ZH_Obergericht)  → `PENDING_LEGAL_REVIEW`

Bereits vom Law-Team erledigt (☒): 3.

## Issue 2 – Zahlungsaufforderung mit Kündigungsandrohung (`CH_TENANCY_PAYMENT_WARNING`)

### Elemente

| Dossier-Element | Status | Umsetzung |
|---|---|---|
| Gesetzesartikel (17) | `IMPLEMENTED` | Alle als Quellen in `sources.yaml` (Wortlaut `text_de`, `valid_as_of`, PDF-Seite); Fedlex-Verifikation steht aus (`UNVERIFIED`). |
| Leitentscheide (8) | `PENDING_LEGAL_REVIEW` | Alle als Quellen mit Kernaussage/Fundstelle; Prüfstand «Volltext» laut Dossier, nicht systemseitig verifiziert. |
| Benötigte Informationen | `IMPLEMENTED` | 36 Fakten inkl. gemeinsam genutzter Vorprüfung; bedingte Pflicht über `required_if`; gleiche Frage nur einmal pro Fall. |
| Grenzen und Ausnahmefälle | `PARTIAL` | Als Eskalationsregeln, Prüfhinweise (REVIEW_POINT) und Aussagenfilter; nicht 1:1 abgebildete Randfälle siehe «Lücken». |
| Verfahren und Fristen | `IMPLEMENTED` | Nur als Aussage/Hinweis und Produktschwelle; **kein berechnetes Fristende**. |
| Stellen und Behörden | `PENDING_LEGAL_REVIEW` | `authorities.yaml` (`contact_verified: false`) und `referral_network.yaml` (Signale); keine erfundenen Kontakte. |
| Eskalationsregeln | `IMPLEMENTED` | Tabelle unten. |
| Erlaubte/verbotene Aussagen | `IMPLEMENTED` | Tabellen unten; Policy-Muster in `forbidden_statements.yaml`. |
| Briefing für die Fachperson | `IMPLEMENTED` | `briefing_profile` (Gruppen, Prüfpunkte, Dokumente, Stellen) im gemeinsamen Fallbericht; Template nicht dupliziert. |
| Teamentscheide (7.11.2026) | `IMPLEMENTED` | Siehe Eskalations- und Aussagen-Tabellen; Einwilligung `consent_briefing`; G7 pro Fakt (max. 2 Nachfragen, danach UNKNOWN → Eskalation). |

### Eskalationsregeln des Dossiers

| # | Wenn (Dossier) | Route / Dringlichkeit (Dossier) | Regel-ID(s) | Status |
|---:|---|---|---|---|
| 1 | Ein zwingendes Faktum ist noch nicht erhoben | Rückfrage · – | Engine (ASK) | `IMPLEMENTED` |
| 2 | Frist läuft möglicherweise noch, nicht vollständig bezahlt | Sozialarbeiterin + Rechtsperson · sofort | `PW_FRIST_LAEUFT_NICHT_BEZAHLT` | `IMPLEMENTED` |
| 3 | Empfangsdatum oder Frist unbekannt | Sozialarbeiterin + Rechtsperson · sofort | `PW_EMPFANG_ODER_FRIST_UNBEKANNT` | `IMPLEMENTED` |
| 4 | Frist unter 30 Tagen | Rechtsperson · sofort | `PW_FRIST_UNTER_30` | `IMPLEMENTED` |
| 5 | Keine/unklare Androhung oder unklarer Betrag | Rechtsperson · sofort | `PW_ANDROHUNG_FEHLT_ODER_UNKLAR`, `PW_BETRAG_UNKLAR` | `IMPLEMENTED` |
| 6 | Familienwohnung oder Mitmieter, nicht separat zugestellt | Rechtsperson · sofort | `PW_FAMILIENWOHNUNG_NICHT_SEPARAT`, `PW_MITMIETER_NICHT_ALLE` | `IMPLEMENTED` |
| 7 | Miete wegen Mängeln zurückbehalten | Rechtsperson · sofort | `PW_MIETE_ZURUECKBEHALTEN` | `IMPLEMENTED` |
| 8 | Gegenforderung, Verrechnung gewünscht | Rechtsperson · sofort | `PW_GEGENFORDERUNG` | `IMPLEMENTED` |
| 9 | Sozialdienst zahlt direkt, Zahlung ausgeblieben | Sozialarbeiterin intern + unabhängige Rechtsperson · sofort | `PW_SOZIALDIENST_ZAHLUNG_AUSGEBLIEBEN` | `IMPLEMENTED` |
| 10 | Dritte (z. B. Sozialdienst) haben gezahlt; Vermieterschaft bestreitet die Zahlung oder schickt Geld zurück | Sozialarbeiterin + Rechtsperson · sofort | `PW_DRITTZAHLUNG_STREIT` | `IMPLEMENTED` |
| 11 | Frist möglicherweise abgelaufen, nicht bezahlt | Sozialarbeiterin + Rechtsperson · sofort | `PW_FRIST_ABGELAUFEN` | `IMPLEMENTED` |
| 12 | Kündigung bereits erhalten | Wechsel zu Issue 3 · sofort | `PW_KUENDIGUNG_ERHALTEN` | `IMPLEMENTED` |
| 13 | Ratenvereinbarung oder Gespräch vereinbart | Rechtsperson · bald | `PW_ABSPRACHE` | `IMPLEMENTED` |
| 14 | Zahlungsbefehl erhalten | Rechtsperson · sofort | `PW_ZAHLUNGSBEFEHL` | `IMPLEMENTED` |

### Erlaubte Aussagen (11)

| Aussage (Dossier, gekürzt) | Status | HINT-ID |
|---|---|---|
| Wird der ganze ausstehende Betrag innerhalb der gesetzten Frist bezahlt, darf deswegen nicht gekündigt werden. | `IMPLEMENTED` | `PW_HINT_VOLLE_ZAHLUNG` |
| Bei Wohnungen muss die Zahlungsfrist mindestens 30 Tage betragen. | `IMPLEMENTED` | `PW_HINT_30_TAGE` |
| Die Frist beginnt, wenn die Mahnung tatsächlich in Empfang genommen wird; wird ein Einschreiben nicht abgeholt… | `IMPLEMENTED` | `PW_HINT_FRISTBEGINN` |
| Am sichersten ist die Zahlung mit dem Einzahlungsschein, der der Mahnung beiliegt; Quittung aufbewahren. Bei e… | `IMPLEMENTED` | `PW_HINT_ZAHLWEG` |
| Auch kleine Restbeträge zählen. Bitte den ganzen Betrag zahlen. | `IMPLEMENTED` | `PW_HINT_RESTBETRAG` |
| Wer den Betrag für falsch hält, sollte den nach eigener Kenntnis geschuldeten Betrag fristgerecht zahlen und d… | `IMPLEMENTED` | `PW_HINT_BESTRITTEN` |
| Bei einer Familienwohnung muss auch die Mahnung beiden Ehegatten separat zugestellt werden. Ob das eingehalten… | `IMPLEMENTED` | `PW_HINT_FAMILIENWOHNUNG` |
| Wird nicht rechtzeitig bezahlt, kann mit mindestens 30 Tagen auf Ende eines Monats gekündigt werden, und eine … | `IMPLEMENTED` | `PW_HINT_FOLGE` |
| Den Mietzins wegen Mängeln zurückzubehalten oder bereits fällige Mietzinse zu hinterlegen schützt nicht vor de… | `IMPLEMENTED` | `PW_HINT_MAENGEL` |
| Die Miete kann auch der Sozialdienst oder eine andere Person bezahlen; das zählt wie eine Zahlung der Klientin… | `IMPLEMENTED` | `PW_HINT_DRITTZAHLUNG` |
| Schickt die Vermieterschaft eine Zahlung zurück, bitte sofort melden und das Datum festhalten. | `IMPLEMENTED` | `PW_HINT_RUECKUEBERWEISUNG` |

### Verbotene Aussagen (10)

Alle 10 Dossier-Punkte sind über `policies/forbidden_statements.yaml` (Muster, beim Laden und zur Laufzeit geprüft) bzw. als Systemregel (keine Fristberechnung, keine Prognose, keine Prozentzahl, kein Referenzzinssatz) umgesetzt; die konkreten Beispielsätze sind in `apps/api/tests/test_issues_2_7.py::test_forbidden_statements_from_the_dossiers_are_blocked` bzw. `test_issue01.py` getestet. Abstrakte Punkte wie «Jedes berechnete Fristende» sind durch `FB_DEADLINE_END_DATE` und Textprüfungen der KB abgedeckt.

### Lücken und offene Zulieferungen

| Punkt | Status | Anmerkung |
|---|---|---|
| Muster-Mahnung für den Upload-Test | `BLOCKED` | Optionale Zulieferung des Law-Teams steht aus. |
| Kommunale Richtlinie zur Übernahme von Mietrückständen (Sozialhilfe) | `BLOCKED` | Optionale Zulieferung steht aus. |
| Kontakt Schuldenberatung Kanton Zürich | `PENDING_LEGAL_REVIEW` | Stelle als SCHULDENBERATUNG_ZH geführt, Kontakt nicht verifiziert (laut Dossier nachzutragen). |
| Konkubinat: Partner als Mitmieter prüfen | `PARTIAL` | Über die Fragen zu Mitmietern/Familienwohnung abgedeckt; kein eigener Prüfhinweis. |

### Offene Prüfpunkte laut Dossier (☐) – juristische Bestätigung

- ☐ Erledigt: Folgen einer zu kurzen Zahlungsfrist sind umstritten (h. L. unwirksam/nichtig, Minderheit Umdeutung; BGer offen; Lehrbuch § 31, N 2968h). Im System: keine Entwarnung, trotzdem zahlen, Rechtsperson sofort  → `PENDING_LEGAL_REVIEW`
- ☐ 4A_332/2025 betrifft einen Geschäftsraum; Übertragbarkeit auf Wohnungen ist naheliegend (gleicher Art. 257d), aber im Team festhalten  → `PENDING_LEGAL_REVIEW`
- ☐ Kontakt Schuldenberatung Kanton Zürich und Zürcher Hinterlegungsstelle nachtragen  → `PENDING_LEGAL_REVIEW`
- ☐ Entschieden (7.11.2026): Überweisung spätestens 3 Arbeitstage vor Fristende (siehe Teamentscheide)  → `PENDING_LEGAL_REVIEW`
- ☐ Kündigung vor Fristablauf: Geklärt mit dem Volltext von BGer 4A_585/2010: unwirksam (E. 3.1), Ausnahme bei Zugang nach Fristablauf (E. 3.5). Details in Issue 3.  → `PENDING_LEGAL_REVIEW`
- ☐ Gutgläubige Hinterlegung: Das Lehrbuch (N 2968d, S. 928) schliesst die Kündigung aus, wenn rechtmässig «oder zumindest gutgläubig» hinterlegt wurde (Blumer, N 848; BK-Giger, Art. 257d N 26). BGE 147 III 218 E. 3.3.3 (S. 224) lässt Gutgläubigkeit nur anklingen. Die Schutzregel «nicht hinterlegen, sondern zahlen» bleibt bis zur Klärung.  → `PENDING_LEGAL_REVIEW`
- ☐ Bestätigt durch das Lehrbuch: Verweis nur auf Art. 257d OR ohne ausdrückliche Androhung genügt nicht (N 2968e, S. 929; BGE 136 III 196 E. 2.4.1); Verrechnungserklärung muss innert Frist bei der Vermieterschaft eintreffen (N 2968d, S. 928; BGer 4A_140/2014 E. 5.2); nur Mietzinse, Nebenkosten und Verzugszinse, nicht Betreibungskosten, Kaution oder Schadenersatz (N 2968c, S. 928); zu langes Zuwarten nach Fristablauf kann als Verzicht gelten (N 2968i, S. 930).  → `PENDING_LEGAL_REVIEW`
- ☐ Genaue bibliografische Angabe des Lehrbuchs (Autor:in, Titel, Auflage) ergänzen  → `PENDING_LEGAL_REVIEW`

Bereits vom Law-Team erledigt (☒): 2.

### «Was wir noch von euch brauchen» (Dossier)

- Bitte als PDF oder HTML hochladen, wie bei Issue 1:
- Optional: eine Muster-Mahnung nach Art. 257d OR aus der Praxis (für den Upload-Test)
- Optional: die kommunale Richtlinie eurer Zielgemeinde zur Übernahme von Mietrückständen durch die Sozialhilfe (soziale Seite)
- Erledigt: Alle angefragten Entscheide (inkl. BGE 119 II 147, 119 II 232, 124 III 145) und das SchKG sind im Volltext eingearbeitet. Juristisch ist Issue 2 damit vollständig belegt.
- Offene Prüfpunkte
- ☒ Volltexte aller Leitentscheide und SchKG eingearbeitet
- ☒ Rechtzeitigkeit ohne Einzahlungsschein geklärt: Eingang bei der Vermieterschaft bis Fristende massgeblich (BGE 119 II 232 E. 2); Ausnahme bei beigelegtem Einzahlungsschein (BGE 124 III 145 E. 2)
- ☐ Erledigt: Folgen einer zu kurzen Zahlungsfrist sind umstritten (h. L. unwirksam/nichtig, Minderheit Umdeutung; BGer offen; Lehrbuch § 31, N 2968h). Im System: keine Entwarnung, trotzdem zahlen, Rechtsperson sofort
- ☐ 4A_332/2025 betrifft einen Geschäftsraum; Übertragbarkeit auf Wohnungen ist naheliegend (gleicher Art. 257d), aber im Team festhalten
- ☐ Kontakt Schuldenberatung Kanton Zürich und Zürcher Hinterlegungsstelle nachtragen
- ☐ Entschieden (7.11.2026): Überweisung spätestens 3 Arbeitstage vor Fristende (siehe Teamentscheide)
- Neu aus dem Lehrbuch (§ 31 Miete, eure Datei) – zu klären:
- ☐ Kündigung vor Fristablauf: Geklärt mit dem Volltext von BGer 4A_585/2010: unwirksam (E. 3.1), Ausnahme bei Zugang nach Fristablauf (E. 3.5). Details in Issue 3.
- ☐ Gutgläubige Hinterlegung: Das Lehrbuch (N 2968d, S. 928) schliesst die Kündigung aus, wenn rechtmässig «oder zumindest gutgläubig» hinterlegt wurde (Blumer, N 848; BK-Giger, Art. 257d N 26). BGE 147 III 218 E. 3.3.3 (S. 224) lässt Gutgläubigkeit nur anklingen. Die Schutzregel «nicht hinterlegen, sondern zahlen» bleibt bis zur Klärung.
- ☐ Bestätigt durch das Lehrbuch: Verweis nur auf Art. 257d OR ohne ausdrückliche Androhung genügt nicht (N 2968e, S. 929; BGE 136 III 196 E. 2.4.1); Verrechnungserklärung muss innert Frist bei der Vermieterschaft eintreffen (N 2968d, S. 928; BGer 4A_140/2014 E. 5.2); nur Mietzinse, Nebenkosten und Verzugszinse, nicht Betreibungskosten, Kaution oder Schadenersatz (N 2968c, S. 928); zu langes Zuwarten nach Fristablauf kann als Verzicht gelten (N 2968i, S. 930).
- ☐ Genaue bibliografische Angabe des Lehrbuchs (Autor:in, Titel, Auflage) ergänzen
- Quellen
- Gesetz: OR_admin.pdf (SR 220, Stand 1.10.2026), ZPO.pdf (SR 272, Stand 1.7.2026), SCHKG.pdf (SR 281.1, Stand 1.1.2026)
- Volltexte (eure Dateien): BGE 119 II 147, 119 II 232, 120 II 31, 124 III 145, 140 III 491, 140 III 591, 143 III 15, 147 III 218; Urteil 4A_120/2014 (= BGE 140 III 244); Urteil 4A_332/2025 vom 29.10.2025; Urteil 4A_68/2014 vom 16.6.2014 (vollständiges Urteil zu BGE 140 III 315)
- Kantonale Entscheide: Mietgericht Zürich, ZMP 2018 Nr. 1, Obergericht ZH LF250009
- Sekundärquelle: law.ch zu 4A_333/2022
- Stellen: Heilsarmee Sozialberatung Zürich, Rechtsberatung 07/2026, Obergericht ZH, Rechtsauskunft

## Issue 3 – Kündigung wegen Zahlungsverzug (`CH_TENANCY_PAYMENT_DEFAULT`)

### Elemente

| Dossier-Element | Status | Umsetzung |
|---|---|---|
| Gesetzesartikel (18) | `IMPLEMENTED` | Alle als Quellen in `sources.yaml` (Wortlaut `text_de`, `valid_as_of`, PDF-Seite); Fedlex-Verifikation steht aus (`UNVERIFIED`). |
| Leitentscheide (8) | `PENDING_LEGAL_REVIEW` | Alle als Quellen mit Kernaussage/Fundstelle; Prüfstand «Volltext» laut Dossier, nicht systemseitig verifiziert. |
| Benötigte Informationen | `IMPLEMENTED` | 44 Fakten inkl. gemeinsam genutzter Vorprüfung; bedingte Pflicht über `required_if`; gleiche Frage nur einmal pro Fall. |
| Grenzen und Ausnahmefälle | `IMPLEMENTED` | Als Eskalationsregeln, Prüfhinweise (REVIEW_POINT) und Aussagenfilter; nicht 1:1 abgebildete Randfälle siehe «Lücken». |
| Verfahren und Fristen | `IMPLEMENTED` | Nur als Aussage/Hinweis und Produktschwelle; **kein berechnetes Fristende**. |
| Stellen und Behörden | `PENDING_LEGAL_REVIEW` | `authorities.yaml` (`contact_verified: false`) und `referral_network.yaml` (Signale); keine erfundenen Kontakte. |
| Eskalationsregeln | `IMPLEMENTED` | Tabelle unten. |
| Erlaubte/verbotene Aussagen | `IMPLEMENTED` | Tabellen unten; Policy-Muster in `forbidden_statements.yaml`. |
| Briefing für die Fachperson | `IMPLEMENTED` | `briefing_profile` (Gruppen, Prüfpunkte, Dokumente, Stellen) im gemeinsamen Fallbericht; Template nicht dupliziert. |
| Teamentscheide (7.11.2026) | `IMPLEMENTED` | Siehe Eskalations- und Aussagen-Tabellen; Einwilligung `consent_briefing`; G7 pro Fakt (max. 2 Nachfragen, danach UNKNOWN → Eskalation). |

### Eskalationsregeln des Dossiers

| # | Wenn (Dossier) | Route / Dringlichkeit (Dossier) | Regel-ID(s) | Status |
|---:|---|---|---|---|
| 1 | Jede Kündigung wegen Zahlungsverzug (Grundregel) | Rechtsperson + Sozialarbeiterin · sofort | `PD_GRUNDREGEL` | `IMPLEMENTED` |
| 2 | Zwingendes Faktum fehlt | Rückfrage, parallel Grundregel · sofort | `PD_GRUNDREGEL`; Engine (ASK) | `IMPLEMENTED` |
| 3 | Empfangsdatum der Kündigung unbekannt oder ≥ 20 Tage | Rechtsperson · sofort, höchste Priorität | `PD_EMPFANG_UNBEKANNT_ODER_GE20` | `IMPLEMENTED` |
| 4 | Keine Mahnung, Mahnung fehlerhaft, zu kurze Frist | Rechtsperson · sofort | `PD_PRUEFFRAGE1_MAHNUNG` | `IMPLEMENTED` |
| 5 | Angabe «innert Frist bezahlt» oder Teilzahlung mit Hinweis | Rechtsperson · sofort | `PD_PRUEFFRAGE2_ZAHLUNG` | `IMPLEMENTED` |
| 6 | Kündigung vor Fristablauf, kein Formular, Familienwohnung/Mitmieter nicht separat | Rechtsperson · sofort | `PD_PRUEFFRAGE3_FORM` | `IMPLEMENTED` |
| 7 | Gesuch ans Gericht, Vorladung, Räumungstermin | Wechsel zu Issue 6 · sofort | `PD_GERICHT` | `IMPLEMENTED` |
| 8 | Vermieterschaft räumt selbst oder sperrt aus | Rechtsperson (ggf. Polizei) + Sozialarbeiterin · sofort | `PD_SELBSTHILFE` | `IMPLEMENTED` |
| 9 | Sozialdienst zahlt direkt | Unabhängige Rechtsperson · sofort | `PD_SOZIALDIENST_ZAHLT` | `IMPLEMENTED` |
| 10 | Kinder, Gesundheit, keine Anschlusslösung | Sozialarbeiterin · sofort | `PD_KEINE_ANSCHLUSSLOESUNG` | `IMPLEMENTED` |

### Erlaubte Aussagen (8)

| Aussage (Dossier, gekürzt) | Status | HINT-ID |
|---|---|---|
| Eine Kündigung kann innert 30 Tagen nach Empfang bei der Schlichtungsbehörde angefochten werden; das Verfahren… | `IMPLEMENTED` | `PD_HINT_ANFECHTUNG` |
| Bei einer Kündigung wegen Zahlungsverzug ist eine Erstreckung ausgeschlossen. Die Suche nach einer Unterkunft … | `IMPLEMENTED` | `PD_HINT_KEINE_ERSTRECKUNG` |
| Eine solche Kündigung setzt eine gültige schriftliche Mahnung mit Frist und ausdrücklicher Kündigungsandrohung… | `IMPLEMENTED` | `PD_HINT_MAHNUNG` |
| Wurde der ganze Betrag rechtzeitig bezahlt, kann die Kündigung unwirksam sein. Bitte alle Belege mit Datum sic… | `IMPLEMENTED` | `PD_HINT_RECHTZEITIG` |
| Eine Zahlung nach Fristablauf macht die Kündigung nicht automatisch unwirksam, auch wenn die Vermieterschaft d… | `IMPLEMENTED` | `PD_HINT_NACH_FRIST` |
| Auch bei einer Kündigung muss die Vermieterschaft das amtliche Formular verwenden und bei einer Familienwohnun… | `IMPLEMENTED` | `PD_HINT_FORM` |
| Die Vermieterschaft darf die Wohnung nicht selbst räumen; dafür braucht es einen Entscheid einer Behörde oder … | `IMPLEMENTED` | `PD_HINT_SELBSTHILFE` |
| Eine Anfechtung schützt nicht sicher vor einem schnellen Ausweisungsverfahren. | `IMPLEMENTED` | `PD_HINT_ANFECHTUNG_SCHUETZT_NICHT` |

### Verbotene Aussagen (7)

Alle 7 Dossier-Punkte sind über `policies/forbidden_statements.yaml` (Muster, beim Laden und zur Laufzeit geprüft) bzw. als Systemregel (keine Fristberechnung, keine Prognose, keine Prozentzahl, kein Referenzzinssatz) umgesetzt; die konkreten Beispielsätze sind in `apps/api/tests/test_issues_2_7.py::test_forbidden_statements_from_the_dossiers_are_blocked` bzw. `test_issue01.py` getestet. Abstrakte Punkte wie «Jedes berechnete Fristende» sind durch `FB_DEADLINE_END_DATE` und Textprüfungen der KB abgedeckt.

### Lücken und offene Zulieferungen

| Punkt | Status | Anmerkung |
|---|---|---|
| BGE 127 III 548 / BGE 121 III 156 (optionale Volltexte) | `BLOCKED` | Optionale Zulieferung des Law-Teams steht aus. |
| Muster-Kündigungsformular des Kantons Zürich (Upload-Test) | `BLOCKED` | Optionale Zulieferung steht aus. |
| Anfechtungsempfehlung | `NOT_APPLICABLE` | Teamentscheid: Das System empfiehlt nie selbst, der Entscheid bleibt bei der Rechtsperson. |

### Offene Prüfpunkte laut Dossier (☐) – juristische Bestätigung

- ☐ Geklärt: Wartezeit nach Fristablauf. Keine feste Grenze; knapp drei Wochen «wohl an der Grenze», länger kann Verzicht bedeuten (BGer 4A_366/2008 E. 4). Produktentscheid vorgeschlagen: ab 14 Tagen zwischen Fristablauf und Kündigung Prüfhinweis an die Fachperson, ohne Entwarnung. Optional noch 4C.430/2004 E. 3.1 lesen  → `PENDING_LEGAL_REVIEW`
- ☐ Kontakt Schuldenberatung Kanton Zürich nachtragen  → `PENDING_LEGAL_REVIEW`

Bereits vom Law-Team erledigt (☒): 3.

### «Was wir noch von euch brauchen» (Dossier)

- Optional: BGE 127 III 548 – Schadenersatz der Mieterin nach Zahlungsverzugskündigung (für das Briefing).
- Optional: BGE 121 III 156 – Grundlage für «verfrühte Kündigung unwirksam» (in 4A_585/2010 zitiert).
- Die bibliografische Angabe des Lehrbuchs (Autor:in, Titel, Auflage).
- Optional: ein Muster-Kündigungsformular des Kantons Zürich (für den Upload-Test).
- Erledigt: BGE 141 III 262, BGE 135 III 441 und BGer 4A_585/2010 sind im Volltext eingearbeitet.
- Offene Prüfpunkte
- ☒ Widerspruch geklärt: Kündigung vor Fristablauf ist nach neuerer Praxis unwirksam (4A_585/2010 E. 3.1), Ausnahme bei Zugang nach Fristablauf (E. 3.5); BGE 119 II 147 E. 4 ist insoweit überholt bzw. als ältere Praxis zu kennzeichnen
- ☐ Geklärt: Wartezeit nach Fristablauf. Keine feste Grenze; knapp drei Wochen «wohl an der Grenze», länger kann Verzicht bedeuten (BGer 4A_366/2008 E. 4). Produktentscheid vorgeschlagen: ab 14 Tagen zwischen Fristablauf und Kündigung Prüfhinweis an die Fachperson, ohne Entwarnung. Optional noch 4C.430/2004 E. 3.1 lesen
- ☒ Produktentscheid: Soll das System bei Issue 3 jede Kündigung zur Anfechtung empfehlen oder nur bei erkennbarem Mangel? (Empfehlung: Entscheid immer der Fachperson überlassen, Frist aber als «sofort» markieren)
- ☒ BGE 141 III 262 und 4A_585/2010 betrafen eher Geschäftsräume; Übertragbarkeit auf Wohnungen im Team festhalten (gleiche Normen)
- ☐ Kontakt Schuldenberatung Kanton Zürich nachtragen
- Quellen
- Gesetz: OR_admin.pdf (SR 220, Stand 1.10.2026), ZPO.pdf (SR 272, Stand 1.7.2026)
- Volltexte (eure Dateien): BGE 119 II 147, 119 II 232, 120 II 31, 124 III 145, 135 III 441, 140 III 491, 140 III 591, 141 III 262, 143 III 15, 147 III 218; Urteile 4A_120/2014 (= BGE 140 III 244), 4A_332/2025, 4A_585/2010, 4A_366/2008
- Lehrbuch: euer Auszug «§ 31 Miete (Art. 253–273c OR) und Pacht», N 2968e–2968k (S. 929–931), N 3005e (S. 961), N 3006 (S. 961), N 3009a (S. 964), N 3010a (S. 965), N 3024c (S. 988), N 3025d–3025f (S. 991–993)
- Online: Obergericht ZH LF250009, Obergericht ZH, Schlichtungsbehörden, Heilsarmee Sozialberatung Zürich, Rechtsberatung 07/2026

## Issue 4 – Erstreckung des Mietverhältnisses (`CH_TENANCY_EXTENSION`)

### Elemente

| Dossier-Element | Status | Umsetzung |
|---|---|---|
| Gesetzesartikel (17) | `IMPLEMENTED` | Alle als Quellen in `sources.yaml` (Wortlaut `text_de`, `valid_as_of`, PDF-Seite); Fedlex-Verifikation steht aus (`UNVERIFIED`). |
| Leitentscheide (15) | `PENDING_LEGAL_REVIEW` | Alle als Quellen mit Kernaussage/Fundstelle; Prüfstand «Volltext» laut Dossier, nicht systemseitig verifiziert. |
| Benötigte Informationen | `IMPLEMENTED` | 37 Fakten inkl. gemeinsam genutzter Vorprüfung; bedingte Pflicht über `required_if`; gleiche Frage nur einmal pro Fall. |
| Grenzen und Ausnahmefälle | `PARTIAL` | Als Eskalationsregeln, Prüfhinweise (REVIEW_POINT) und Aussagenfilter; nicht 1:1 abgebildete Randfälle siehe «Lücken». |
| Verfahren und Fristen | `IMPLEMENTED` | Nur als Aussage/Hinweis und Produktschwelle; **kein berechnetes Fristende**. |
| Stellen und Behörden | `PENDING_LEGAL_REVIEW` | `authorities.yaml` (`contact_verified: false`) und `referral_network.yaml` (Signale); keine erfundenen Kontakte. |
| Eskalationsregeln | `IMPLEMENTED` | Tabelle unten. |
| Erlaubte/verbotene Aussagen | `IMPLEMENTED` | Tabellen unten; Policy-Muster in `forbidden_statements.yaml`. |
| Briefing für die Fachperson | `IMPLEMENTED` | `briefing_profile` (Gruppen, Prüfpunkte, Dokumente, Stellen) im gemeinsamen Fallbericht; Template nicht dupliziert. |
| Teamentscheide (7.11.2026) | `IMPLEMENTED` | Siehe Eskalations- und Aussagen-Tabellen; Einwilligung `consent_briefing`; G7 pro Fakt (max. 2 Nachfragen, danach UNKNOWN → Eskalation). |

### Eskalationsregeln des Dossiers

| # | Wenn (Dossier) | Route / Dringlichkeit (Dossier) | Regel-ID(s) | Status |
|---:|---|---|---|---|
| 1 | Ausschlussgrund (Zahlungsverzug, Pflichtverletzung, Konkurs) | Wechsel zu Issue 3 bzw. Rechtsperson · sofort | `EX_ZAHLUNGSVERZUG`, `EX_AUSSCHLUSS_ANDERE` | `IMPLEMENTED` |
| 2 | Unbefristet: Empfang unbekannt oder ≥ 20 Tage seit Empfang | Rechtsperson · sofort | `EX_UNBEFRISTET_FRIST` | `IMPLEMENTED` |
| 3 | Befristet: weniger als 75 Tage bis Vertragsende oder Ende unbekannt | Rechtsperson · sofort | `EX_BEFRISTET_FRIST` | `IMPLEMENTED` |
| 4 | Zweite Erstreckung: weniger als 75 Tage bis Ende der ersten | Rechtsperson · sofort | `EX_ZWEITERSTRECKUNG` | `IMPLEMENTED` |
| 5 | Frist möglicherweise verpasst | Rechtsperson + Sozialarbeiterin · sofort | `EX_FRIST_VERPASST` | `IMPLEMENTED` |
| 6 | Fristen gewahrt, Härtegründe vorhanden | Rechtsperson + Sozialarbeiterin · bald | `EX_HAERTEGRUENDE` | `IMPLEMENTED` |
| 7 | Vermieterschaft bietet Ersatzwohnung oder Vergleich mit Verzicht an | Rechtsperson · sofort | `EX_ERSATZ_ODER_VERGLEICH` | `IMPLEMENTED` |
| 8 | Keine Suchbemühungen bisher | Sozialarbeiterin · bald | `EX_KEINE_SUCHE` | `IMPLEMENTED` |
| 9 | Konkubinat, Untermiete, Familienwohnung | Rechtsperson · bald | `EX_SONDERFRAGEN` | `IMPLEMENTED` |

### Erlaubte Aussagen (9)

| Aussage (Dossier, gekürzt) | Status | HINT-ID |
|---|---|---|
| Wenn der Auszug für die Klientin oder ihre Familie eine besondere Härte bedeutet, kann sie eine Erstreckung de… | `IMPLEMENTED` | `EX_HINT_ANSPRUCH` |
| Bei einem unbefristeten Vertrag muss das Begehren innert 30 Tagen nach Empfang der Kündigung bei der Schlichtu… | `IMPLEMENTED` | `EX_HINT_FRIST` |
| Berücksichtigt werden unter anderem die Dauer des Mietverhältnisses, die persönlichen, familiären und finanzie… | `IMPLEMENTED` | `EX_HINT_ABWAEGUNG` |
| Bei Wohnungen kann um insgesamt höchstens vier Jahre erstreckt werden. Wie lange, entscheidet die Behörde im E… | `IMPLEMENTED` | `EX_HINT_DAUER` |
| Die Klientin sollte sofort mit der Wohnungssuche beginnen und alles dokumentieren (Bewerbungen, Absagen). Das … | `IMPLEMENTED` | `EX_HINT_SUCHE` |
| Die Umzugsmühe allein reicht nicht; entscheidend sind konkrete Umstände wie Kinder, Gesundheit, Alter oder fin… | `IMPLEMENTED` | `EX_HINT_UMZUGSMUEHE` |
| Während des Verfahrens muss die Klientin die Wohnung nicht verlassen. | `IMPLEMENTED` | `EX_HINT_VERFAHREN` |
| Findet die Klientin während der Erstreckung eine Wohnung, kann sie mit verkürzter Frist kündigen. | `IMPLEMENTED` | `EX_HINT_NEUE_WOHNUNG` |
| Das Verfahren vor der Schlichtungsbehörde kostet keine Gerichtskosten. | `IMPLEMENTED` | `EX_HINT_KOSTEN` |

### Verbotene Aussagen (9)

Alle 9 Dossier-Punkte sind über `policies/forbidden_statements.yaml` (Muster, beim Laden und zur Laufzeit geprüft) bzw. als Systemregel (keine Fristberechnung, keine Prognose, keine Prozentzahl, kein Referenzzinssatz) umgesetzt; die konkreten Beispielsätze sind in `apps/api/tests/test_issues_2_7.py::test_forbidden_statements_from_the_dossiers_are_blocked` bzw. `test_issue01.py` getestet. Abstrakte Punkte wie «Jedes berechnete Fristende» sind durch `FB_DEADLINE_END_DATE` und Textprüfungen der KB abgedeckt.

### Lücken und offene Zulieferungen

| Punkt | Status | Anmerkung |
|---|---|---|
| Zürcher Entscheide zu Erstreckung bei Wohnungen mit Kindern | `BLOCKED` | Empfohlene Zulieferung des Law-Teams steht aus (BGE-Dauer-Entscheide betreffen Geschäftsräume). |
| Zürcher Wohnhilfe-/Wohnungssuche-Stellen | `PENDING_LEGAL_REVIEW` | WOHNHILFE_ZH als Platzhalter ohne Kontakt. |
| Konkubinat als Härtegrund | `PARTIAL` | Nur als Faktum erfasst (Teamentscheid); Bewertung durch die Rechtsperson. |

### Offene Prüfpunkte laut Dossier (☐) – juristische Bestätigung

- ☐ Produktschwelle für befristete Verträge festlegen (Vorschlag: 75 Tage vor Ablauf = sofort)  → `PENDING_LEGAL_REVIEW`
- ☐ Konkubinat: Soll das System Lebenspartner als Härtegrund erfassen? Volltextlage: BGE 105 II 197 E. 3c verneint «Familie» (altes Recht); 4A_673/2014 betrifft nur die Vermieterseite. Vorschlag: Faktum erfassen, Bewertung der Rechtsperson überlassen  → `PENDING_LEGAL_REVIEW`
- ☐ Zürcher Wohnhilfe- bzw. Wohnungssuche-Stellen ergänzen  → `PENDING_LEGAL_REVIEW`

Bereits vom Law-Team erledigt (☒): 1.

### «Was wir noch von euch brauchen» (Dossier)

- Erledigt: BGE 142 III 336, 135 III 121, 117 II 415, 105 II 197, BGer 4A_72/2011, 4A_673/2014 (Volltexte eingearbeitet).
- Empfohlen: ein bis zwei Entscheide des Mietgerichts oder Obergerichts Zürich zur Erstreckung bei Wohnungen mit Kindern oder gesundheitlichen Problemen (entscheidsuche.ch, Suchbegriffe «Erstreckung», «Kinder», «Suchbemühungen», Filter ZH). Grund: Die Bundesgerichtsentscheide zur Dauer betreffen fast alle Geschäftsräume.
- Optional: BGE 110 II 249 und 116 II 446 (Suchbemühungen schon bei der ersten Erstreckung, direkt am Leitentscheid).
- Bibliografische Angabe des Lehrbuchs (Autor:in, Titel, Auflage).
- Offene Prüfpunkte
- ☒ Kernaussagen der Lehrbuch-Zitate am Volltext bestätigt (BGE 142 III 336, 135 III 121, 117 II 415, 105 II 197, 4A_72/2011, 4A_673/2014)
- ☐ Produktschwelle für befristete Verträge festlegen (Vorschlag: 75 Tage vor Ablauf = sofort)
- ☐ Konkubinat: Soll das System Lebenspartner als Härtegrund erfassen? Volltextlage: BGE 105 II 197 E. 3c verneint «Familie» (altes Recht); 4A_673/2014 betrifft nur die Vermieterseite. Vorschlag: Faktum erfassen, Bewertung der Rechtsperson überlassen
- ☐ Zürcher Wohnhilfe- bzw. Wohnungssuche-Stellen ergänzen
- Quellen
- Gesetz: OR_admin.pdf (SR 220, Stand 1.10.2026), Art. 272–273c OR (S. 82–84); ZPO.pdf (SR 272, Stand 1.7.2026)
- Lehrbuch: euer Auszug «§ 31 Miete», N 3023b–3024g (S. 986–989)
- Volltexte (eure Dateien): BGE 105 II 197, 117 II 415, 135 III 121, 135 III 441, 139 III 7, 140 III 244 (Urteil 4A_120/2014), 142 III 91, 142 III 336, 143 III 15, 151 III 481; BGer 4A_72/2011, 4A_673/2014
- Stellen: Obergericht ZH, Schlichtungsbehörden, Formular Kündigungsschutz, Heilsarmee Sozialberatung Zürich, Rechtsberatung 07/2026

## Issue 5 – Mängel an der Mietsache (`CH_TENANCY_DEFECTS`)

### Elemente

| Dossier-Element | Status | Umsetzung |
|---|---|---|
| Gesetzesartikel (21) | `IMPLEMENTED` | Alle als Quellen in `sources.yaml` (Wortlaut `text_de`, `valid_as_of`, PDF-Seite); Fedlex-Verifikation steht aus (`UNVERIFIED`). |
| Leitentscheide (8) | `PENDING_LEGAL_REVIEW` | Alle als Quellen mit Kernaussage/Fundstelle; Prüfstand «Volltext» laut Dossier, nicht systemseitig verifiziert. |
| Benötigte Informationen | `IMPLEMENTED` | 43 Fakten inkl. gemeinsam genutzter Vorprüfung; bedingte Pflicht über `required_if`; gleiche Frage nur einmal pro Fall. |
| Grenzen und Ausnahmefälle | `IMPLEMENTED` | Als Eskalationsregeln, Prüfhinweise (REVIEW_POINT) und Aussagenfilter; nicht 1:1 abgebildete Randfälle siehe «Lücken». |
| Verfahren und Fristen | `IMPLEMENTED` | Nur als Aussage/Hinweis und Produktschwelle; **kein berechnetes Fristende**. |
| Stellen und Behörden | `PENDING_LEGAL_REVIEW` | `authorities.yaml` (`contact_verified: false`) und `referral_network.yaml` (Signale); keine erfundenen Kontakte. |
| Eskalationsregeln | `IMPLEMENTED` | Tabelle unten. |
| Erlaubte/verbotene Aussagen | `IMPLEMENTED` | Tabellen unten; Policy-Muster in `forbidden_statements.yaml`. |
| Briefing für die Fachperson | `IMPLEMENTED` | `briefing_profile` (Gruppen, Prüfpunkte, Dokumente, Stellen) im gemeinsamen Fallbericht; Template nicht dupliziert. |
| Teamentscheide (7.11.2026) | `IMPLEMENTED` | Siehe Eskalations- und Aussagen-Tabellen; Einwilligung `consent_briefing`; G7 pro Fakt (max. 2 Nachfragen, danach UNKNOWN → Eskalation). |

### Eskalationsregeln des Dossiers

| # | Wenn (Dossier) | Route / Dringlichkeit (Dossier) | Regel-ID(s) | Status |
|---:|---|---|---|---|
| 1 | Zahlungsaufforderung mit Kündigungsandrohung vorhanden | RECHT (Wechsel zu Issue 2) · SOFORT | `DF_ZAHLUNGSAUFFORDERUNG` | `IMPLEMENTED` |
| 2 | Klientin hat Miete gekürzt, verrechnet oder zurückbehalten | RECHT · BALD | `DF_MIETE_GEKUERZT` | `IMPLEMENTED` |
| 3 | Hinterlegung läuft oder ist erfolgt | RECHT · SOFORT | `DF_HINTERLEGUNG_LAEUFT` | `IMPLEMENTED` |
| 4 | Klientin will hinterlegen | RECHT · BALD | `DF_HINTERLEGUNG_GEPLANT` | `IMPLEMENTED` |
| 5 | Gefahr für Gesundheit oder Sicherheit, Wohnung unbewohnbar | RECHT + SOZIAL · SOFORT | `DF_GESUNDHEIT_GEFAHR`, `DF_H1_BESCHWERDEN`, `DF_H2_GROSSER_BEFALL`, `DF_H3_NICHT_MEIDBAR`, `DF_H4_KEINE_ZWISCHENUNTERKUNFT`, `DF_H5_GEMEINDE_ZUWEISUNG`, `DF_H7_GESUNDHEIT_UNBEKANNT` | `IMPLEMENTED` |
| 6 | Klientin will wegen des Mangels ausziehen oder fristlos kündigen | RECHT · BALD | `DF_AUSZIEHEN` | `IMPLEMENTED` |
| 7 | Kündigung oder Drohung nach Mängelmeldung | RECHT (Wechsel zu Issue 1) · SOFORT | `DF_KUENDIGUNG_NACH_MELDUNG` | `IMPLEMENTED` |
| 8 | Schaden an Sachen oder Zusatzkosten | RECHT · NORMAL | `DF_SCHADEN` | `IMPLEMENTED` |
| 9 | Klientin will selbst reparieren lassen | RECHT · NORMAL | `DF_SELBST_REPARIEREN` | `IMPLEMENTED` |
| 10 | Brief oder Entscheid der Schlichtungsbehörde oder des Gerichts | RECHT · SOFORT | `DF_BEHOERDENBRIEF` | `IMPLEMENTED` |
| 11 | Ursache unklar oder Klientin könnte verantwortlich sein | RECHT · NORMAL | `DF_URSACHE_UNKLAR` | `IMPLEMENTED` |
| 12 | Mangel gemeldet, keine Kürzung, keine Gefahr, Vermieterschaft hat noch Zeit | KI_WEITER · NORMAL | Engine (PROCEED) | `IMPLEMENTED` |
| 13 | Vermieterschaft reagiert nach der Produktschwelle nicht | RECHT · NORMAL | `DF_KEINE_REAKTION_30` | `IMPLEMENTED` |

Zusätzlich H6 als Prüfhinweis `DF_REVIEW_SUBVENTIONIERT` (kein Routing, nur Hinweis auf Issue 7).

### Erlaubte Aussagen (11)

| Aussage (Dossier, gekürzt) | Status | HINT-ID |
|---|---|---|
| Wenn jemand gesundheitliche Beschwerden hat, sollte das ärztlich abgeklärt werden. Besonders gefährdete Person… | `IMPLEMENTED` | `DF_HINT_ARZT` |
| Räume mit starkem Schimmelbefall nach Möglichkeit geschlossen halten und nicht benutzen, besonders Schlaf- und… | `IMPLEMENTED` | `DF_HINT_RAEUME_MEIDEN` |
| Abklärung und Sanierung sind Sache der Vermieterschaft. Eigene Gutachten oder Luftmessungen sind in der Regel … | `IMPLEMENTED` | `DF_HINT_SANIERUNG` |
| Die Vermieterschaft muss die Wohnung in einem gebrauchstauglichen Zustand erhalten. | `IMPLEMENTED` | `DF_HINT_PFLICHT` |
| Melden Sie den Mangel schriftlich, am besten eingeschrieben, und verlangen Sie die Behebung. Eine Herabsetzung… | `IMPLEMENTED` | `DF_HINT_MELDEN` |
| Bezahlen Sie die volle Miete weiter, bis eine Fachperson den Fall geprüft hat. Wer die Miete selbst kürzt, zur… | `IMPLEMENTED` | `DF_HINT_VOLLE_MIETE` |
| Sammeln Sie Belege: Fotos mit Datum, Briefe, E-Mails, Namen von Zeugen. | `IMPLEMENTED` | `DF_HINT_BELEGE` |
| Kleine Reparaturen und Reinigungen, etwa eine Glühbirne oder ein verstopfter Abfluss, muss die Mieterin selbst… | `IMPLEMENTED` | `DF_HINT_KLEINER_UNTERHALT` |
| Handwerkern für die Behebung müssen Sie Zutritt gewähren; die Arbeiten müssen rechtzeitig angekündigt werden. | `IMPLEMENTED` | `DF_HINT_ZUTRITT` |
| Das Verfahren vor der Schlichtungsbehörde kostet keine Gerichtskosten. Dort gibt es auch eine kostenlose Recht… | `IMPLEMENTED` | `DF_HINT_KOSTENLOS` |
| Wer wegen einer Mängelmeldung gekündigt wird, kann die Kündigung möglicherweise anfechten. Bringen Sie eine so… | `IMPLEMENTED` | `DF_HINT_RACHEKUENDIGUNG` |

### Verbotene Aussagen (12)

Alle 12 Dossier-Punkte sind über `policies/forbidden_statements.yaml` (Muster, beim Laden und zur Laufzeit geprüft) bzw. als Systemregel (keine Fristberechnung, keine Prognose, keine Prozentzahl, kein Referenzzinssatz) umgesetzt; die konkreten Beispielsätze sind in `apps/api/tests/test_issues_2_7.py::test_forbidden_statements_from_the_dossiers_are_blocked` bzw. `test_issue01.py` getestet. Abstrakte Punkte wie «Jedes berechnete Fristende» sind durch `FB_DEADLINE_END_DATE` und Textprüfungen der KB abgedeckt.

### Lücken und offene Zulieferungen

| Punkt | Status | Anmerkung |
|---|---|---|
| Musterbrief «Mängelmeldung» ausfüllen | `BLOCKED` | Teamentscheid erlaubt das Ausfüllen (ohne Prozentzahl, ohne Hinterlegungsandrohung); die Brief-Erzeugung ist noch nicht gebaut. |
| Stichwortliste «Gefahr» für das Keyword-Netz | `PARTIAL` | Globale Safety-Erkennung besteht; Mängel-spezifische Stichwörter (Gas, Strom, Einsturz) sind über das Faktum health_safety_danger abgedeckt, nicht über ein eigenes Netz. |
| Gesundheitsbehörde / kommunale Stelle bei Schimmel | `PENDING_LEGAL_REVIEW` | Nur AWEL als allgemeine Auskunft; kommunale Eingriffsstelle ist im Dossier offen. |
| Planungs- und Baugesetz ZH (PBG) | `BLOCKED` | Optional laut Dossier, nicht geliefert. |

### Offene Prüfpunkte laut Dossier (☐) – juristische Bestätigung

- ☐ Produktschwelle festlegen: Nach wie vielen Tagen ohne Reaktion eskaliert das System (Vorschlag 30 Tage; bei schweren Mängeln sofort)? Hinweis: In 4C.264/2003 E. 3.2.2 galten fünf Monate für eine Parkettreparatur noch als angemessen  → `PENDING_LEGAL_REVIEW`
- ☐ Soll das System den Musterbrief «Mängelmeldung» selbst ausfüllen dürfen? Mein Vorschlag: ja, mit Verlangen der Behebung (wichtig für die Rückwirkung nach BGE 142 III 557 E. 8.3.4), aber ohne Prozentzahl und ohne Hinterlegungsandrohung  → `PENDING_LEGAL_REVIEW`
- ☐ Liste der «Gefahr»-Stichworte für das Keyword-Netz (Schimmel und Kleinkind, Gas, Strom, keine Heizung, kein Wasser, Einsturz)  → `PENDING_LEGAL_REVIEW`
- ☐ Kontakte ergänzen (Schlichtungsbehörden nach Bezirk, Mieterverband, Gesundheitsbehörde)  → `PENDING_LEGAL_REVIEW`

Bereits vom Law-Team erledigt (☒): 1.

### «Was wir noch von euch brauchen» (Dossier)

- Erledigt: Volltexte der acht Leitentscheide und § 66 GOG ZH (eingearbeitet).
- Optional: BGer 4A_565/2009, 4A_368/2007, 4A_739/2011 (Hinterlegung) und 4A_472/2008 (Verrechnung ausgeschlossen, wo Hinterlegung möglich; zitiert in 4A_140/2014 E. 5.2).
- Empfohlen für die Demo: zwei bis drei Zürcher Entscheide zu typischen Wohnungsmängeln (Schimmel, Heizung, Baulärm), z. B. aus der «Zürcher Mietrechtspraxis» oder über entscheidsuche.ch. Grund: BGE 130 III 504 und 4A_140/2014 betreffen Geschäftsräume.
- Bibliografische Angabe des Lehrbuchs.
- Für Abschnitt 3a: falls die Gemeinde die App betreibt: IDG ZH (LS 170.4); optional: Planungs- und Baugesetz ZH (PBG, LS 700.1), falls ihr die im ZUP-Artikel genannte Pflicht der Eigentümerschaft belegen wollt (die genaue Bestimmung nennt der Artikel nicht); Kontakt Notunterkunft erledigt. Erledigt: BV, DSG, BGE 120 Ia 1, 131 I 166, 136 I 290, CESCR General Comment No. 4.
- Offene Prüfpunkte
- ☒ Kernaussagen der Lehrbuch-Zitate am Volltext bestätigt (mit zwei Abweichungen: 4C.264/2006 falsch zitiert; N 2956b gibt 4A_140/2014 E. 5.4 umgekehrt wieder)
- ☐ Produktschwelle festlegen: Nach wie vielen Tagen ohne Reaktion eskaliert das System (Vorschlag 30 Tage; bei schweren Mängeln sofort)? Hinweis: In 4C.264/2003 E. 3.2.2 galten fünf Monate für eine Parkettreparatur noch als angemessen
- ☐ Soll das System den Musterbrief «Mängelmeldung» selbst ausfüllen dürfen? Mein Vorschlag: ja, mit Verlangen der Behebung (wichtig für die Rückwirkung nach BGE 142 III 557 E. 8.3.4), aber ohne Prozentzahl und ohne Hinterlegungsandrohung
- ☐ Liste der «Gefahr»-Stichworte für das Keyword-Netz (Schimmel und Kleinkind, Gas, Strom, keine Heizung, kein Wasser, Einsturz)
- ☐ Kontakte ergänzen (Schlichtungsbehörden nach Bezirk, Mieterverband, Gesundheitsbehörde)
- Quellen
- Gesetz: OR_admin.pdf (SR 220, Stand 1.10.2026), Art. 256–260, 257d, 271a OR (S. 67–72, 81); ZPO.pdf (SR 272, Stand 1.7.2026), Art. 113, 200, 209–211, 243 ZPO; GOG ZH (LS 211.1, Stand 1.7.2020), §§ 63, 66 (S. 13 f.)
- Lehrbuch: euer Auszug «§ 31 Miete», N 2939m–2967 (S. 911–925)
- Volltexte (eure Dateien): BGE 124 III 201, 125 III 120, 130 III 504, 135 III 345, 142 III 557; BGer 4C.97/2003, 4C.264/2003, 4A_140/2014 und 4A_250/2014. Nicht verwendbar: BGer 4C.264/2006 (Bankauftrag)
- Obergericht Zürich: Seiten «Mietzinsminderung», «Hinterlegung», «Mangel» (gerichte-zh.ch, abgerufen 7.11.2026); Formular Hinterlegungsgesuch

## Issue 6 – Ausweisung und Räumung (`CH_TENANCY_EVICTION`)

### Elemente

| Dossier-Element | Status | Umsetzung |
|---|---|---|
| Gesetzesartikel (20) | `IMPLEMENTED` | Alle als Quellen in `sources.yaml` (Wortlaut `text_de`, `valid_as_of`, PDF-Seite); Fedlex-Verifikation steht aus (`UNVERIFIED`). |
| Leitentscheide (10) | `PENDING_LEGAL_REVIEW` | Alle als Quellen mit Kernaussage/Fundstelle; Prüfstand «Volltext» laut Dossier, nicht systemseitig verifiziert. |
| Benötigte Informationen | `IMPLEMENTED` | 28 Fakten inkl. gemeinsam genutzter Vorprüfung; bedingte Pflicht über `required_if`; gleiche Frage nur einmal pro Fall. |
| Grenzen und Ausnahmefälle | `IMPLEMENTED` | Als Eskalationsregeln, Prüfhinweise (REVIEW_POINT) und Aussagenfilter; nicht 1:1 abgebildete Randfälle siehe «Lücken». |
| Verfahren und Fristen | `IMPLEMENTED` | Nur als Aussage/Hinweis und Produktschwelle; **kein berechnetes Fristende**. |
| Stellen und Behörden | `PENDING_LEGAL_REVIEW` | `authorities.yaml` (`contact_verified: false`) und `referral_network.yaml` (Signale); keine erfundenen Kontakte. |
| Eskalationsregeln | `IMPLEMENTED` | Tabelle unten. |
| Erlaubte/verbotene Aussagen | `IMPLEMENTED` | Tabellen unten; Policy-Muster in `forbidden_statements.yaml`. |
| Briefing für die Fachperson | `IMPLEMENTED` | `briefing_profile` (Gruppen, Prüfpunkte, Dokumente, Stellen) im gemeinsamen Fallbericht; Template nicht dupliziert. |
| Teamentscheide (7.11.2026) | `IMPLEMENTED` | Siehe Eskalations- und Aussagen-Tabellen; Einwilligung `consent_briefing`; G7 pro Fakt (max. 2 Nachfragen, danach UNKNOWN → Eskalation); Issue 6 ohne Rückfrage-Runden. |

### Eskalationsregeln des Dossiers

| # | Wenn (Dossier) | Route / Dringlichkeit (Dossier) | Regel-ID(s) | Status |
|---:|---|---|---|---|
| 1 | Jedes Schreiben eines Gerichts oder Ammannamts zur Ausweisung | RECHT + SOZIAL · SOFORT | `EV_GRUNDREGEL` | `IMPLEMENTED` |
| 2 | Räumungstermin steht oder Räumung findet statt | SOZIAL + RECHT · SOFORT | `EV_RAEUMUNG_STEHT` | `IMPLEMENTED` |
| 3 | Vermieterschaft räumt ohne Gericht | RECHT + SOZIAL · SOFORT | `EV_SELBSTHILFE` | `IMPLEMENTED` |
| 4 | Nur Kündigung, noch kein Verfahren | Wechsel zu Issue 1 oder 3 · nach diesen Issues | `EV_NUR_KUENDIGUNG_ZAHLUNGSVERZUG`, `EV_NUR_KUENDIGUNG_ANDERE` | `IMPLEMENTED` |
| 5 | Stadium unklar | RECHT + SOZIAL · SOFORT | `EV_STADIUM_UNKLAR` | `IMPLEMENTED` |
| 6 | Klientin will «freiwillig» einen Auszugstermin unterschreiben | RECHT · SOFORT | `EV_UNTERSCHRIFT_AUSZUG` | `IMPLEMENTED` |

### Erlaubte Aussagen (7)

| Aussage (Dossier, gekürzt) | Status | HINT-ID |
|---|---|---|
| Die Vermieterschaft darf die Wohnung nicht selbst räumen. Dafür braucht es einen Entscheid eines Gerichts. | `IMPLEMENTED` | `EV_HINT_KEINE_SELBSTHILFE` |
| Schreiben von Gericht oder Ammannamt enthalten oft sehr kurze Fristen. Bitte heute noch einer Rechtsfachperson… | `IMPLEMENTED` | `EV_HINT_BEHOERDENFRIST` |
| Auch wenn die Kündigung angefochten ist, kann ein Ausweisungsverfahren laufen. Reagieren Sie deshalb auf jedes… | `IMPLEMENTED` | `EV_HINT_ANFECHTUNG` |
| Wer nach Ablauf der Zahlungsfrist bezahlt, macht die Kündigung dadurch nicht ungültig. Eine Einigung mit der V… | `IMPLEMENTED` | `EV_HINT_NACHZAHLUNG` |
| Parallel zur rechtlichen Prüfung sollte jetzt eine Unterkunft gesucht werden. | `IMPLEMENTED` | `EV_HINT_UNTERKUNFT` |
| Bewahren Sie alle Schreiben mit Umschlag und Abholungseinladung auf. | `IMPLEMENTED` | `EV_HINT_UNTERLAGEN` |
| Hat der Sozialdienst oder eine andere Person während der Zahlungsfrist für die Klientin bezahlt, kann das ents… | `IMPLEMENTED` | `EV_HINT_DRITTZAHLUNG` |

### Verbotene Aussagen (9)

Alle 9 Dossier-Punkte sind über `policies/forbidden_statements.yaml` (Muster, beim Laden und zur Laufzeit geprüft) bzw. als Systemregel (keine Fristberechnung, keine Prognose, keine Prozentzahl, kein Referenzzinssatz) umgesetzt; die konkreten Beispielsätze sind in `apps/api/tests/test_issues_2_7.py::test_forbidden_statements_from_the_dossiers_are_blocked` bzw. `test_issue01.py` getestet. Abstrakte Punkte wie «Jedes berechnete Fristende» sind durch `FB_DEADLINE_END_DATE` und Textprüfungen der KB abgedeckt.

### Lücken und offene Zulieferungen

| Punkt | Status | Anmerkung |
|---|---|---|
| Streitwert-Berechnung (4A_391/2013 E. 5, OG ZH LF260018 E. 5.1) | `NOT_APPLICABLE` | Das System berechnet keine Fristen oder Streitwerte; Prüfpunkt für die Rechtsperson. |
| Keyword-Netz «Audienz», «Einzelgericht», «Räumungstermin», «Schloss ausgewechselt» | `IMPLEMENTED` | In issue_keywords.py (Mock/Prefilter); die globale Eskalation gilt zusätzlich. |
| Zürcher Entscheide mit Erfolg der Mieterin | `BLOCKED` | Optionale Zulieferung steht aus. |

### Offene Prüfpunkte laut Dossier (☐) – juristische Bestätigung

- ☐ Produktentscheid: Bei Issue 6 keine Rückfrage-Runden, sondern sofort eskalieren, auch wenn Fakten fehlen (Ausnahme zu G7). Einverstanden?  → `PENDING_LEGAL_REVIEW`
- ☐ Darf das System der Sozialarbeiterin eine Liste der Unterlagen für die Rechtsperson ausgeben (Mietvertrag, Mahnung, Kündigung, Zahlungsbelege inkl. Zahlungen des Sozialdienstes, Gerichtsschreiben)? Vorschlag: ja  → `PENDING_LEGAL_REVIEW`
- ☐ Faktenliste für «mögliche Einwände» ergänzen (mündliche Abmachungen, Zahlungen Dritter, Zustellprobleme, Familienwohnung), weil nach BGE 138 III 620 E. 5.1.1 substanziierte und schlüssige Einwände den klaren Fall verhindern können  → `PENDING_LEGAL_REVIEW`
- ☐ Keyword-Netz ergänzen: «Audienz», «Einzelgericht», «Räumungstermin», «Schloss ausgewechselt»  → `PENDING_LEGAL_REVIEW`

Bereits vom Law-Team erledigt (☒): 1.

### «Was wir noch von euch brauchen» (Dossier)

- Erledigt: Volltexte BGE 138 III 620, 141 III 23, 142 III 515, 138 III 123, 139 III 38, 140 III 315, 142 III 690, BGer 4A_391/2013.
- Erledigt: Volltext BGer 4A_68/2014 (vollständiges Urteil zu BGE 140 III 315), eingearbeitet.
- Streitwert: 4A_391/2013 E. 5 und OG ZH LF260018 E. 5.1 geben den Massstab (Mietzins für die voraussichtliche Dauer, bis die Vermieterschaft wieder verfügen kann). Ein publizierter BGE dazu wäre besser, ist aber nicht zwingend.
- Optional: ein bis zwei Zürcher Entscheide, in denen die Mieterin Erfolg hatte (Nichteintreten wegen unklarer Lage).
- Kontakte: Notunterkunft und Sozialdienst der Stadt Zürich bzw. eurer Demo-Gemeinde; Stadtammannämter.
- Offene Prüfpunkte
- ☒ Lehrbuch-Zitate am Volltext bestätigt
- ☐ Produktentscheid: Bei Issue 6 keine Rückfrage-Runden, sondern sofort eskalieren, auch wenn Fakten fehlen (Ausnahme zu G7). Einverstanden?
- ☐ Darf das System der Sozialarbeiterin eine Liste der Unterlagen für die Rechtsperson ausgeben (Mietvertrag, Mahnung, Kündigung, Zahlungsbelege inkl. Zahlungen des Sozialdienstes, Gerichtsschreiben)? Vorschlag: ja
- ☐ Faktenliste für «mögliche Einwände» ergänzen (mündliche Abmachungen, Zahlungen Dritter, Zustellprobleme, Familienwohnung), weil nach BGE 138 III 620 E. 5.1.1 substanziierte und schlüssige Einwände den klaren Fall verhindern können
- ☐ Keyword-Netz ergänzen: «Audienz», «Einzelgericht», «Räumungstermin», «Schloss ausgewechselt»
- Quellen
- Gesetz: ZPO.pdf (SR 272, Stand 1.7.2026), Art. 198, 236, 239, 243, 248, 252–257, 308, 314 f., 321, 325, 336–343 (S. 52–99); OR_admin.pdf (SR 220, Stand 1.10.2026), Art. 257d, 266l–o, 267, 271–273 (S. 68–84); GOG ZH (LS 211.1, Stand 1.7.2020), §§ 21, 24, 26, 147 (S. 6 f., 32)
- Lehrbuch: euer Auszug «§ 31 Miete», N 3025d–3025f (S. 990–992)
- Volltexte (eure Dateien): BGE 138 III 123, 138 III 620, 139 III 38, 140 III 315, 141 III 23, 141 III 262, 142 III 515, 142 III 690; BGer 4A_391/2013, 4A_68/2014
- Obergericht Zürich: Beschluss LF260018-O/U vom 16.3.2026; Checkliste Ausweisungsgesuch (gerichte-zh.ch, abgerufen 7.11.2026)

## Issue 7 – Mietzinserhöhung (`CH_TENANCY_RENT_INCREASE`)

### Elemente

| Dossier-Element | Status | Umsetzung |
|---|---|---|
| Gesetzesartikel (29) | `IMPLEMENTED` | Alle als Quellen in `sources.yaml` (Wortlaut `text_de`, `valid_as_of`, PDF-Seite); Fedlex-Verifikation steht aus (`UNVERIFIED`). |
| Leitentscheide (9) | `PENDING_LEGAL_REVIEW` | Alle als Quellen mit Kernaussage/Fundstelle; Prüfstand «Volltext» laut Dossier, nicht systemseitig verifiziert. |
| Benötigte Informationen | `IMPLEMENTED` | 38 Fakten inkl. gemeinsam genutzter Vorprüfung; bedingte Pflicht über `required_if`; gleiche Frage nur einmal pro Fall. |
| Grenzen und Ausnahmefälle | `IMPLEMENTED` | Als Eskalationsregeln, Prüfhinweise (REVIEW_POINT) und Aussagenfilter; nicht 1:1 abgebildete Randfälle siehe «Lücken». |
| Verfahren und Fristen | `IMPLEMENTED` | Nur als Aussage/Hinweis und Produktschwelle; **kein berechnetes Fristende**. |
| Stellen und Behörden | `PENDING_LEGAL_REVIEW` | `authorities.yaml` (`contact_verified: false`) und `referral_network.yaml` (Signale); keine erfundenen Kontakte. |
| Eskalationsregeln | `IMPLEMENTED` | Tabelle unten. |
| Erlaubte/verbotene Aussagen | `IMPLEMENTED` | Tabellen unten; Policy-Muster in `forbidden_statements.yaml`. |
| Briefing für die Fachperson | `IMPLEMENTED` | `briefing_profile` (Gruppen, Prüfpunkte, Dokumente, Stellen) im gemeinsamen Fallbericht; Template nicht dupliziert. |
| Teamentscheide (7.11.2026) | `IMPLEMENTED` | Siehe Eskalations- und Aussagen-Tabellen; Einwilligung `consent_briefing`; G7 pro Fakt (max. 2 Nachfragen, danach UNKNOWN → Eskalation). |

### Eskalationsregeln des Dossiers

| # | Wenn (Dossier) | Route / Dringlichkeit (Dossier) | Regel-ID(s) | Status |
|---:|---|---|---|---|
| 1 | Schreiben oder Empfangsdatum fehlt | RÜCKFRAGE · – | Engine (ASK) | `IMPLEMENTED` |
| 2 | Empfang liegt eine Produktschwelle oder länger zurück (Vorschlag: ab 20 Tagen) oder ist unbekannt | RECHT · SOFORT | `RI_FRIST_20_ODER_UNBEKANNT` | `IMPLEMENTED` |
| 3 | Kein amtliches Formular, keine Begründung oder Kündigungsandrohung | RECHT · BALD (SOFORT bei Drohung) | `RI_KEIN_FORMULAR`, `RI_KUENDIGUNGSDROHUNG` | `IMPLEMENTED` |
| 4 | Formgültig, Klientin will prüfen lassen | RECHT · BALD | `RI_PRUEFUNG_GRUNDREGEL` | `IMPLEMENTED` |
| 5 | Subventionierte Wohnung oder Genossenschaft | RECHT · BALD | `RI_SUBVENTIONIERT_GENOSSENSCHAFT` | `IMPLEMENTED` |
| 6 | Klientin soll etwas unterschreiben oder hat zugestimmt | RECHT · SOFORT | `RI_UNTERSCHRIFT` | `IMPLEMENTED` |
| 7 | Erhöhung führt über die Mietzinslimite der Sozialhilfe oder ist nicht finanzierbar | SOZIAL (+ RECHT) · BALD | `RI_NICHT_FINANZIERBAR` | `IMPLEMENTED` |
| 8 | Staffelmiete, formgerecht, Klientin will nur Information | KI_WEITER · NORMAL | Engine (PROCEED) | `IMPLEMENTED` |
| 9 | Schreiben enthält zugleich eine Kündigung | Wechsel zu Issue 1 · SOFORT | `RI_KUENDIGUNG_IM_SCHREIBEN` | `IMPLEMENTED` |

### Erlaubte Aussagen (8)

| Aussage (Dossier, gekürzt) | Status | HINT-ID |
|---|---|---|
| Eine Mietzinserhöhung muss auf einem amtlichen Formular mitgeteilt und begründet werden. Ob das hier erfüllt i… | `IMPLEMENTED` | `RI_HINT_FORM` |
| Wer eine Erhöhung für missbräuchlich hält, kann sie innert 30 Tagen nach Empfang bei der Schlichtungsbehörde a… | `IMPLEMENTED` | `RI_HINT_ANFECHTUNG` |
| Während der Anfechtung muss nur die bisherige Miete bezahlt werden. Es lohnt sich aber, die Differenz zur Seit… | `IMPLEMENTED` | `RI_HINT_ALTER_MIETZINS` |
| Das Verfahren vor der Schlichtungsbehörde kostet keine Gerichtskosten. | `IMPLEMENTED` | `RI_HINT_KOSTENLOS` |
| Eine Kündigung, die erfolgt, weil jemand eine Erhöhung anficht, kann ihrerseits angefochten werden. | `IMPLEMENTED` | `RI_HINT_KUENDIGUNG_NACH_ANFECHTUNG` |
| Dasselbe gilt für neue Nebenkosten oder wenn Leistungen gestrichen werden. | `IMPLEMENTED` | `RI_HINT_NEBENKOSTEN` |
| Bei Erhöhungen wegen Kostensteigerungen oder Renovationen kann man verlangen, dass die Vermieterschaft die Zah… | `IMPLEMENTED` | `RI_HINT_ZAHLEN_VERLANGEN` |
| Die Schlichtungsbehörde berät auch ohne Verfahren und hilft einzuschätzen, ob eine Erhöhung missbräuchlich ist… | `IMPLEMENTED` | `RI_HINT_BERATUNG` |

### Verbotene Aussagen (7)

Alle 7 Dossier-Punkte sind über `policies/forbidden_statements.yaml` (Muster, beim Laden und zur Laufzeit geprüft) bzw. als Systemregel (keine Fristberechnung, keine Prognose, keine Prozentzahl, kein Referenzzinssatz) umgesetzt; die konkreten Beispielsätze sind in `apps/api/tests/test_issues_2_7.py::test_forbidden_statements_from_the_dossiers_are_blocked` bzw. `test_issue01.py` getestet. Abstrakte Punkte wie «Jedes berechnete Fristende» sind durch `FB_DEADLINE_END_DATE` und Textprüfungen der KB abgedeckt.

### Lücken und offene Zulieferungen

| Punkt | Status | Anmerkung |
|---|---|---|
| Formularprüfung automatisch aus dem Upload (OCR/Layout) | `PARTIAL` | Pflichtangaben nach Art. 19 VMWG werden als Fakten abgefragt und von der Sozialarbeiterin am Original bestätigt; keine automatische Dokumentanalyse. |
| Mietzinslimiten der Sozialhilfe der Demo-Gemeinde | `BLOCKED` | Optionale Zulieferung steht aus; das System nennt keine Limite. |
| Zürcher Entscheid zu Erhöhung (Referenzzinssatz/Renovation) | `BLOCKED` | Optionale Zulieferung steht aus. |
| Referenzzinssatz-Wert / Missbräuchlichkeitsberechnung | `NOT_APPLICABLE` | Bewusst nicht implementiert (Verbot laut Dossier). |

### Offene Prüfpunkte laut Dossier (☐) – juristische Bestätigung

- ☐ Produktschwelle festlegen: ab wie vielen Tagen seit Empfang SOFORT (Vorschlag 20 Tage)  → `PENDING_LEGAL_REVIEW`
- ☐ Formularprüfung aus dem Upload: Das System schlägt anhand der Pflichtangaben nach Art. 19 VMWG vor (bisheriger und neuer Mietzins, Zeitpunkt, Begründung, Verweis auf Begleitschreiben, Anfechtungshinweis, Seite 3 vorhanden), die Sozialarbeiterin bestätigt; nie als rechtliche Bewertung  → `PENDING_LEGAL_REVIEW`
- ☐ Mietzinslimiten der Sozialhilfe eurer Demo-Gemeinde (falls ihr den Sozialhilfe-Fall zeigen wollt)  → `PENDING_LEGAL_REVIEW`

Bereits vom Law-Team erledigt (☒): 1.

### «Was wir noch von euch brauchen» (Dossier)

- Erledigt: VMWG, Zürcher Formular, Volltexte BGE 118 II 130, 121 III 163, 121 III 214, 124 III 67, 131 III 566, 137 III 208, 137 III 362, 142 III 375, 147 III 14.
- Optional: ein Zürcher Entscheid zu einer Erhöhung wegen Referenzzinssatz oder nach Renovation bei einer Wohnung (für die Demo).
- Optional: Hinweis, ob der Kanton Zürich das Formular auch für neue Verträge vorschreibt (Art. 270 Abs. 2 OR); nur für den Anfangsmietzins relevant.
- Offene Prüfpunkte
- ☒ Lehrbuch-Zitate am Volltext geprüft (drei Abweichungen, zwei durch neues Recht überholte Aussagen, siehe Leitentscheide)
- ☐ Produktschwelle festlegen: ab wie vielen Tagen seit Empfang SOFORT (Vorschlag 20 Tage)
- ☐ Formularprüfung aus dem Upload: Das System schlägt anhand der Pflichtangaben nach Art. 19 VMWG vor (bisheriger und neuer Mietzins, Zeitpunkt, Begründung, Verweis auf Begleitschreiben, Anfechtungshinweis, Seite 3 vorhanden), die Sozialarbeiterin bestätigt; nie als rechtliche Bewertung
- ☐ Mietzinslimiten der Sozialhilfe eurer Demo-Gemeinde (falls ihr den Sozialhilfe-Fall zeigen wollt)
- Quellen
- Gesetz: OR_admin.pdf (SR 220, Stand 1.10.2026), Art. 253b, 269–270e, 271a (S. 66, 78–81); VMWG (SR 221.213.11, Stand 1.10.2025), Art. 2, 12a, 13, 14, 18–21 (S. 1–9); ZPO.pdf (SR 272, Stand 1.7.2026), Art. 113, 209–211, 243; GOG ZH (Stand 1.7.2020), §§ 21, 63, 66
- Formular: Kanton Zürich, Direktion der Justiz und des Innern, «Mitteilung von Mietzinserhöhungen und einseitigen Vertragsänderungen (Art. 269d OR)», 3 Seiten
- Lehrbuch: euer Auszug «§ 31 Miete», N 3017–3019o (S. 971–982)
- Volltexte (eure Dateien): BGE 118 II 130, 121 III 163, 121 III 214, 124 III 67, 131 III 566, 137 III 208, 137 III 362, 142 III 375, 147 III 14
- Datenschutz: DSG (Stand 7.7.2025), Art. 5 lit. c Ziff. 6

## Querschnitt

| Thema | Status | Anmerkung |
|---|---|---|
| Mehrere Issues pro Fall, Cross-Issue-Verweise aus YAML (`routes_to_issue`) | `IMPLEMENTED` | Geladene Issues werden zusätzlich angewendet; Status DRAFT wird im Hinweis ausgewiesen. |
| Gleiche Frage nur einmal (gemeinsame Fakten-IDs) | `IMPLEMENTED` | `analyze_facts` führt Fakten über Issues zusammen. |
| Höchste Dringlichkeit, zusammengeführte Gründe, deduplizierte Fachstellen | `IMPLEMENTED` | Engine sortiert nach Dringlichkeit; Referral-Plan dedupliziert. |
| Rückfrage-Runden (G7): max. 2 Nachfragen pro Fakt | `IMPLEMENTED` | Pro Fakt (bestehende Logik «zweimal unklar → unbekannt»); Issue 6 ohne Rückfrageschleife. Ein globaler Rundenzähler über den ganzen Fall existiert nicht. |
| `consent_briefing` (Status, Zeitpunkt, Erfasser, Geltungsbereich) | `IMPLEMENTED` | Fakt in allen Issues; Block im Fallbericht; blockiert die lokale Fallaufnahme nicht. Es gibt keinen Freigabe-Workflow für die tatsächliche externe Weitergabe. |
| Datenschutzrechtliche Einordnung (IDG ZH vs. DSG) | `PENDING_LEGAL_REVIEW` | Im Bericht als «voraussichtlich» gekennzeichnet; Bestätigung vor produktivem Einsatz nötig. |
| Gesundheitsangaben (H1–H7) ohne Diagnose/Ursache | `IMPLEMENTED` | Nur ja/nein; Wortlaut wird nicht gespeichert (`store_evidence: false`). |
| Gemini-Klassifikation für alle 7 Issues | `IMPLEMENTED` | Katalog dynamisch aus der KB; Fakten-Katalog per Keyword-Prefilter begrenzt (Kostenkontrolle); Entscheidungen bleiben deterministisch. |
| Fedlex-Verifikation der neuen Gesetzesquellen | `PENDING_LEGAL_REVIEW` | `python -m app.services.sources.fedlex.cli sync` (nur nach Freigabe); bis dahin `UNVERIFIED`. |

