# Fallzusammenfassung (case_summary_v1)

Erzeugt aus den Pipeline-Daten ein PDF für die Sachbearbeitung: Seite 1 mit allen Eckdaten und Ampel,
Seite 2 mit Details, danach Unterlagenverzeichnis und Scans.

## Dateien

| Datei | Zweck |
|---|---|
| `knowledge_base/briefings/case_summary_v1.yaml` | Spezifikation: Felder, Abschnitte, **Ampel-Regeln** (vom Law-Team pflegbar) |
| `templates/case_summary.html.j2` | Layout (Jinja2, A4, Druck-CSS) |
| `render_summary.py` | JSON → PDF (Chrome via Playwright), hängt Original-PDFs unverändert an |
| `sample/case_sample.json` | Fiktiver Musterfall (Format der Eingabe) |
| `sample/make_sample_scans.py` | Erzeugt die fiktiven Muster-Scans |
| `templates/expert_briefing.html.j2` | **Bridge Expert Briefing** im neuen Layout (Daten aus Bridge, Layout der Fallzusammenfassung) |
| `templates/design.css` | Gemeinsames Design (Farben, Typografie, Ampel) für beide Vorlagen |
| `render_briefing.py` | Bridge-JSON → PDF; ergänzt Kontakte aus `knowledge_base/referrals/referral_rules.yaml` |
| `sample/bridge_fall_0011.json` | FALL-0011 aus dem Bridge-Briefing als JSON (Vorschlag für die Schnittstelle) |

## Logo

Das LexTec-Logo als `assets/lextec_logo.svg` (oder `.png`) ablegen. Der Renderer setzt es oben rechts auf jeder Seite ein; ohne Datei erscheint ein Schriftzug.

## Ausführen

```bash
python render_briefing.py sample/bridge_fall_0011.json --out output/Expert_Briefing_FALL-0011.pdf --html output/expert_briefing.html
```

Das HTML (`--html`) kann direkt als Druckansicht in die Bridge-App übernommen werden; im Browser-Druckdialog Kopf- und Fusszeilen ausschalten.


```bash
pip install jinja2 pyyaml pypdf playwright && playwright install chromium
python render_summary.py sample/case_sample.json --out output/Fallzusammenfassung.pdf
```

`CHROME` in `render_summary.py` auf `None` setzen, um Playwrights Chromium zu verwenden.

## Eingabeformat (Kurzfassung)

Jedes Feld ist ein Werte-Objekt oder `null`:

```json
{"v": "CHF 1'640.–", "src": "doc", "ref": "MV S.1", "confirmed": false}
```

`src`: `doc` (aus Unterlage, `ref` = Fundstelle) · `user` (Angabe) · `confirmed` (bestätigt) · `derived` (berechnet).
`null` erscheint als **FEHLT** – es wird nie geschätzt. Aus Unterlagen gelesene, noch nicht bestätigte Werte sind gestrichelt unterstrichen.

## Was der Renderer selbst berechnet

- Dauer seit Mietbeginn, Bruttomiete (Netto + NK)
- Frist-Ende und Resttage (nur Warnsignal; Hinweis bei Ende am Wochenende)
- **Ampel** aus den Regeln in `case_summary_v1.yaml` – erste zutreffende Stufe gewinnt, weitere Treffer erscheinen als «zudem»
- Seitenzahl, ab der der Anhang beginnt (zwei Durchgänge)

Bilder (PNG/JPG) werden im Anhang seitenfüllend eingebettet, PDFs werden unverändert angehängt.
