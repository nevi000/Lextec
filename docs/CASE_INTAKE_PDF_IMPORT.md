# Phase 1: Fallbeschreibung eingeben, PDF-Textimport, Analyseanzeige

## Zweck
Das PDF ist **ausschliesslich eine alternative Eingabe für den Freitext** der Fallbeschreibung (z. B. eine in Word verfasste und als PDF
gespeicherte Schilderung). Es werden **keine** Mietverträge, Kündigungen, Belege oder anderen Beweisdokumente verarbeitet; es gibt keine
Dokumentenverwaltung, kein Datenbankmodell für Dateien und keine Anhänge im Expert Briefing.

## Ablauf
1. «Fallbeschreibung als PDF importieren» → Dateidialog (ein PDF).
2. Browser sendet die Bytes an `POST /api/intake/pdf-text` (Body = rohes PDF; kein Multipart, keine neue Abhängigkeit).
3. Backend (`app/services/intake/pdf_text.py`, `pypdf`, rein lokal) liefert `{text, pages, truncated}`. Es wird nichts gespeichert, es erfolgt
   **kein** KI-Aufruf, kein OCR, kein externer Dienst. Die Bytes liegen nur während des Requests im Arbeitsspeicher.
4. Der Text landet im **gleichen** Textfeld (eine Text-State-Variable). Ist das Feld nicht leer, wird nie still überschrieben:
   «Text aus PDF anhängen» / «Bestehenden Text ersetzen» / «Abbrechen».
5. «Fall analysieren» sendet den Text als normale `DESCRIPTION`-Nachricht – dieselbe Pipeline wie bei getipptem Text (Prefilter, Klassifikation,
   Regelengine). Importierter und getippter Text sind danach nicht unterscheidbar.

## Unterstützt / Limits (`Settings`, überschreibbar per Umgebungsvariable)
* Textbasierte PDFs (auswählbarer Text). Gescannte PDFs: Meldung «Aus diesem PDF konnte kein Text ausgelesen werden …» (kein OCR).
* `PDF_IMPORT_MAX_BYTES` = 10 MB, `PDF_IMPORT_MAX_PAGES` = 30; Text auf 20 000 Zeichen begrenzt (Hinweis «gekürzt»); die Seiten-Extraktion
  bricht bei übermässig viel Text ab. Serverseitig durchgesetzt (auch beim Streamen ohne `Content-Length`).
* Typprüfung am Inhalt (`%PDF-`), nicht am Dateinamen oder Content-Type.
* Fehler (HTTP 422, Code in Klammern): leer (`pdf_empty`), kein PDF (`pdf_invalid_type`), zu gross (`pdf_too_large`), zu viele Seiten
  (`pdf_too_many_pages`), passwortgeschützt (`pdf_encrypted`; nur leeres Passwort wird versucht), beschädigt (`pdf_corrupt`),
  sonstiger Fehler (`pdf_extraction_failed`), kein Text (`pdf_no_text`). Fehlermeldungen enthalten nie Dateiinhalt. Bei einem Fehler bleibt
  der vorhandene Text unverändert.
* PDF-Inhalt ist Daten, nie Anweisung: er wird nur ins Textfeld gelegt und danach wie Benutzertext (untrusted) verarbeitet.

## Analyseanzeige («Fall wird analysiert»)
* Der Text bleibt sichtbar (Textfeld nur `readOnly`), er wird erst geleert, **nachdem** der Server die Nachricht gespeichert hat. Bisher wurde das
  Feld beim Klick sofort geleert (`setDraft("")` vor dem Request) und das Phase-1-Formular fiel zum Spinner im Button zusammen; bei einem
  Netzwerkfehler ging der Text verloren.
* `AnalysisCard`: unbestimmter Fortschrittsbalken, drei Schritte. **Messbar sind nur zwei Ereignisse:** «Anfrage an den Server übergeben»
  (Schritt 1 erledigt) und «Antwort erhalten» (Karte verschwindet, Übergang in die nächste Phase). Schritt 2 läuft, Schritt 3 steht aus –
  ohne Prozentwerte, ohne Timer, der Schritte als erledigt markiert. Nach 20 s erscheint «Die Analyse dauert etwas länger als gewöhnlich.
  Ihre Eingaben bleiben erhalten.» (kein Abbruch). Animationen respektieren `prefers-reduced-motion` (`motion-safe:` und `MotionConfig`).
* Der Button ist während der Analyse deaktiviert; auch Strg+Enter und Formular-Submit lösen keinen zweiten Request aus.
* Fehler: Meldung, Text bleibt, erneutes Absenden ist möglich; wurde die Nachricht gespeichert, bietet die bestehende Leiste «Erneut analysieren» an.

## Einschränkungen
Kein OCR, nur ein PDF pro Import, keine Drag-and-drop-Zone, keine Übernahme von Tabellen-/Layoutstruktur (reiner Text), Leserichtung mehrspaltiger PDFs
kann abweichen – deshalb wird der Text vor der Analyse zur Prüfung angezeigt.

## Tests
`apps/api/tests/test_pdf_import.py` (15: gültig, Umlaute, mehrseitig, leer/ohne Text, kaputt, passwortgeschützt, falscher Typ, zu gross, zu viele
Seiten, Kürzung, keine Speicherung/kein KI-Aufruf, kein Datei-Modell, Pipeline → Issue 7), `apps/web/src/test/intake.test.tsx` (7),
`apps/web/e2e/pdf_import.spec.ts` (2). Keine Tests rufen Gemini auf.
