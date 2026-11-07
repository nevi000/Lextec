# Integration des neuen Fallberichts (Expert Briefing)

Der Fallbericht («Expert Briefing») wird jetzt im Layout und nach der Struktur der Law-Team-Vorlage (`docs/briefing_reference/`) als
A4-HTML-Vorschau und echtes PDF erzeugt. Gemini, Regeln, Safety-/Referral-Engine, Fedlex und Datenbank sind unverändert; es gibt keine KI-Aufrufe
für Vorschau oder PDF.

## 1. Übernommene Dateien aus `case_summary_template.zip`

Entpackt nach `docs/briefing_reference/case_summary_extracted/` (Referenz, unverändert, inkl. Muster-Scans nur als Testmaterial).
In die Anwendung übernommen (`apps/api/app/services/report/`):

| Datei | Verwendung |
|---|---|
| `templates/design.css` | Design (Farben, Typografie, Ampel, A4-Tabellen). Nur «Inter Display» → «Inter» ersetzt (eine eingebettete Schrift). |
| `templates/expert_briefing.html.j2` | Basis des Fallberichts; **angepasst** (Abschnitt 2). |
| `templates/case_summary.html.j2` | generische Fallzusammenfassung für dokumentbasierte Fälle; nur im Test mit `case_sample.json` verwendet (Fristende-Zeilen entfernt). |
| `assets/lextec_logo.png` | Logo (lokal, als `data:`-URI eingebettet, kein Nachladen). |
| Inter (`inter-latin-wght-normal.woff2`, OFL) | aus dem bereits vorhandenen `@fontsource-variable/inter`, eingebettet. |
| `render_briefing.py` / `render_summary.py` | **nicht** übernommen (Linux-Chrome-Pfad, Fristberechnung, eigene Ampel); durch `render.py`, `pdf.py`, `view.py` ersetzt. |
| `knowledge_base/briefings/case_summary_v1.yaml` | Spezifikation (Referenz). Die Ampelregeln darin werden **nicht** ausgeführt (Abschnitt 5). |
| `knowledge_base/referrals/referral_rules.yaml` (Zip) | gleicher Inhalt wie die bereits integrierte v1.1; bestehende `referral_network.yaml` gilt. |

## 2. Änderungen für LexTec Bridge

- **Datenmodell:** `Case State → CaseBriefing (+ ReportExtras) → View Model → Jinja → PDF`. `ReportExtras` wird beim Erstellen jeder Version mitgespeichert (Chronologie, Gespräch, Ort, Safety, Fachstellen, Modell); jede Version rendert dadurch exakt wie erstellt. Ältere Versionen ohne Extras werden mit Hinweis gerendert.
- **Template datengetrieben:** nicht mehr auf «Mietrecht, Zürich, 30 Tage, Art. 273 OR» festgelegt. Mehrere Issues werden gemeinsam dargestellt; Eckdaten kommen aus `knowledge_base/report/report_profile.yaml` (pro Issue), sonst generisch aus den Schlüsselangaben.
- **Neu gegenüber der Referenz-PDF:** Sicherheitsbanner, Personendaten-Block, Mietverhältnis-/Eckdaten-Block, Chronologie, Gesprächsinformationen, Unterlagenübersicht, Prüfpunkt-Zustände, Quellenstatus in vier getrennten Ebenen, Links zu Fedlex. Die «Notizen»-Zeilen stehen auf der Weiterleitungsseite statt auf Seite 1 (sonst sprengt Seite 1 bei vollen Fällen den Rahmen).
- **API (rückwärtskompatibel):** `GET /api/cases/{id}/briefings/{bid}/preview` (HTML, CSP `default-src 'none'`, keine Skripte), `GET …/pdf`. Bestehende Briefing-Endpunkte, Versionierung und Datenstruktur bleiben; `CaseBriefing.extras` ist optional.
- **UI:** Briefing-Seite zeigt die A4-Vorschau (sandboxed iframe), «PDF herunterladen», «Fallbericht aktualisieren», «In neuem Tab öffnen und drucken» (Browserdruck bleibt Fallback). Die frühere React-Ansicht liegt unter «Frühere Detailansicht (technisch)». Phase 3: «Fallbericht erstellen / ansehen / aktualisieren» und «PDF herunterladen» je nach Zustand; der Übergabestatus bleibt getrennt.
- **Abhängigkeiten:** `jinja2`, `pypdf`, `playwright` (nur der Python-Treiber; kein Browser-Download nötig), dev: `pymupdf`. Der Browser wird gefunden über `LEXTEC_PDF_BROWSER`, PATH, Standardpfade (Chrome/Edge unter Windows/macOS/Linux) oder den Playwright-Cache. Ohne Browser meldet die API «PDF nicht verfügbar» (503), die Vorschau und der Browserdruck funktionieren weiter.

## 3. Wie Falldaten ins Template gelangen

`view.build_view()` ordnet nur um, was gespeichert ist: Fakten (Herkunft je Wert), Entscheidung/Regeln, Prüfpunkte, Hinweise, Quellen (Fedlex-Status), Fachstellen und Safety aus dem Backend. Es enthält keine Entscheidungslogik, keine KI und keine Schätzung. Daten anderer Fälle werden nie einbezogen (Test).

## 4. Fehlende Angaben und Herkunft

Fehlend wird als **«Fehlt»** mit Grund angezeigt («nicht erfasst», «nicht erfragt», «gefragt, unbekannt», «unklar»), nie als Wert. Herkunft je Wert: Angabe, KI (gestrichelt, «nicht bestätigt»), bestätigt, Unterlage, abgeleitet. Menschliche Korrekturen haben Vorrang, weil der Bericht die gespeicherten (geschützten) Fakten abbildet. Personalien (Name, Telefon, …) und Vertragsdaten ohne Fakt in der Wissensbasis (Vermieter, Mietbeginn, Kaution, …) werden **nicht** erfasst und deshalb als fehlend markiert; sie verändern weder die ASK-/ESCALATE-Logik noch erzeugen sie Pflichtfragen.

## 5. Dringlichkeit, Ampel und Safety

Die Ampel ist eine reine **Abbildung** des Backend-Ergebnisses: Dringlichkeit HIGH → Rot, MEDIUM → Orange, LOW → Grün; ESCALATE/ASK nie Grün; Safety IMMEDIATE → Rot «Sofort handeln» (nie niedriger als die Safety-Entscheidung), HUMAN_CHECK mindestens Orange. Bei akuter Gefahr steht der Sicherheitsbanner (Überschrift, Notrufnummern 144/117, Beratung 143/147/142 getrennt, Sofortschritte, Hinweis «Der Bericht ersetzt die Kontaktaufnahme nicht») **vor** dem Titel und der juristischen Einschätzung.
**Abweichung von `case_summary_v1.yaml` (Law-Team entscheidet):** Dort berechnet die Ampel aus Tagen bis Fristende (≤ 10 Tage Rot, ≤ 20 Amber), Haftungs-Flags und Anzahl fehlender Angaben. Das würde ein Fristende voraussetzen und eine zweite Regel-Engine einführen. Es gilt die getestete Backend-Engine (Dringlichkeit aus Produktschwellen, Safety). `deadline.days_left`, `liability_flag` und `missing_critical_count` werden nicht ausgewertet.

## 6. Fristen

Der Bericht berechnet **kein Fristende** und nennt keine Resttage. Er zeigt das dokumentierte Empfangsdatum bzw. die abgeleiteten internen Tage, die allgemeine gesetzliche Frist (aus den freigegebenen Hinweisen mit Quelle), die interne Dringlichkeit und den Hinweis «Das Fristende prüft und berechnet die Fachperson». `render_summary.py` rechnete Fristende und Resttage; das wurde bewusst nicht übernommen (Tests prüfen, dass kein Datum «Empfang + 30 Tage» erscheint). Hinweis: Der Beispieldatensatz der Vorlage enthält in seinen eigenen Texten ein Fristende; das sind Eingabedaten der Vorlage, nicht vom Renderer berechnet.

## 7. Dokumentenfunktionen (Stand)

LexTec Bridge hat **keinen Dokumentupload** und keine Dateiablage. Der Bericht erfindet daher keine Dokumente: «Keine Unterlagen im System», fehlende Dokumenttypen laut Wissensbasis als «fehlt», als «belegt» markierte Angaben als Hinweis, und ein Dokumentenverzeichnis, das ausdrücklich die fehlende Funktion nennt. Scans, Seitenzahlen, OCR-Qualität, Fundstellen und das Anhängen von PDFs sind nicht umgesetzt (die Vorlage sieht sie vor). Die Muster-Scans der Vorlage erscheinen nie in echten Berichten (sie werden nur vom generischen Test gerendert). Eine Upload-Schnittstelle bräuchte eine eigene Entscheidung (Speicherung, Datenschutz).

## 8. PDF-Export

`render.py` (Jinja2 `SandboxedEnvironment`, Autoescape, Daten nur als Werte) → `pdf.py` (Playwright-Treiber + installiertes Chrome/Edge, A4, Hintergrund, Fusszeile mit Fall-ID und «n / N», Metadaten) → Download `Fallbericht_<Fall>_v<Version>.pdf`. Netzwerkzugriffe der Seite werden blockiert; Schrift und Logo sind eingebettet; die Seitenzahl ergibt sich dynamisch aus dem Inhalt. Die HTML-Vorschau nutzt dieselbe Vorlage.

## 9. Neue Issues

1. Issue in der Wissensbasis anlegen (Fakten, Regeln, `briefing_profile`, Quellen); der Bericht übernimmt Gruppen, Prüfpunkte, Unterlagenliste automatisch.
2. Optional in `knowledge_base/report/report_profile.yaml` einen Abschnitt für die Eckdaten auf Seite 1 ergänzen (Zeilen mit `fact_id` oder ohne = «nicht erfasst»). Das Laden prüft, dass die Fakten existieren.
3. Fachstellen kommen aus `referral_network.yaml`; Safety aus der Safety-Engine. Kein Code nötig.

## 10. Vom Law-Team abzustimmen

1. Ampel: Abbildung der Backend-Dringlichkeit statt der Fristregeln aus `case_summary_v1.yaml` (Abschnitt 5).
2. Fristende nicht berechnen (Abschnitt 6) bzw. ob/wie die Frist künftig angezeigt werden soll.
3. Personalien-/Vertragsfelder (Name, Telefon, Vermieter, Mietbeginn, Kaution, Referenzzinssatz …): heute nicht erfasst; sollen sie erfasst werden (und wie, ohne neue Pflichtfragen)?
4. Dokumentupload, Dokumentenverzeichnis und Scan-Anhang (Abschnitt 7).
5. Notizen-Block auf Seite 2 statt Seite 1; Prüfpunkt-Zustände («Regel ausgelöst, menschliche Prüfung nötig» / «Offen»); Umlaut-Korrektur der Kontaktdaten nur für die Anzeige.
6. Das Logo (PNG aus der Vorlage); für beste Druckqualität das SVG.

## 11. Tests

`tests/test_report.py`: echter Datenbankfall (C), wenige Daten (D), Safety (E), mehrere Issues (F), Chronologie/Fristen, Versionierung (H), Escaping/XSS, Ampel-Abbildung, generische Vorlage mit `case_sample.json` (A), `bridge_fall_0011.json` gegen die gelieferte Referenz-PDF (B: Fall-ID, KB-Version, Entscheid, Übergabe, alle 15 Quellen, Stellen, Ampel), echte PDFs (A4, Seitenzahlen, Fusszeile, Links, Umlaute, Logo, keine leeren Seiten, lange Texte, kein Netzwerk). Frontend: `app.test.tsx`/`ux.test.tsx`; Browser: `e2e/*.spec.ts` (Vorschau im iframe, PDF-Download).
