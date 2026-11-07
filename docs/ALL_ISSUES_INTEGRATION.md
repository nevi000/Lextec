# Integration der sieben Mietrechts-Issues (Law-Dossiers vom 7.11.2026)

Alle sieben Dossiers (`docs/legal_inputs/issues/issue_01.docx … issue_07.docx`) sind in die **bestehende** Architektur integriert:
deterministische Engine (ESCALATE > ASK > PROCEED), YAML-Wissensbasis, Safety-Layer, Referral-Netz, Fedlex-Quellenmodell,
versionierter Fallbericht. Es gibt keine neue Architektur neben der bestehenden, keine `if issue == …`-Sonderfälle im Code
und keine UI-Auswahl für Issues. **Kein Issue ist juristisch freigegeben** (`content_status: DRAFT`); die Dossiers sind kein
Freigabedokument. Details pro Dossier-Zeile: [`ISSUE_COVERAGE_MATRIX.md`](ISSUE_COVERAGE_MATRIX.md) (generiert).

## 1. Überblick

| # | Issue-ID | Titel | Fakten | Eskalationsregeln | Aussagen / Prüfhinweise |
|---|---|---|---:|---:|---|
| 1 | `CH_TENANCY_TERMINATION` | Kündigung durch die Vermieterschaft | 35 | 23 | 10 / 7 |
| 2 | `CH_TENANCY_PAYMENT_WARNING` | Zahlungsaufforderung mit Kündigungsandrohung | 36 | 20 | 12 / 4 |
| 3 | `CH_TENANCY_PAYMENT_DEFAULT` | Kündigung wegen Zahlungsverzug | 44 | 15 | 8 / 6 |
| 4 | `CH_TENANCY_EXTENSION` | Erstreckung des Mietverhältnisses | 37 | 15 | 9 / 5 |
| 5 | `CH_TENANCY_DEFECTS` | Mängel an der Mietsache (inkl. Gesundheit H1–H7) | 43 | 25 | 11 / 4 |
| 6 | `CH_TENANCY_EVICTION` | Ausweisung und Räumung | 28 | 17 | 7 / 3 |
| 7 | `CH_TENANCY_RENT_INCREASE` | Mietzinserhöhung / einseitige Vertragsänderung | 38 | 14 | 8 / 8 |

Das frühere Demo-Issue `tenancy_defects` (DEMO_SYNTHETIC) bleibt für alte Fälle und Tests geladen, wird aber **nicht mehr klassifiziert**
(`KnowledgeBase.catalog_issues()` blendet Demo-Issues aus, sobald ein echtes Issue mit gleichem `legal_area` + `issue` existiert).
Keine Datenbank-Migration nötig: Fakten-, Issue- und Quellen-IDs aus Issue 1 sind unverändert; es kamen nur neue IDs hinzu.

## 2. Wie die Daten entstehen (Pipeline)

```
docx ──scripts/kb/extract_issue_docs.py──▶ docs/legal_inputs/issues_extracted/issue_0N.json   (verlustfreie Kopie)
JSON-Tabellen (Gesetzesartikel, Leitentscheide) ─▶ knowledge_base/legal_sources/sources.yaml   (automatisch, Wortlaut 1:1)
scripts/kb/specs/issue_0N.py (Fakten, Regeln, erlaubte Aussagen, Briefing) ─▶ legal_issues/<ID>.yaml + tests/scenarios_<ID>.yaml
                                  python scripts/kb/build_issue_kb.py
python scripts/kb/build_coverage_matrix.py ─▶ docs/ISSUE_COVERAGE_MATRIX.md   (bricht ab, wenn Dossier-Zeilen und Zuordnung auseinanderlaufen)
```

Issue 1 wird weiter von Hand gepflegt (`CH_TENANCY_TERMINATION.yaml`); die Specs 2–7 sind die Quelle der generierten YAML-Dateien
(Dateikopf: «GENERIERT … nicht von Hand ändern»). Validierung: `python -m app.services.knowledge.cli` (Schema, Quellen-Referenzen,
Aussagen-Policy auf allen KB-Texten, 128 Szenarien).

## 3. Cross-Issue-Architektur (Teil 11 der Aufgabe)

| Anforderung | Umsetzung |
|---|---|
| Mehrere Issues pro Fall | `case_issues` (unverändert) + Aktivierung über `routes_to_issue` |
| Issue-IDs strikt validiert | Loader: `routes_to_issue` muss geladenes Issue oder `related_issues.yaml`-Eintrag sein; KI-Zuordnungen werden gegen den Katalog geprüft (`validation.py`) |
| Cross-Issue-Links aus YAML | `escalation_rules[].routes_to_issue`. Ein **geladenes** Issue wird zusätzlich angewendet (auch `DRAFT`; der Hinweis sagt «Dossierstand, nicht juristisch freigegeben»). Nicht geladene bleiben «menschliche Prüfung empfohlen» |
| Gemeinsame Fakten, keine doppelte Frage | Gleiche Fakt-ID in mehreren Issues = eine Frage (`analyze_facts`); die Specs kopieren gemeinsame Fakten aus Issue 1/2/4/5 |
| Bedingte Fakten | `required_if` (z. B. separate Zustellung nur bei Familienwohnung, Reaktion nur nach Meldung, Gesundheitsfelder nur bei Schimmel/Gefahr) |
| Fallzustand bleibt bei Issue-Wechsel | Fakten gehören zum Fall, nicht zum Issue; Test `test_case_state_is_preserved_when_issues_are_added` |
| Gründe zusammenführen, höchste Dringlichkeit | Engine sortiert `triggered_rules` nach Dringlichkeit (HIGH zuerst) über alle aktiven Issues; `max_urgency` = höchste |
| Fachstellen deduplizieren | `plan_referrals`: eine Karte pro Stelle, Signale (`signal_bindings`) aus Regel-IDs |
| Widersprüchliche Standardaussagen | `suppress_standard_statements` (z. B. Issue 4 bei Zahlungsverzug: keine Erstreckungsaussagen) |
| Getrennte Fristregeln | Issue 1 (absolute Empfangstheorie, `derived.days_since_earliest_receipt`) und Issue 2/7 (relative Empfangsregel, eigene Fakten `warning_receipt_date` / `increase_receipt_date`, eigene `derived`-Werte) |

## 4. Gemini und Kostenkontrolle

* Der Issue-Katalog (`issue_catalog`) wird dynamisch aus allen **klassifizierbaren** Issues der KB gebaut (`classification.description`, `typical_situations`).
  Der Prompt ist unverändert (strukturierter Output, wörtliche Zitate, «nicht möglichst viele Issues wählen»); Entscheidungen bleiben deterministisch.
* **Kostenkontrolle:** Der Fakten-Katalog wird nicht mehr pauschal für alle Fakten (~230) gesendet, sondern nur für bereits erkannte Issues bzw. Issues,
  die der **lokale Keyword-Prefilter** (`app/services/ai/issue_keywords.py`, kein API-Aufruf) für die Nachricht plausibel macht. Ohne Treffer: Fallback auf alle.
  Routing-Issues werden über Fragen erhoben, nicht aus Freitext extrahiert. Keine zusätzlichen Aufrufe beim Rendern; Budget-/Request-Limits unverändert.
* Gesundheitsfakten (`health_symptoms_reported`, `medical_risk_reported`) haben `store_evidence: false`: gespeichert wird nur ja/nein, nie der Wortlaut (keine Diagnose/Ursache).
* Alle automatisierten Tests verwenden ausschliesslich die Mock-KI.

## 5. Pro Issue

### Issue 1 – Kündigung (aktualisiert, nicht neu erstellt)
1. **Geändert:** Neue Dossierfassung: Fakt `contract_termination_dates` («Welche Kündigungstermine nennt der Mietvertrag?») und Prüfhinweis `TT_HINT_LOCAL_TERMS` (ortsübliche Termine **nicht hart kodiert**);
   Teamentscheide: ≥ 20 Tage oder Empfang unbekannt → sofort (bestand), **neu** befristeter Vertrag ≤ 75 Tage bis Vertragsende oder Ende unbekannt → sofort (`TT_FIXED_TERM_LE_75`, Fakt `contract_end_date`, Wert `days_until_contract_end`), `consent_briefing`.
2. **Unverändert:** alle Fakt-IDs, Regel-IDs, Quellen-IDs. `TT_MOVE_OUT_LT_60` bleibt als bisheriger Produktentscheid.
3. **Verbunden mit:** 2/3 (Zahlungsverzug), 4 (Erstreckung/befristet), 6 (Gerichtsverfahren), 5 und 7 (Rückverweise).

### Issue 2 – Zahlungsaufforderung (Art. 257d Abs. 1 OR)
* Parallele Eskalation Sozialarbeiterin (Zahlung sichern) + Rechtsperson: Regel `PW_FRIST_LAEUFT_NICHT_BEZAHLT`. Relative Empfangsregel (BGE 119 II 147), eigene Fakten; **kein berechnetes Fristende**.
* 3-Arbeitstage-Puffer für Überweisungen = Produktempfehlung (`PW_HINT_UEBERWEISUNG_PUFFER`, Quelle `PRODUKTREGEL`), keine Gesetzesfrist.
* Zahlungen Dritter (Sozialdienst) und Rücküberweisungen (BGer 4A_68/2014); Interessenkonflikt bei Sozialdienst-Zahlung → unabhängige Rechtsperson.
* Übergänge: Kündigung erhalten / Frist abgelaufen → Issue 3; Miete wegen Mängeln zurückbehalten → Issue 5. 14-Tage-Wartezeit-Hinweis (Teamentscheid).

### Issue 3 – Kündigung wegen Zahlungsverzug
* Grundregel `PD_GRUNDREGEL`: **jede** solche Kündigung eskaliert sofort an Rechtsperson + Sozialarbeiterin, auch bei fehlenden Pflichtfeldern (Fragen laufen parallel). Keine Erfolgsprognose, Erstreckung ausgeschlossen (Statement), drei Prüffragen (Mahnung / Zahlung / Kündigung) als Briefing-Gruppen.
* Wiederverwendung der Mahnungs-Fakten aus Issue 2; Übergang zu Issue 6 bei Gericht/Selbsthilfe. Wartezeit ≥ 14 Tage = Prüfhinweis (Verzicht?).

### Issue 4 – Erstreckung
* Immer Rechtsperson (Ermessen), keine Prognose zur Dauer; Ausschluss bei Zahlungsverzug (→ Issue 3, Aussagen unterdrückt) und frühere gültige Mahnung (BGE 117 II 415).
* Produktschwellen: unbefristet ≥ 20 Tage seit Empfang oder unbekannt; befristet ≤ 75 Tage bis Vertragsende oder unbekannt; Zweiterstreckung ≤ 75 Tage bis Ende der ersten. Konkubinat nur als Faktum.

### Issue 5 – Mängel (inkl. 3a Gesundheit)
* Einziges Issue mit `PROCEED` (einfache Fälle ohne Geld/Frist/Gesundheit, Teamentscheid «KI_WEITER»). Regeln H1–H5, H7 als Eskalationsregeln, H6 als Prüfhinweis; `UNBEKANNT ist nie NEIN` (H7).
* Keine Prozentzahl, keine Hinterlegungs-/Fristlos-Empfehlung, keine Schwere-Einordnung, keine Ursachenaussage; 30-Tage-Produktschwelle ohne Reaktion der Vermieterschaft.
* Übergänge: Zahlungsaufforderung/Kürzung → Issue 2, Kündigung nach Meldung → Issue 1. Notunterkunft-Stellen (Stadt Zürich) aus dem Dossier als Stellen; Telefonnummern nur wo im Dossier genannt.

### Issue 6 – Ausweisung und Räumung
* **Keine Rückfrage-Runden** (bewusste Ausnahme von G7): `EV_GRUNDREGEL` eskaliert immer sofort; fehlende Angaben werden parallel erhoben. Bei Räumungstermin/Schloss: SOZIAL zuerst, dann RECHT.
* Fristen aus Gerichts-/Ammannamtsschreiben nur wörtlich (`deadline_quoted_text`), nie berechnet. Einwände (Familienwohnung, Zahlungen Dritter, Abmachungen, Anfechtung hängig) als Briefing-Fakten. Unterlagenliste im Fallbericht.

### Issue 7 – Mietzinserhöhung (Art. 269 ff. OR, VMWG)
* Relative Empfangsregel (BGE 137 III 208); ≥ 20 Tage oder unbekannt → sofort (`RI_FRIST_20_ODER_UNBEKANNT`).
* Formular-Vorprüfung nach Art. 19 VMWG nur als **Hinweis** (`RI_REVIEW_FORMHINWEIS`), von der Sozialarbeiterin am Original bestätigt; gedruckte Unterschrift ist seit 1.10.2025 kein Formfehler.
* Keine Missbräuchlichkeitsberechnung, kein Referenzzinssatz-Wert, kein berechnetes Datum. Staffelmiete formgerecht → `PROCEED`.

## 6. Quellen

* `sources.yaml`: von 48 auf 192 Einträge. Gesetze OR (SR 220), ZPO (SR 272), SchKG (SR 281.1), VMWG (SR 221.213.11), BV, DSG als `provider: fedlex`; **GOG ZH / IDG ZH als kantonal** (`provider: other`, `fedlex_sync: false`).
* BGE/BGer strukturiert (Zitat, Kernaussage, Fundstelle, Prüfstand); ein Eintrag wird von mehreren Issues wiederverwendet. Lehrbuch und Produktregeln sind eigene Typen (`other`), nie als Gesetz/BGE dargestellt.
* Alles bleibt `UNVERIFIED`, bis ein Fedlex-Sync gelaufen ist; `dossier_status` trennt «laut Dossier geprüft» von systemseitiger Verifikation.

## 7. Datenschutz / Einwilligung

`consent_briefing` (boolean, optional) in allen Issues. Im Fallbericht: Status, Zeitpunkt (`updated_at`), Erfasser (Sozialarbeiterin / KI-Vorschlag), Geltungsbereich (externe Weitergabe, **nicht** lokale Erstellung/Download).
Die lokale Fallaufnahme wird nie blockiert. Es gibt (noch) keinen Freigabe-Workflow für die tatsächliche externe Weitergabe. Die Einordnung IDG ZH vs. DSG ist als «voraussichtlich» gekennzeichnet und vor produktivem Einsatz fachlich zu bestätigen.

## 8. Tests

* `apps/api/tests/test_issues_2_7.py`: Struktur/Quellen, Issue-Logik, Cross-Issue, 57 verbotene Beispielsätze, alle erlaubten Aussagen der Dossiers (Policy + Abdeckung), die **10 Cross-Issue-Tests** (Mock-KI), Einwilligung im Bericht, Kosten-Prefilter.
* 128 KB-Szenarien (`knowledge_base/tests/scenarios*.yaml`), darunter T5-01…16, T6-01…07, T7-01…10 aus den Dossiers (alle `SYNTHETIC_TECHNICAL`, keine echten Fälle).
* Angepasst (nicht «passend gemacht»): Tests, die den früheren Zustand «Issue 3/4/6 nicht umgesetzt» prüften (`available is False`, Anzahl Issues, Anzahl Stellen).

## 9. Anleitung: Issue 8 hinzufügen (primär durch Daten)

1. Dossier nach `docs/legal_inputs/issues/issue_08.docx`, `python scripts/kb/extract_issue_docs.py` ausführen.
2. `scripts/kb/specs/issue_08.py` nach dem Muster `issue_05.py` anlegen (`SPEC` mit `facts`, `escalation`, `legal`, `briefing`, `scenarios`; gemeinsame Fakten über `shared_facts([...])` / `common(...)`), Modul in `SPEC_MODULES` (`build_issue_kb.py`) eintragen.
3. Gesetzes-/BGE-Tabellen werden automatisch in `sources.yaml` importiert (`collect_dossier_sources`); zusätzliche Quellen in `EXTRA_SOURCES`, neue Stellen in `AUTHORITIES_NEW`.
4. Verbote aus dem Dossier als Muster in `policies/forbidden_statements.yaml` (je ein Testsatz in `test_issues_2_7.py`).
5. Referral: `issue_rules` + `signal_bindings` in `referrals/referral_network.yaml`; Verweise von anderen Issues über `routes_to_issue`.
6. Mock-Schlüsselwörter in `app/services/ai/issue_keywords.py` (nur für Tests/Prefilter; die echte Klassifikation nutzt `classification.description`).
7. `python scripts/kb/build_issue_kb.py && python -m app.services.knowledge.cli`, dann `python scripts/kb/build_coverage_matrix.py` (Zeilenzuordnung `ESC_MAP` ergänzen).
Kein Code-Eingriff in Engine, Service oder Frontend ist nötig, solange nur die vorhandene Regelsprache verwendet wird.

## 10. Bekannte Grenzen

* Keine automatische Dokumentanalyse (Formular-Upload) für Issue 7; Pflichtangaben werden abgefragt.
* Musterbrief «Mängelmeldung» wird nicht erzeugt (Teamentscheid erlaubt ihn, ohne Prozentzahl/Hinterlegungsandrohung).
* Kein globaler Rundenzähler für Rückfragen: G7 gilt pro Fakt (max. 2 Nachfragen, dann «unbekannt» → Eskalation).
* Neue Quellen sind nicht gegen Fedlex synchronisiert; Kontakte der Stellen sind nicht verifiziert.
* Optionale Zulieferungen des Law-Teams (siehe Matrix, «BLOCKED») fehlen.
