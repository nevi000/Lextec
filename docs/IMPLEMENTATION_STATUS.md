# Implementation status

Honest status per area. *Verified* = executed in this repository on the developer's Windows machine (see "How verified"). Nothing here claims legal correctness.

## Implemented and tested

| Area | Evidence |
|---|---|
| YAML knowledge base schema, loader, cross-validation, validation CLI, content-hash KB version | `tests/test_conditions_and_kb.py` (unknown operator, duplicate ids, bad refs, bad action/schema version, broken YAML, …) |
| Rule-condition language (`all/any/not`, 8 operators, 3-valued logic, no `eval`) | `tests/test_conditions_and_kb.py` |
| Deterministic decision engine (ESCALATE > ASK > PROCEED), reason codes, rule trace, fail-safes | `tests/test_decision_engine.py` + 13 YAML scenarios |
| Missing-information engine (required, `required_if`, shared facts, priority order, deferral) | `tests/test_decision_engine.py` |
| Case pipeline, fact merge (contradiction, ambiguity, human-correction protection), persistence across restart, handover state machine, versioned briefings | `tests/test_api_flow.py` |
| AI output validation (fabricated evidence, unknown ids, type coercion) and AI-failure handling (message kept, `FAILED`, retry, no fabricated analysis) | `tests/test_ai_layer.py` |
| Alembic migration from empty DB, incl. missing `data/` directory (regression) | `tests/test_migrations.py` |
| Frontend flows: dashboard, case list/filter, create case, next question + one-click answer, fact dialog + validation + correction, defer needs reason, escalation card, failed analysis banner, briefing rendering | `src/test/app.test.tsx` (Vitest + Testing Library, `fetch` mocked) |
| Browser end-to-end (real API in mock mode + real UI): create → describe → ASK → answer → decision explanation → briefing → reload persistence; escalation with handover; unsupported area; fact correction survives new input; evaluation; KB page | `apps/web/e2e/*.spec.ts` (Playwright/Chromium) |
| Desktop + mobile layout screenshots reviewed | `apps/web/e2e/visual.spec.ts` → `test-results/screens/` |
| Launcher on Windows (`scripts/dev.ps1`): setup, migrations, both servers, proxy, clean shutdown | run manually (incl. on non-default ports) |

## Issue 1 (Kündigung durch die Vermieterschaft) – siehe `docs/ISSUE_01_INTEGRATION.md`

| Status | Inhalt |
|---|---|
| Implemented + tested | 32 Fakten, 22 Eskalationsregeln, 9 freigegebene Hinweise + 7 Prüfpunkte (alle mit Quelle), Zustand «gefragt, unbekannt», abgeleitete Tageswerte (interne Dringlichkeit), Weiterleitung auf Issues 3/4/6 (aktuell «nicht verfügbar»), Unterdrückung von Standardaussagen ausserhalb des Moduls, Statement-Policy (KB-Texte + KI-Freitext), Issue-Briefing, geführte Demo, 48 Szenarien, 124 pytest, 26 vitest, 13 Playwright |
| Cost control | Serverseitige Limits mit Reservierung vor jedem Gemini-Request, Token-/Kosten-Log aus echten Usage-Metadaten, lokale Verarbeitung einfacher Antworten, Single-Flight, Versuchsgrenze (alles getestet mit gefaktem SDK-Client) |
| **Verified against the real API (once)** | `gemini-3.8-flash` existiert für den konfigurierten Schlüssel; ein echter Extraktionsaufruf (Schritte 1–3 des Demofalls): Klassifikation und alle 10 Fakten korrekt, Belege wörtlich, 5094/1367 Tokens, ≈ $0.0089. `MINIMAL`-Denkstufe wird von diesem Modell abgelehnt (HTTP 400) → Standard `LOW`. |
| Juristisch noch zu validieren | alles im Dossier-Stand (DRAFT); offene Prüfpunkte und meine technischen Annahmen: `docs/ISSUE_01_INTEGRATION.md` §8 |
| Technisch offen | BGer-Abruf (BGE bleiben Dossier-Stand), semantische Zitatprüfung; Fedlex-Abruf/Wortlautabgleich ist umgesetzt, siehe [FEDLEX_INTEGRATION.md](FEDLEX_INTEGRATION.md), Issues 3/4/6, Dokument-Upload, Authentifizierung, Gemini über längere Fälle (nur ein Live-Aufruf gemacht) |

## Implemented but not externally verified

* **Gemini in der vollen Pipeline über mehrere Schritte** wurde nicht live durchgespielt (nur ein Aufruf, bewusst kostenbegrenzt). Mit echtem Gemini kann die Formulierung/Vollständigkeit der Extraktion bei anderen Texten abweichen; Validierung und Regeln bleiben deterministisch.
* **`AI_REPHRASE_QUESTIONS=true`**: implementiert (inkl. Policy-Guard), aus, ohne Live-Test.
* **GitHub Actions**: geschrieben, nicht auf GitHub gelaufen. **`scripts/dev.sh`**: nicht ausgeführt.
* Druckansicht: Print-CSS + PDF-Erzeugung über Chromium im Test geprüft (Navigation ausgeblendet, PDF > 20 kB); die Layout-Qualität auf Papier wurde nicht begutachtet.

## Mock-only
* `MockAIProvider` is keyword/regex based. It recognises only the four demo issues (plus a few unsupported areas such as divorce/inheritance/criminal/tax/immigration) and answers to asked questions. It demonstrates the pipeline; it is **not** a model of language understanding.

## Pending legal-team input (nothing legally validated yet)
* Issues 2–4 (Mängel, Arbeitskündigung, Lohn) bleiben **demo/synthetic**. Issue 1 stammt aus dem Law-Dossier (`DRAFT`, keine Freigabe für echte Klienten).
* The global thresholds (`confidence < 0.5`, `> 3` issues) are technical placeholders.
* No Swiss deadline is computed or asserted anywhere.
* The legal/ethical framework document (Sub-Challenge 2) is not part of the code base.
* See `docs/LEGAL_TEAM_HANDOFF.md`.

## Not implemented (explicitly)
* Implemented: Fedlex retrieval (SPARQL + Akoma Ntoso), versioned local cache, wording comparison, sync CLI ([FEDLEX_INTEGRATION.md](FEDLEX_INTEGRATION.md)). Not implemented: semantic citation checking, Bundesgericht/entscheidsuche.ch (BGE stay «Dossier-Stand»), legal interpretation review.
* Authentication / authorisation / audit log / retention policy (local demo mode is labelled as such).
* Out of scope by decision: global safety pre-check, self-harm/crisis detection, mental-health scoring, emergency workflows, automatic notifications.
* Server-side PDF generation; dark mode; UI to confirm/reject a detected legal issue (API stores status, UI does not edit it); per-case pinning of a KB version; editing the case title in the UI (API supports `PATCH`).
* Real contact with professionals. "Handover" is a recorded state only.

## Known limitations
* Fact values are per case, not per issue: two issues that share a fact id share the answer (intended; ids with different meaning must differ).
* A decision is re-evaluated live with the *current* KB; the decision history keeps what was true at the time (with its KB version).
* SQLite, single process; no concurrency control beyond DB transactions.
* Pages are code-split per route; the largest chunk (consultation workspace) is ~190 kB (58 kB gzip).
