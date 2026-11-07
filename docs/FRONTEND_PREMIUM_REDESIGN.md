# Frontend Premium Redesign (Branch `feat/premium-frontend-redesign`)

Geschützter Ausgangsstand: Branch `backup/pre-premium-redesign` (= Commit `14e030e`, unverändert). Der Branch wurde **nicht gepusht**; `main` ist unberührt.
Umfang: **nur Frontend** (`apps/web`) und diese Doku. Backend, Wissensbasis, API-Verträge, Logo und gespeicherte Fälle sind unverändert.

## Gefundene Probleme (Audit)
* Lange Stapel gleich grosser weisser Karten ohne klare Hierarchie; die aktive Frage stand nicht im Zentrum.
* Sprachbrücke stand vor der eigentlichen Empfehlung (Phase 3) und wirkte wie ein weiteres Haupt-Panel.
* «noch N Angaben offen» wirkte wie eine Pflichtlast (die Zahl zählt offene Angaben, nicht Pflichtfelder).
* Inhaltsspalte war nicht an Titel und Phasenleiste ausgerichtet; schmale Fliesstextspalte; flache Schatten, kaum Tiefe.
* Antwortoptionen wirkten wie einfache Buttons; Typografie ohne klare Stufen.

## Designrichtung
Zurückhaltend, ruhig, präzise: LexTec-Grün und dunkle Navigation bleiben, Logo unverändert (`/brand/lextec-logo-white.png`). Keine neuen Schriftdateien (weiter Manrope + Inter lokal).

## Designsystem (`src/styles/index.css`, `components/ui`)
* Tokens: Canvas leicht grünlich-neutral (`#f6f7f5`), Linien/«sunken» angepasst, Radien 12/16, zweilagige Schatten (`--shadow-card`, neu `--shadow-raised`).
* Typografie: Basis 14,5 px, Überschriften `text-wrap: balance`, Fliesstext `pretty`, Silbentrennung nur in Absätzen (nicht in Überschriften/Fragen), lange deutsche Wörter brechen statt zu überlaufen.
* Buttons: `rounded-lg`, definierte Übergänge, haptisches Press-Feedback, `secondary` mit Brand-Hover; `prefers-reduced-motion` unverändert global respektiert.
* PageHeader/EmptyState/Card: grössere Titel, ruhiger Leerzustand mit Ring-Icon.

## Geänderte Komponenten
`AppShell` (breitere Sidebar, aktiver Navigationsbalken, Datenschutz-/KI-Hinweis als kompakte Karte, breitere Inhaltsspalte), `PhaseStepper` (nummerierte Pillen, gleiche Semantik `aria-current`), `CaseList` (Zeilen mit Display-Titel und Hover-Pfeil), `Composer` (Phase 1: grössere Eingabe, klarere Typografie), `NextActionCard` + `QuestionForm` (Frage 22–24 px als Zentrum, Auswahl als Radio-Karten mit Haken, Aktionsleiste abgesetzt), `CaseSummary`, `WorkspacePage` (eine ausgerichtete Spalte, Sprachbrücke nach der Hauptaktion), `BridgePanel` (inaktiv als ruhiger Einstieg, aktiv hervorgehoben, Antwortkarte), `MobileBridgePage` (Logo, grössere Typografie und Touch-Flächen).

## Workflow-Verbesserungen
* Phase 1: Eingabe ist Mittelpunkt, PDF-Import bleibt sekundär (kein Dokumentenmanagement).
* Phase 2: «Eine Frage nach der anderen» statt «noch N Angaben offen»; die Zahl bleibt als Tooltip und für Screenreader erhalten, Fragenlogik unverändert. Weiss nicht / Später beantworten bleiben sichtbar.
* Phase 3: Entscheidung und Anlaufstellen zuerst, Sprachbrücke danach; Hinweise zu DRAFT, unverifizierten Kontakten und nicht abgedeckten Gebieten unverändert.
* Sprachbrücke: ruhiger Aktivierungs-Einstieg, kompakter Status nach Verbindung, hervorgehobene Antwortprüfung; Übersetzungs- und Verbindungsstatus unverändert wahrheitsgetreu.

## Responsiv und Barrierefreiheit
Eine Spalte mit max. 880 px für den Fallablauf, Container bis 1200 px; Umbruch langer Wörter; Touch-Flächen ≥ 48 px (Handy 64 px); RTL (Arabisch) unverändert (`dir`, logische Eigenschaften); Fokusring und `aria`-Rollen unverändert; Auswahl nicht nur über Farbe (Haken-Symbol). Geprüft per Screenshot bei 1440 px und 390 px.

## Tests
Typecheck sauber; Vitest 91 bestanden; Produktions-Build ok; Playwright 41 bestanden (inkl. Phase 1–3, PDF-Import, Sprachbrücke mit zwei Browsern, Eskalation, Referral, Briefing). Ein veralteter Text-Match im Sprachbrücken-E2E («This interview has ended») wurde angepasst.

## Bekannte Grenzen / offen
* Nicht in allen Auflösungen per Screenshot geprüft (1920/1280/1024/360 px offen); das Layout ist fluid, aber nicht einzeln bestätigt.
* Phase 3 ist optisch beruhigt, aber nicht strukturell umgebaut (Entscheidungs-, Fachstellen- und Fallaufnahme-Block bleiben in der bisherigen Reihenfolge; ein Zwei-Spalten-Layout wäre ein grösserer Eingriff).
* Dark Mode, Seitenübergänge und neue Illustrationen wurden bewusst nicht eingeführt.
* Verbesserungen, die Backend-Änderungen bräuchten (z. B. Zählung «Pflicht» vs. «optional» im Entscheidungsobjekt für einen ehrlichen Fortschritt), sind nicht umgesetzt.
