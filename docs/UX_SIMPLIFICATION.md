# UX-Vereinfachung für Sozialarbeitende

Nur die Darstellung wurde vereinfacht. Entscheidungslogik, Regeln, Gemini-Pipeline, Fedlex, Kostenkontrolle,
Briefing-Generator, Briefing-Seite und alle APIs sind unverändert. Die Oberfläche zeigt ausschliesslich Zustände aus
dem Backend an; es gibt keine neuen Rechtsregeln im Frontend.

## Geänderte Screens

| Screen | Vorher | Jetzt |
|---|---|---|
| Navigation | 7 Einträge | **Meine Fälle** und **Neuen Fall erfassen** |
| Startseite `/` | Dashboard mit 5 Statistik-Karten | **Meine Fälle**: ruhige Liste, Suche, Filter Alle / In Bearbeitung / Übergabe / Abgeschlossen |
| Fallbearbeitung `/cases/:id` | 2 Spalten, Sidebar mit eigener Scrollbar, 2 konkurrierende Eingaben | **eine Spalte**, drei Phasen, eine Frage im Zentrum |
| Eskalation | alle Regeln, Codes, Dringlichkeiten auf einmal | kurze Empfehlung, Details aufklappbar |
| Fakten | permanente Sidebar | Dialog **Alle Fallinformationen** |
| Verlauf | lange Karten mit Badges | eingeklappt: **Gesprächsverlauf anzeigen** |
| Briefing, Entscheidungsbegründung | – | **unverändert** (nur der Zugang wurde angepasst) |

### Navigation: was wohin ging
Demo, Evaluation, Knowledge Base, Einstellungen und das Briefing-Verzeichnis sind aus der Sidebar entfernt, aber nicht
gelöscht. Sie sind unter **`/dev`** (Entwicklerbereich) gebündelt; die alten URLs `/demo`, `/evaluation`,
`/knowledge-base`, `/settings`, `/briefings` funktionieren weiter. Ein dezenter Link «Entwicklerbereich» erscheint nur
bei `APP_ENV=development`. Es gibt bewusst kein Rollen- oder Login-System. `/cases` leitet auf `/` um. Die geführte
Demo startet weiterhin ihren Fall (Titel «Demo: Mietkündigung Zürich») und blendet ihre Anleitung nur dort ein.

Der Hinweis auf externe KI-Verarbeitung bleibt in der Sidebar sichtbar («Texte werden … an eine externe KI (Gemini)
gesendet»). Aufrufzähler und Kosten liegen unter `/settings`.

## Der dreiphasige Ablauf

Die Phase wird aus dem Backend-Zustand abgeleitet (`lib/caseStatus.ts: currentPhase`) und ist nur Orientierung, nie eine Sperre.

1. **Situation erfassen**: keine Nachricht vorhanden. Grosses Feld «Was ist passiert?», Button «Situation analysieren».
2. **Fragen klären**: Entscheidung ASK mit Pflichtfrage. Eine Frage im Zentrum, «Warum ist das wichtig?» einklappbar.
3. **Nächste Schritte**: Entscheidung ESCALATE oder PROCEED (auch bei offenen Fragen!) oder nur noch optionale Fragen.
   Eine Eskalation direkt nach der ersten Schilderung zeigt sofort Phase 3.

Nach der Analyse zeigt eine Kompaktkarte «Dieser Fall» das erkannte Problem, die neutrale KI-Zusammenfassung
(als KI-erstellt gekennzeichnet) und «Alle Fallinformationen». Nicht angezeigt: Rohdaten, JSON, Confidence-Prozente,
Reason Codes, Faktenlisten. Ein nicht abgedecktes Problem wird verständlich erklärt, rechtliche Standardhinweise werden
weiterhin unterdrückt.

## Fragen

- **Pflichtfragen**: eine nach der anderen, Reihenfolge und Relevanz bestimmt die Engine (`required_if`, nicht anwendbare
  Felder erscheinen nicht; durch Test abgesichert).
- **Eingabe**: Ja/Nein und Auswahl mit ≤ 4 Werten als Buttons, Datum, Zahl, Text als passendes Feld. Hauptbutton
  «Antwort speichern und weiter».
- **Weiss nicht**: eigene Aktion, wird als «gefragt, aber unbekannt» gespeichert und nicht erneut gefragt.
- **Später beantworten**: sekundär, erfasst wie bisher einen Grund (bestehende Deferral-API).
- **Weitere Informationen aus dem Gespräch ergänzen**: dezenter Link, öffnet das Freitextfeld; läuft über dieselbe
  Pipeline (Gemini → Regeln). Die Frage bleibt die primäre Aktion.
- **Optionale Fragen** (Phase 3): nie automatisch. Hinweis «Optional können Sie noch ergänzende Angaben erfassen» und
  Button «Weitere Fragen beantworten». Dann eine Frage gleichzeitig mit «Weiter», «Weiss nicht», «Überspringen» und
  «Ergänzende Fragen beenden». «Überspringen» nutzt die bestehende Zurückstellung mit dem automatischen Grund
  «Optionale Angabe übersprungen»; zurückgestellte Fragen werden hier nicht erneut angeboten (keine Endlosschleife).
  Die Übergabe ist jederzeit sofort möglich.

## Eskalation und Übergabe

Hauptansicht: Überschrift («Prüfung durch eine Fachperson empfohlen», bei höchster Dringlichkeit «Dringende Prüfung …»),
dann **Was ist das Problem?** (die zwei wichtigsten Gründe, höchste Dringlichkeit zuerst), **Warum braucht es eine
Fachperson?** (allgemein, keine Rechtsauskunft) und **Was sollten Sie jetzt tun?** (empfohlene Anlaufstelle). Es wird nur
die höchste Dringlichkeit gezeigt. Hauptaktion: **Übergabe vorbereiten**.

Aufklappbar unter «Weitere Gründe und rechtliche Details anzeigen»: alle Regeln mit Rule-ID, Reason Code, Issue,
Dringlichkeit, Verweise auf andere Issues, Hauptgrund und der Link zur vollständigen Entscheidungsbegründung.

Übergabestatus (unverändert streng): *empfohlen* (noch niemand kontaktiert) → *angefragt* (Sozialarbeiterin markiert) →
*bestätigt* (mit Notiz). Das System behauptet nie, jemanden kontaktiert zu haben.

## Briefing

«Übergabe vorbereiten» erzeugt das Briefing über die bestehende API und öffnet die unveränderte Briefing-Seite. Existiert
bereits eines, heisst die Hauptaktion «Briefing ansehen». Auch bei offenen Fragen (ASK) erscheint «Briefing ansehen» in
der Kopfzeile, sobald eines existiert. Die Routen `/cases/:id/briefing[/:briefingId]` sind unverändert.

## Wo ist was?

- **Fakten** (bekannt, offen, unbekannt, widersprüchlich, KI vs. bestätigt, Korrektur, Änderungsverlauf): Dialog «Alle Fallinformationen».
- **Quellen / Fedlex**: «Rechtliche Hinweise zu diesem Fall» (aufklappbar, mit Quellenstatus und Fedlex-Link); vollständig im Briefing.
- **Decision Trace**: «Weitere Gründe und rechtliche Details anzeigen» und die Seite «Entscheidungsbegründung».
- **Klassifikations-Wahrscheinlichkeit**: nicht mehr angezeigt (nur noch in den Backend-Daten).
- **Gesprächsverlauf**: eingeklappt am Ende; erkannte Angaben pro Nachricht ebenfalls eingeklappt.

## Unverändert

Gemini-Klassifikation und -Extraktion, Mock-Provider, KB-Loader, YAML-Regeln, Rule Engine (ASK/PROCEED/ESCALATE),
Dreiwertige Logik, Human-Overrides, Rule Trace, Fedlex-Provider und -Cache, Briefing-Generator/-Seite/Druck/Versionen,
Datenbank und Kostenkontrolle. Die UI löst nie selbst Analysen aus: Öffnen von Fakten, Verlauf, rechtlichen Hinweisen
oder Phasenwechsel sendet nur GET-Anfragen (Test `ux.test.tsx`, Backend-Test
`test_read_only_endpoints_never_call_the_ai_provider`).

## Testen

```powershell
cd C:\Users\nevio\Lextec
.\scripts\check.ps1 -E2E                     # alles: ruff, KB, pytest, tsc, vitest, build, Playwright
.\scripts\dev.ps1 -ApiPort 8001 -WebPort 5174   # manuell, http://localhost:5174
```
Manuell: «Neuen Fall erfassen» → Text aus `docs/ISSUE_01_INTEGRATION.md` (Mietkündigung Zürich) einfügen → Frage beantworten
→ «Weiss nicht» → «Alle Fallinformationen» → Eskalation → «Weitere Gründe …» → «Übergabe vorbereiten».

## Bekannte Punkte

- Die KI-Zusammenfassung kann Daten falsch zuordnen; sie ist deshalb als KI-erstellt gekennzeichnet (Prompt nicht geändert).
- Die mobile Ansicht zeigt «Meine Fälle» und «Neuen Fall erfassen» (Hauptbutton auf der Startseite); die Systemhinweise der Sidebar erscheinen dort nicht.
