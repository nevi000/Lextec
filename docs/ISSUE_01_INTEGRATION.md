# Issue 1 – Kündigung durch die Vermieterschaft: Integration

Quelle: `docs/legal_inputs/14.28 Issue 1 – Kündigung durch die Vermieterschaft.docx` (Law-Dossier vom 7.11.2026, Gesetzeswortlaut OR Stand 1.10.2026 und ZPO Stand 1.7.2026). Eine ältere Fassung ohne «14.28» liegt in `Downloads`; **verwendet wurde die neuere, ausführlichere** (identisch mit der Datei im Repo).

> **Status:** `content_status: DRAFT`. Das Dossier ist **keine endgültige Freigabe für den Einsatz mit echten Klienten**. Alles unten ist als *implementiert / getestet / juristisch noch zu validieren / technisch offen* getrennt.

## 1. Was aus dem Dossier übernommen wurde

| Dossier-Abschnitt | Umsetzung | Datei |
|---|---|---|
| 1) 16 OR- + 9 ZPO-Artikel (wörtlich, mit PDF-Seite, Stand) | 25 Quellen mit Wortlaut, Absatz, Rechtsfrage, `valid_as_of`, `origin_ref`; in OR zusätzlich 6 nur erwähnte Artikel ohne Wortlaut (`REFERENCED_ONLY`) | `knowledge_base/legal_sources/sources.yaml` |
| 1) 8 Leitentscheide | Fundstelle, Geschäftsnummer, Datum, Erwägungen mit Seite, Kernaussage, Grenzen, relevante Fakten, `DOSSIER_CHECKED` | dito |
| Reserve-Entscheide | 6 Einträge, `DOSSIER_PENDING` (nicht als geprüft ausgewiesen) | dito |
| 2) Benötigte Informationen | 32 Fakten in 6 Gruppen; «zwingend» → `required`, «ja, bei …» → `required_if`; Frage und juristische Funktion pro Fakt | `knowledge_base/legal_issues/CH_TENANCY_TERMINATION.yaml` |
| 3) Grenzen und Ausnahmen | Anwendungsbereich (Untermiete, Notwohnung/Heim, Ferienwohnung, möbliertes Zimmer, Zahlungsverzug, laufendes Verfahren, Krankheit, Aufhebungsvereinbarung, Konkubinat/ausgezogene Partnerperson, falscher Termin, fehlende Begründung, nur Härte) als Fakten, Regeln oder Policy | dito + `policies/` |
| 4) Verfahren und Fristen | Allgemeine, quellengebundene Hinweise ohne Datum; **kein** Fristende | dito (`legal_rules`) |
| 5) Stellen im Kanton Zürich | 7 Stellen mit Zweck, Kosten laut Dossier, Quelle; **Kontaktdaten nicht verifiziert** | `knowledge_base/referrals/authorities.yaml` |
| 6) Eskalationsregeln | 22 Issue-Regeln + 4 globale + 1 System-Regel (siehe §3) | dito |
| 6) Erlaubte / verbotene Aussagen | 9 freigegebene Hinweise (HINT, je mit Quelle); 8 Verbotsregeln mit Mustern | `legal_rules`, `policies/forbidden_statements.yaml` |
| 6) Briefing (ca. 200 Wörter, 9 Teile) | Issue-spezifische Briefing-Ansicht über der allgemeinen 11-Abschnitte-Struktur | `briefing_profile` |
| Offene Prüfpunkte | siehe §8 | – |

Zusätzlich gibt es `routing/related_issues.yaml` (Issue 3, 4, 6 als *geplant*).

## 2. Architektur-Erweiterungen (rückwärtskompatibel)

* **Fakt-Zustand `UNKNOWN`** («gefragt, Klientin weiss es nicht») neben `MISSING` («noch nicht gefragt»), `KNOWN`, `AMBIGUOUS`, `CONTRADICTORY`, `NOT_APPLICABLE`. Operator `is_unknown`; `is_missing` bleibt «nicht bekannt» (inkl. unbekannt).
  * `MISSING` → Rückfrage (ASK). `UNKNOWN` → **nie erneut gefragt**; eine *erforderliche* Angabe in diesem Zustand löst die Systemregel `SYSTEM_REQUIRED_FACT_UNKNOWN` (Eskalation) aus; Zustell-/Empfangsangaben zusätzlich `TT_UNKNOWN_DELIVERY_OR_RECEIPT` (sofort).
  * Erfassung: Knopf «Weiss nicht» (lokal, ohne KI), KI-Feld `unknown` (nur als Antwort auf eine Frage), Korrektur im Fakt-Dialog. Zweimal unklar beantwortet → `UNKNOWN` (keine Endlosschleife).
  * Menschliche Korrekturen behalten Vorrang (getestet).
* **Abgeleitete Werte** (`derived:` in der KB): `days_since_earliest` / `days_until` über Datumsfakten, ausgewertet mit dem Stichtag (`APP_TODAY` oder heute). Nutzbar nur für **interne Dringlichkeit**.
* **Dokumentbeleg**: Fakt kann «durch Dokument belegt» markiert werden (Briefing-Stufe *dokumentarisch belegt*).
* **Weiterleitung** (`routes_to_issue`): ein verwandtes Issue gilt nur als *verfügbar*, wenn es geladen **und** `LEGALLY_REVIEWED` ist; sonst Empfehlung menschlicher Prüfung, keine Spezialregeln. (Pfad «verfügbar» ist mit einem Test-Issue getestet; real existiert noch keines.)
* **Unterdrückung** (`suppress_standard_statements`): ausserhalb des Moduls (Untermiete, Notunterkunft, Ferienwohnung, Zahlungsverzug, laufendes Verfahren) werden Hinweise und Prüfpunkte nicht ausgegeben.
* **Optionale Folgefragen**: wenn nichts Zwingendes mehr offen ist, werden optionale Angaben als «Optional» vorgeschlagen.
* **Quellenmodell**: `dossier_status` (Prüfstand laut Law-Dossier) **getrennt** von `verification_status` (Live-Prüfung durch das System, immer `UNVERIFIED`, da Fedlex/BGer nicht angebunden).
* **Statement-Policy** (`policies/forbidden_statements.yaml`): beim KB-Laden werden *alle* KB-Texte geprüft (Treffer = Validierungsfehler), zur Laufzeit jeder KI-Freitext (Zusammenfassung, umformulierte Fragen); bei Treffer sicherer Fallback. Jede `legal_rule` braucht mindestens eine Quelle.
* Issue-IDs dürfen Grossbuchstaben enthalten (`CH_TENANCY_TERMINATION`). Das frühere **Demo-Issue `tenancy_termination` wurde ersetzt**; seine Tests/Szenarien wurden auf die neue Definition umgestellt. Die Demo-Issues Mängel, Arbeitskündigung, Lohn bleiben.

## 3. Regeln (Dringlichkeit: HIGH = *sofort*, MEDIUM = *bald*, LOW = *normal*)

| Dossier | Regel-ID | Dringlichkeit |
|---|---|---|
| Zwingendes Faktum nicht erhoben → Rückfrage | Missing-Information-Engine (ASK) | – |
| Empfangsdatum/Zustellart nach Rückfrage unbekannt | `TT_UNKNOWN_DELIVERY_OR_RECEIPT` (+ `SYSTEM_REQUIRED_FACT_UNKNOWN`) | sofort |
| ≥ 20 Tage seit frühestem Empfangshinweis (20–30) | `TT_DAYS_GE_20` *(Produktentscheid)* | sofort |
| > 30 Tage | `TT_DAYS_GT_30` | sofort |
| < 20 Tage, alles bekannt | `TT_DAYS_LT_20_ALL_KNOWN` *(Produktentscheid)* | bald |
| Kein amtliches Formular | `TT_FORM_MISSING` | bald |
| Familienwohnung ohne separate Zustellung / Mitmieter nicht benachrichtigt | `TT_FAMILY_HOME_NOT_SEPARATE`, `TT_CO_TENANT_NOT_NOTIFIED` | bald |
| Streit/Verfahren (3 J.), Änderung Familie | `TT_PRIOR_DISPUTE`, `TT_FAMILY_CHANGE` | bald |
| Grund Sanierung/Abbruch/Eigenbedarf | `TT_REASON_SPECIAL` | bald |
| Härtegründe → + Sozialberatung, Issue 4 | `TT_HARDSHIP` | bald |
| Auszug < 60 Tage → + Sozialarbeit | `TT_MOVE_OUT_LT_60` *(Produktentscheid)* | bald |
| Zahlungsverzug → Issue 3 | `TT_PAYMENT_DEFAULT` | sofort |
| Aufhebungsvereinbarung | `TT_AGREEMENT` | sofort |
| Nicht Mieterin / Notwohnung / Untermiete / Ferienwohnung | `TT_OUT_OF_SCOPE_ROLE`, `TT_OUT_OF_SCOPE_OBJECT` | bald |
| Laufendes Verfahren/Ausweisung → Issue 6 | `TT_COURT_PROCEEDING` | sofort |
| Krankheit beim Empfang | `TT_ILLNESS_AT_RECEIPT` | sofort |
| Besondere Verletzlichkeit (ausserhalb des Moduls) | `TT_VULNERABILITY` | bald |
| Wunsch nach Fachperson | `TT_EXPERT_REQUESTED` | normal |
| Möbliertes Zimmer | `TT_FURNISHED_ROOM` | bald |
| *Technische Annahme:* Wohnung nicht im Kanton Zürich | `TT_CANTON_NOT_ZH` | bald |

**20/60-Tage-Schwellen sind interne Produktentscheide, keine Gesetzesfristen** (in der YAML, im Briefing und in der Oberfläche so ausgewiesen). Das Dossier nennt sie in Abschnitt 6; sie sind noch im Team festzuhalten (offener Prüfpunkt).

## 4. Kein Fristende, keine Gültigkeitsaussage

Unterschieden werden (getestet): (1) **interne Dringlichkeit** (Tage-Zahl, systemseitig abgeleitet, als solche gekennzeichnet), (2) **allgemeiner Hinweis** («innert 30 Tagen nach Empfang», ohne Datum) und (3) **verbotene** definitive Fristberechnung. Tests prüfen, dass im Demo-Fall weder `04.12.2026` noch ein anderes Fristende in Entscheid oder Briefing vorkommt, und dass 13 verbotene Beispielsätze (Fristende, «gültig/ungültig/nichtig», «ohne Begründung ungültig», «weil hart anfechten», Ferien verschieben die Frist, Erfolgsgarantien, «Eigenbedarf vorgeschoben», «muss (nicht) ausziehen») erkannt und ersetzt werden. Wörtliche Gesetzes-/BGE-Zitate in `legal_sources` sind ausgenommen (das Dossier erlaubt Zitate).

## 5. Gemini

* Modell `gemini-3.8-flash` über die Modellliste **verifiziert** (verfügbar). Preise: offizielle Preisseite, abgerufen 7.11.2026: $0.75 Input / $3.75 Output (inkl. Denken) pro 1 Mio. Token bis 31.12.2026, danach $1.50 / $7.50 (als Tabelle im Code, per `AI_PRICE_*` überschreibbar).
* Denkstufe `MINIMAL` wird von diesem Modell mit HTTP 400 abgelehnt (**verifiziert**); Standard ist `LOW` (`AI_THINKING_LEVEL`).
* Aufgaben: Issue-Klassifikation, Faktenextraktion (Structured Output + Pydantic-Validierung, Belege müssen wörtlich in der Nachricht stehen), Erkennung unklarer Aussagen, optional Umformulierung von Fragen (aus). **Eskalation bleibt regelbasiert.**
* **Einziger echter Test** (`python -m app.cli live-test --confirm`, ein Aufruf, kein Retry): Rechtsgebiet `CH_TENANCY_TERMINATION` (1.0) erkannt; alle 10 Fakten der Schritte 1–3 korrekt (Rolle, Mitmieter, Objektart, Gemeinde, Kanton, Vertragsart, Zustellart, Empfangsdatum 2026-11-04, Formular nein, Termin 2027-01-31), alle Belege wörtlich, keine Validierungswarnung. 5094 Eingabe-, 1367 Ausgabe-, 0 Denk-Tokens, ≈ **$0.0089**. Zwei vorangehende Anfragen wurden von Google mit HTTP 400 abgelehnt (Denkstufe), ohne Token-Verbrauch. Insgesamt **3 gesendete Anfragen**.

## 6. Kostenkontrolle (serverseitig, vor jedem Request)

| Einstellung | Standard |
|---|---|
| `AI_MAX_CALLS_PER_CASE` | 12 |
| `AI_MAX_INPUT_TOKENS_PER_CALL` | 8000 (lokale, konservative Schätzung) |
| `AI_MAX_OUTPUT_TOKENS_PER_CALL` | 2500 (hartes Limit an Gemini, inkl. Denken) |
| `AI_DAILY_REQUEST_LIMIT` | 30 |
| `AI_DAILY_TOKEN_LIMIT` | 150 000 |
| `AI_DAILY_BUDGET_USD` / `AI_CASE_BUDGET_USD` | 0.50 / 0.10 |
| `AI_MAX_RETRIES` (nur transiente Fehler) | 1 |

* Jeder Aufruf (auch Retry) wird **vorab reserviert** (Worst-Case-Kosten, unter globalem Lock → parallele Requests können Limits nicht umgehen) und danach mit den echten `usage_metadata` abgeschlossen (Tabelle `ai_usage`: Modell, Zeit, Fall-ID, Funktion, Input/Output/Denk-Tokens, Kosten, Status; **kein Nachrichteninhalt**).
* Überschreitung blockiert **vor** dem Senden mit verständlicher Meldung; blockierte Versuche zählen nicht als Analyse-Versuch.
* Unbekannter Modellpreis → Kosten «unbekannt» (nie erfunden); Token-Limit bleibt aktiv.
* Keine KI beim Laden von Seiten; einfache Antworten (Ja/Nein, Datum, Zahl, Auswahl, «Weiss nicht») werden **lokal** verarbeitet; ein Fall hat höchstens eine laufende Analyse; identische Doppel-Eingaben (< 10 s) werden nicht doppelt analysiert; höchstens 3 Analyseversuche pro Nachricht; Rephrase aus; Tests/Playwright erzwingen Mock (auch gegen den Schlüssel in `.env`).
* Anzeige: Seitenleiste (Aufrufe, geschätzte Kosten), Einstellungen (Tabelle). **Das sind Anwendungslimits, keine garantierte Google-Abrechnungsgrenze** – zusätzlich ein Budget-Alert in Google AI Studio setzen.

## 7. Demo starten

`.\scripts\dev.ps1 -Seed -ApiPort 8001 -WebPort 5174` → http://localhost:5174 → **«Demo Mietkündigung»** → «Demo starten». Die geführte Hilfe fügt vorbereitete Texte in das normale Eingabefeld ein (vorher editierbar); danach «Fall analysieren». Reihenfolge und erwartete Ergebnisse: siehe Abschnitt 8 des Abschlussberichts bzw. die Demo-Seite. Für ein reproduzierbares Datum `APP_TODAY=2026-11-07` in `.env` setzen (sonst zählt «heute»: nach > 20 Tagen ändert sich die Dringlichkeit – gewollt).

## 8. Offene Punkte

**Juristisch noch zu validieren** (Dossier-Checkliste): Reserve-BGE im Volltext (137 III 208, 148 III 215, 136 III 257, 145 III 281); ortsübliche Kündigungstermine Kanton/Stadt Zürich (Art. 266c); aktuelles amtliches Zürcher Kündigungsformular beschaffen; möbliertes Zimmer – Formvorschriften; Kontaktdaten und Kosten der Stellen auf den offiziellen Seiten bestätigen; kantonale Praxis (Obergericht ZH); Schwellen 20/60 Tage als Produktentscheid festhalten; Freigabe vor Einsatz mit echten Klienten.
**Meine technischen Annahmen (nicht im Dossier):** Fakt `property_in_canton_zh` und Regel `TT_CANTON_NOT_ZH`; Aufteilung «Familienwohnung» in drei Fakten; `hardship_present`/`vulnerability_present`/`eviction_or_court_proceeding`/`illness_at_receipt`/`absence_at_receipt`/`client_requests_expert` als boolesche Fakten, um die Regeln auslösbar zu machen; Modus «Zahlungsverzug erkannt → Standardaussagen unterdrückt»; Auslegung von «zwingend» (siehe `required`). Bitte prüfen.
**Technisch offen:** Fedlex-/BGer-Abruf und Zitatprüfung (alles `UNVERIFIED`); Issues 3, 4, 6; Gemeinde → Bezirk-Zuordnung (bewusst nicht erfunden); Foto-/Dokument-Upload (nur Markierung «belegt»); Authentifizierung; serverseitiges PDF.

## 9. Tests

`knowledge_base` 48/48 Szenarien (inkl. Grenzwerte 19/20/30/31 Tage, früheste Datumsquelle, bedingte Fakten, «unbekannt» vs. «nicht gefragt», Ausserhalb-Modul, Weiterleitung); `pytest` 124 (Klassifikation mit den 6 Dossier-Formulierungen, Demo-Ablauf Schritt 1–4 + Briefing, UNKNOWN, Policy, Quellenstatus, Kostenkontrolle inkl. Parallelität, Retry-Grenzen, «keine KI beim Seitenaufruf»); `vitest` 26; `playwright` 13 (inkl. kompletter Demo im Mock-Modus, Druckansicht und PDF-Erzeugung). Alle Tests nutzen den Mock; der einzige echte Aufruf ist `live-test`.
