# LexTec Bridge

AI-assisted legal case **intake, analysis, decision support and expert handover** for Swiss social workers and advisers.

A social worker records a consultation in natural language. LexTec Bridge identifies the legal issues, extracts the stated facts (each linked to the words it came from), finds what is missing, suggests the **one next question**, and decides – with explicit rules, not a language model – whether to **ASK**, **PROCEED** or **ESCALATE** to a human expert. Every case ends in a structured **Expert Briefing**.

> **Not a lawyer.** The system supports information gathering and escalation. The social worker stays in control: every AI-extracted fact can be inspected and corrected, and corrections are never silently overwritten.

> ⚠️ **Prototype with synthetic content.** All legal content in `knowledge_base/` is `DEMO / SYNTHETIC / NOT LEGALLY VALIDATED`. **Do not enter real client data** before data-protection, contractual and access-control reviews (revDSG). In Gemini mode, text is sent to Google's API.

## Features
* **Consultation workspace** (German UI): free-text intake, one prominent *next action* (question / proceed / escalate), a timeline that separates what the user *reported*, what the AI *extracted* and what the system *recommends*, and a fact panel with evidence, correction, confirmation and history.
* **Deterministic decision engine** with rule IDs and reason codes; unknown legal areas or broken rule files escalate, never proceed.
* **YAML knowledge base** maintained by the law team without code changes, with validation tooling and JSON Schemas for editor support.
* **Expert Briefing**: 11 structured sections, versioned, printable (browser *Save as PDF*), reported vs. inferred facts, source verification status (currently always "not verified").
* **Evaluation center** running YAML scenarios against the engine; distinguishes synthetic technical tests from legally validated ones; no fabricated accuracy score.
* **Gemini or mock AI**, strict Pydantic-validated structured output, evidence checked against the stored messages.

## Quick start (Windows)

Prerequisites: Python 3.12+, Node 22+ (Vite 8 needs at least 20.19), optionally [`uv`](https://docs.astral.sh/uv/).

```powershell
git clone <repo> ; cd Lextec
.\scripts\dev.ps1 -Seed        # creates .env, venv, installs deps, migrates DB, seeds 3 synthetic cases, starts both servers
```

| | URL |
|---|---|
| Web app | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

Port 8000 or 5173 already used by another program? `.\scripts\dev.ps1 -ApiPort 8001 -WebPort 5174` (the launcher tells you which process holds the port).

macOS/Linux: `./scripts/dev.sh --seed` (`API_PORT` / `WEB_PORT` env vars). Manual start:

```powershell
cd apps\api;  .venv\Scripts\python.exe -m app.cli migrate; .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
cd apps\web;  npm install; npm run dev
```

**Geführte Demo (Issue 1, Mietkündigung Zürich):** Seitenleiste → *Demo Mietkündigung* → *Demo starten*; Details in [`docs/ISSUE_01_INTEGRATION.md`](docs/ISSUE_01_INTEGRATION.md).

Or try it freely: **Fälle → Neuen Fall erfassen**, then enter e.g. *«Mein Arbeitgeber hat mir gekündigt.»* (→ ASK) or *«Mein Arbeitgeber hat mir gekündigt. Jetzt kann ich meine Miete nicht mehr bezahlen und habe Angst, meine Wohnung zu verlieren.»* (→ ESCALATE, two legal areas).

## Configuration (`.env` in the repo root, created from `.env.example`)

| Variable | Default | Meaning |
|---|---|---|
| `AI_PROVIDER` | `mock` | `mock` (no credentials, deterministic) or `gemini` |
| `GEMINI_API_KEY` | – | required when `AI_PROVIDER=gemini`; never exposed to the browser, never logged |
| `GEMINI_MODEL` | `gemini-3.8-flash` | model id (verified available via the model list) |
| `AI_THINKING_LEVEL` | `LOW` | `MINIMAL` is rejected by gemini-3.8-flash |
| `AI_MAX_CALLS_PER_CASE`, `AI_DAILY_REQUEST_LIMIT`, `AI_DAILY_BUDGET_USD`, `AI_CASE_BUDGET_USD`, `AI_MAX_*_TOKENS_*` | 12 / 30 / 0.50 / 0.10 / see `.env.example` | server-side cost control (application limits, not a Google billing cap) |
| `APP_TODAY` | today | pin the reference date for "days since receipt" |
| `AI_REPHRASE_QUESTIONS` | `false` | let Gemini reword template questions (untested) |
| `DATABASE_URL` | `sqlite:///<repo>/data/lextec.db` | SQLite file (gitignored) |
| `APP_ENV` | `development` | |

### Gemini setup / switching modes
1. Create an API key in Google AI Studio.
2. In `.env`: set `AI_PROVIDER=gemini` and `GEMINI_API_KEY=<your key>` (optionally `GEMINI_MODEL=<model id>`).
3. Restart the API. The sidebar shows **«KI: Gemini (extern)»**; Settings shows the active mode.
4. Back to mock: `AI_PROVIDER=mock`.

Misconfiguration is a clear startup error (missing key) or a visible analysis failure (quota, wrong model, network). The app **never silently falls back to mock** and never fakes an analysis; a failed analysis keeps the message and offers *«Erneut analysieren»*.

## Tests and checks

```powershell
.\scripts\check.ps1          # ruff, KB validation, pytest, typecheck, vitest, production build
.\scripts\check.ps1 -E2E     # + Playwright browser tests (first time: cd apps\web; npx playwright install chromium)
```
Individually: `cd apps\api; .venv\Scripts\python.exe -m pytest` · `cd apps\web; npm test` · `npm run e2e` (uses ports 8100/5273 and a throw-away DB).
No test calls the real Gemini API (tests force the mock provider even if `.env` contains a key). The only real call is the manual `python -m app.cli live-test --confirm` (one request, no retry).

Other commands (in `apps/api`): `python -m app.services.knowledge.cli` (validate KB + run scenarios) · `python -m app.cli seed-demo | migrate | export-schemas`. After API changes: `cd apps/web; npm run gen:api`.

## Repository layout
```
apps/api/        FastAPI, SQLAlchemy 2, Alembic, services (ai, knowledge, rules, decisions, cases, briefings, sources)
apps/web/        React + TS (strict) + Tailwind + TanStack Query; features/* per screen; Vitest + Playwright
knowledge_base/  YAML maintained by the law team (issues, routing, sources, referrals, briefings, tests)
schemas/         generated JSON Schemas for the YAML files (editor validation)
demo_fixtures/   synthetic demo cases
docs/            ARCHITECTURE · KNOWLEDGE_BASE · API · IMPLEMENTATION_STATUS · LEGAL_TEAM_HANDOFF
scripts/         dev / check launchers
```

## Documentation
* [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Implementation status](docs/IMPLEMENTATION_STATUS.md)
* **Law team:** [Knowledge base guide](docs/KNOWLEDGE_BASE.md) · [Handoff checklist](docs/LEGAL_TEAM_HANDOFF.md)

## Project status
Working local foundation: full consultation workflow, persistence, deterministic decisions, briefings, evaluation, mock AI. **Not yet:** real legal content, authentication, semantic citation checking. Fedlex statute retrieval + cache is available (see [Fedlex integration](docs/FEDLEX_INTEGRATION.md)). See [Implementation status](docs/IMPLEMENTATION_STATUS.md) for exactly what is verified.

## Before real client data (outstanding)
Authentication and role-based access · audit logging · retention/deletion policy · data-protection impact assessment and a lawful basis for the external AI API (processing agreement, data location) · encryption at rest · legally reviewed knowledge base · professional-responsibility review of the user-facing wording.
