# UX- und Marken-Refinement

Gezieltes Refinement auf Basis von [UX_SIMPLIFICATION.md](UX_SIMPLIFICATION.md). Keine Änderung an Gemini, Regeln,
Knowledge Base, Fedlex, Datenbank, Briefing-Generator, Briefing-Struktur oder PDF-Ausgabe.

## Marke (analysiert auf lextec-rechtsberatung.ch)

| Wert | Quelle der Website | Verwendung in der App |
|---|---|---|
| Grün `#4A915C` (`--brand-green`) | Akzent der Website | `brand-500`: Akzentleisten, Logo-Umgebung |
| Dunkelgrün `#3A724B` | Hover-Grün der Website | `brand-600`: Hauptbuttons, aktive Elemente (weisser Text erreicht AA-Kontrast; `#4A915C` allein nicht) |
| Dunkel `#1E1C1C` (`--brand-dark`) | Header/Footer | Navigation (`brand-900`) |
| Text `#1A1A1A`, Grau `#6B7280` | Text der Website | `ink`, `ink-subtle` (`ink-muted #4B5563` für Lesbarkeit) |
| Flächen `#F9F9F9`, `#F1F1F1` | Hintergründe | `canvas`, `sunken` |
| Schriften | Manrope (Überschriften), Inter (Text) | `font-display` (Manrope Variable), `font-sans` (Inter Variable), lokal via `@fontsource-variable`, kein Google-CDN |

Radien (Website: 1 rem Karten, Pill-Buttons) wurden für eine Arbeitsanwendung ruhiger gewählt: Karten 10 px, Buttons 8 px,
Chips 6 px. Keine Gradients, keine Glows; Schatten nur als Haarlinie. Rot ist ausschliesslich für Dringendes reserviert,
Amber für normale Hinweise, Grün für Marke und Hauptaktionen. Status wird immer mit Text (und Icon) vermittelt, nie nur mit Farbe.

## Logo

Eingebunden ist das weisse LexTec-Wortmarken-Asset der Website
(`https://lextec-rechtsberatung.ch/wp-content/uploads/2026/01/lextec-logo-white.png`, 1888 × 446 px, transparenter
Hintergrund). Es liegt **lokal** unter `apps/web/public/brand/lextec-logo-white.png` (kein Hotlink) und steht auf der dunklen Navigation.
Darunter steht «Bridge» als Produktzusatz. **Offen:** Es ist ein PNG, kein SVG. Für beste Schärfe und Druck bitte das
SVG-Original bei der Marke anfordern und als `public/brand/lextec-logo.svg` ersetzen. Ich habe die Nutzungsberechtigung nicht
geprüft; da es sich um das Logo Ihrer eigenen Marke handelt, wurde es verwendet. Bitte bei externer Veröffentlichung bestätigen.

## Phase 3 «Nächste Schritte» (neu)

Drei klar getrennte Bereiche (`NextSteps.tsx`):

1. **Einschätzung** («Was empfiehlt LexTec Bridge?»): Überschrift, ein Erklärsatz, höchstens die zwei wichtigsten Gründe,
   «Empfohlene Fachperson» und Dringlichkeit. Bei hoher Dringlichkeit steht oben ein roter Hinweis: «Bitte nehmen Sie umgehend
   Kontakt mit einer geeigneten Fachperson auf. Ein Fallbericht ersetzt diese Kontaktaufnahme nicht.» Der Status steht nur einmal
   (Überschrift); die Kopfzeile zeigt nur Übergabe-/Abschluss-Status. «Rechtliche Details ansehen» (eingeklappt) enthält alle Regeln,
   Rule-IDs, Reason Codes, Dringlichkeiten, Verweise und den Link zur Entscheidungsbegründung.
2. **Ergänzende Angaben (optional)**: «Möchten Sie den Fall noch ergänzen?», Anzahl tatsächlich verfügbarer Fragen
   (Backend: `missing_facts` + `optional_open_facts`, ohne zurückgestellte), Button «Ergänzende Fragen beantworten». Dann genau eine Frage
   mit «Antwort speichern und weiter», «Weiss nicht», «Überspringen» (bestehende Zurückstellung, Grund «Bei der Fallaufnahme
   übersprungen») und «Ergänzung beenden». «Andere Informationen ergänzen» öffnet das Freitextfeld (normale Gemini-Pipeline); es ist in Phase 3 nicht dauerhaft sichtbar.
   Welche Regel nach einer Antwort greift, entscheidet allein das Backend.
3. **Fallbericht**: einzige Hauptaktion. «Fallbericht erstellen» → «Fallbericht ansehen» (aktuell) → «Fallbericht aktualisieren»
   (`briefing_stale` vom Backend; der letzte Bericht bleibt per Link erreichbar). Fehler zeigen eine verständliche Meldung, nichts geht
   verloren, der Button bleibt erneut nutzbar. **Übergabestatus verwalten** (eingeklappt) bleibt getrennt: empfohlen / angefragt / bestätigt;
   ein Fallbericht ändert diesen Status nie.

Kein Sticky-Button: Die Hauptaktion steht direkt nach den (eingeklappten) Bereichen und wäre sonst ein zweiter konkurrierender Button.

## Weitere Änderungen

- Neuer Fall: kein Status vor der ersten Analyse («Noch nicht gestartet» in der Liste, nichts im Fallkopf).
- Phasenanzeige als ruhige Textleiste mit Unterstrich; «Fragen klären» zeigt nur dann ein Häkchen, wenn nichts Erforderliches offen ist.
- Fallkarte kompakt: erkanntes Problem, kurze KI-Zusammenfassung; keine Anzahl erfasster Angaben.
- Briefing-Seite: nur Texte/Navigation («Fallbericht erstellen/aktualisieren», «Zurück zum Fall», Hinweis auf veralteten Stand, ältere Versionen bleiben). Briefing-Inhalt, Struktur, PDF unverändert.
- Komponenten: Design-Tokens in `src/styles/index.css`; angepasst `Button`, `Badge`, `AppShell`, `CaseList`, `CaseSummary`, `PhaseStepper`, `NextSteps` (neu), `NextActionCard`, `QuestionForm`, `WorkspacePage`, `BriefingPage` (nur Texte).

## Tests

`ux.test.tsx` (Phase-3-Bereiche, dringender Hinweis, optionale Fragen: starten/überspringen/beenden, Fallbericht
erstellen/ansehen/aktualisieren, Fehler, Bericht ≠ Übergabe, nur GET bei UI-Interaktion), `e2e/phase3.spec.ts` (Neuer Fall,
normale und dringende Eskalation, optionale Fragen, Bericht + Update + Versionen, Mobile ohne Überlauf), Backend-Test: Lese-Endpunkte rufen nie die KI.

## Einschränkungen

- Eine eigene Darstellung für «akute persönliche Gefahr» gibt es nicht: Das Backend liefert dafür kein separates Signal in der UI. Dringlich (HIGH) wird rot, alles andere ruhig dargestellt.
- Das Logo ist ein PNG (siehe oben). Die Anzahl ergänzender Fragen stammt unverändert aus dem Backend und kann bei wenigen erfassten Angaben hoch sein.
- Der Briefing-Inhalt wurde bewusst nicht an die neue Markenfarbgebung angepasst, ausser durch die globalen Design-Tokens.
