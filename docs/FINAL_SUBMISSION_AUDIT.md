# Final submission audit

Stand: `main` nach dem Premium-Frontend-Merge; Audit am 2026-11-08. Alle automatisierten Tests laufen mit der Mock-KI; kein Test ruft Gemini auf.

## A. Executive status

**READY WITH KNOWN LIMITATIONS.** Die Anwendung startet, der gesamte Kernablauf ist getestet, es gibt keine bekannten P0-Blocker. Alle sieben Mietrechts-Issues sind technisch integriert, aber **juristisch nicht freigegeben** (`DRAFT`).

* Verifiziert (automatisiert, Mock-KI): Fallaufnahme, Klassifikation der sieben Issues, deterministische Entscheidung (ASK/PROCEED/ESCALATE), Eskalation, Weiterfragen nach Eskalation, Fachstellen-Auflösung (Zürich, Winterthur, Bülach, ungeprüfte Gemeinde, unbekannte Gemeinde), Fallbericht (HTML/PDF), Sprachbrücke (zwei Browser-Kontexte), PDF-Import der Fallbeschreibung, abgeschnittene/ungültige Gemini-Antworten.
* Nicht automatisiert verifiziert: echtes Smartphone, Gemini-Qualität über viele Texte, GitHub-Actions-Lauf, PDF-Layout auf Papier.
* Offene Blocker: keine. Offene P1/P2-Punkte: siehe H.

## B. Architektur

Modularer Monolith: React/TypeScript-Frontend, FastAPI-Backend, SQLite (Alembic-Migrationen 0001–0005), YAML-Wissensbasis, austauschbarer KI-Provider (Gemini oder Mock). Die KI schlägt Issues und Fakten vor (validiert gegen die Wissensbasis, Zitate werden geprüft); die Entscheidung trifft eine deterministische, dreiwertige Rule Engine. Details: [`ARCHITECTURE.md`](ARCHITECTURE.md).

Verbleibende Architekturrisiken: Eskalationen werden nicht «festgehalten» (die Entscheidung ist eine reine Funktion des aktuellen Zustands; ein unbestätigter, widersprüchlicher Fakt kann ESCALATE vorübergehend zu ASK machen); Sperren der Sprachbrücke sind prozesslokal; Polling statt Push.

## C. Abdeckung der sieben Issues

Gemessen am geladenen Wissensstand (`knowledge_base/legal_issues`): alle Issues sind geladen, klassifizierbar (Katalog), haben Fragen, Prüf- und Eskalationsregeln und sind getestet. Legal-Status überall `DRAFT`.

| Issue | Modul | Fakten | Eskalationsregeln | Prüfregeln | Status |
|---|---|---|---|---|---|
| 1 Kündigung durch die Vermieterschaft | `CH_TENANCY_TERMINATION` | 36 | 23 | 17 | DRAFT |
| 2 Zahlungsaufforderung mit Kündigungsandrohung | `CH_TENANCY_PAYMENT_WARNING` | 37 | 20 | 16 | DRAFT |
| 3 Kündigung wegen Zahlungsverzug | `CH_TENANCY_PAYMENT_DEFAULT` | 45 | 15 | 14 | DRAFT |
| 4 Erstreckung | `CH_TENANCY_EXTENSION` | 38 | 15 | 14 | DRAFT |
| 5 Mängel an der Mietsache | `CH_TENANCY_DEFECTS` | 44 | 25 | 15 | DRAFT |
| 6 Ausweisung und Räumung | `CH_TENANCY_EVICTION` | 29 | 17 | 10 | DRAFT |
| 7 Mietzinserhöhung | `CH_TENANCY_RENT_INCREASE` | 39 | 14 | 16 | DRAFT |

Geprüfte Szenarien (`apps/api/tests/test_release_scenarios.py`, Mock-KI): reine Wohnungskündigung → Issue 1/ASK; reines Arbeitsrecht → «nicht abgedeckt»/ESCALATE; gemischter Fall → Issue 2 verarbeitet, Arbeitsrecht getrennt gemeldet, keine synthetischen Regeln; Ausweisung → Issue 6 (nicht Ausländerrecht); Schimmel im Kinderzimmer → Issue 5/ESCALATE (`DEFECTS_H1_HEALTH_REPORTED`), keine medizinische Schlussfolgerung; Räumungsentscheid → ESCALATE (`EVICTION_DATE_SET_OR_TODAY`); Zahlungsverzug → ESCALATE (`PAYMENT_DEFAULT_TERMINATION_IMMEDIATE`); kleiner Mangel → ASK ohne Notfall; Anweisung im Falltext ändert die Entscheidung nicht.

## D. Testergebnisse

| Prüfung | Ergebnis |
|---|---|
| `ruff check` | bestanden |
| `ruff format --check` | bestanden (116 Dateien) |
| Wissensbasis-Validierung + Szenarien (`python -m app.services.knowledge.cli`) | bestanden (zuletzt 128/128 Szenarien) |
| `pytest` (Backend, vollständiger Lauf, 8 min 58 s) | **532 bestanden, 1 fehlgeschlagen** |
| Behebung des einen Fehlers | `test_cost_control.py::test_budgets_use_worst_case_reservation` nahm den früheren Standardwert von 1500 Ausgabe-Tokens an; der Test pinnt den Wert jetzt explizit (Ursache: Anhebung des Limits auf 4096). Danach `test_cost_control.py`: 19 bestanden. Ein erneuter vollständiger Lauf fand nach dieser Testkorrektur nicht statt. |
| `npm run typecheck` | bestanden |
| Vitest | 91 bestanden (8 Dateien, 37 s) |
| `npm run build` | bestanden |
| Playwright E2E (sequentiell, eigener Port/DB) | 41 bestanden (2,4 min), 0 übersprungen |

Hinweis: Der vollständige `check.ps1`-Lauf brach im Backend-Teil beim erwähnten Test ab; Typecheck, Vitest, Build und E2E wurden danach einzeln und nacheinander ausgeführt (siehe Tabelle).

## E. Sicherheit

* Secrets-Scan über alle getrackten Dateien: keine Treffer (API-Schlüssel, private Schlüssel). `.env`, Datenbanken, `node_modules`, `.venv` sind in `.gitignore` und nicht im Repository.
* `npm audit --omit=dev`: 0 Schwachstellen. Für Python wurde kein Schwachstellen-Scanner ausgeführt (nicht installiert).
* Lokaler `-Lan`-Modus: Vite lauscht im Netzwerk, die API nur auf `127.0.0.1`; Fremdgeräte dürfen nur `/api/bridge/*` und `/api/health` (sonst 403, getestet inkl. `X-Forwarded-For`); Tokens nur als Hash gespeichert, 120 Minuten gültig, widerrufbar, Rate-Limits, `Cache-Control: no-store`, keine Tokens in Logs (getestet). Es werden keine Firewall-Regeln automatisch geändert.
* Bekannte Grenzen: kein HTTPS im lokalen Betrieb, keine Authentifizierung, keine Verschlüsselung der Datenbank, externe KI in Gemini-Modus. Nur für synthetische Daten.

## F. Code-Bereinigung

Geprüft: keine Debug-Ausgaben ausserhalb der CLI (`print` in `app/cli.py` ist beabsichtigt), keine `TODO/FIXME`-Reste, keine KI-typischen Füllkommentare, keine Hinweise auf Werkzeuge im Code. Korrigiert: Formatierung von `test_analysis_robustness.py`; Testannahme in `test_cost_control.py`; Mock-Schlagwörter für kleine Mängel (`issue_keywords.py`). Bewusst unverändert: Architektur, Regeln, Wissensbasis, UI. Es wurden keine Dateien gelöscht.

## G. Dokumentation

README vollständig neu (Englisch; Problem, Lösung, Funktionen, Mermaid-Diagramm, Scope-Tabelle, Setup, Tests, Demo-Szenarien, Safety, Einschränkungen, Team, KI-Hinweis, Lizenzstatus). Aktualisiert: `IMPLEMENTATION_STATUS.md`, `API.md`, `KNOWLEDGE_BASE.md`. Neu: dieses Audit. Die Entwicklungsprotokolle (Integrations-, UX- und Pitch-Dokumente) wurden für die öffentliche Version entfernt und bleiben in der Git-History erhalten. Der Startbefehl `.\scripts\dev.ps1 -Seed -ApiPort 8001 -WebPort 5174` wurde geprüft (Seed erzeugt drei synthetische Fälle: Arbeitsrecht/«nicht abgedeckt», gemischter Fall, Mängel).

## H. Offene Punkte

| Schweregrad | Bereich | Auswirkung | Nächster Schritt | Blockiert Demo? |
|---|---|---|---|---|
| P1 | Juristische Freigabe | alle Inhalte `DRAFT` | Law-Team-Prüfung (`ISSUE_COVERAGE_MATRIX.md`, `KNOWLEDGE_BASE.md` §12) | nein |
| P1 | Referral-Daten | 150 Gemeinde-Sozialdienste nicht einzeln verifiziert (so angezeigt) | Prüfliste des Law-Teams | nein |
| P1 | Sprachbrücke | nur mit Browser-Kontexten getestet, kein echtes Smartphone; Adresse wird beim Start des Skripts festgelegt (nach WLAN-Wechsel Neustart nötig) | manueller iPhone-Test; optional dynamische Adresse | nein |
| P1 | Gemini-Limits | Standard 30 Anfragen/Tag in `.env.example` | für die Demo `AI_DAILY_*` erhöhen | ja, falls vergessen |
| P2 | ESCALATE-Persistenz | keine «Klinke» (siehe B) | explizite Regel nach Law-Team-Entscheid | nein |
| P2 | CI | GitHub-Actions-Workflow nie auf GitHub beobachtet | nach Push prüfen | nein |
| P2 | Lizenz, Team | keine `LICENSE`, Teamnamen fehlen im README | vom Team ergänzen | nein |
| P2 | Test | nach der Testkorrektur kein erneuter vollständiger Pytest-Lauf | vor Abgabe `.\scripts\check.ps1 -E2E` einmal laufen lassen | nein |
