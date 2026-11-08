# Architecture

LexTec Bridge is a **modular monolith**: one React SPA, one FastAPI service, a YAML knowledge base and a SQLite database. There are no queues, caches, vector stores or external services other than the (optional) Gemini API.

```
┌───────────────────────┐   /api (Vite proxy)   ┌────────────────────────────────────────────┐
│ apps/web              │ ────────────────────▶ │ apps/api (FastAPI)                         │
│ React + TS + Tailwind │                       │                                            │
│ TanStack Query        │ ◀──────────────────── │  api/routes ─▶ CaseService (pipeline)      │
└───────────────────────┘      JSON             │                  │       │        │        │
                                                │       AIProvider │       │        │ SQLite │
                                                │   (Mock | Gemini)│       │        │ (SQLA) │
                                                │                  ▼       ▼        ▼        │
                                                │   ai.validation ─▶ decisions.engine        │
                                                │                      ▲   (pure, no I/O)    │
                                                │                      │                     │
                                                │   knowledge.loader ──┘  briefings.generator│
                                                └──────────────▲─────────────────────────────┘
                                                               │ reads
                                                   knowledge_base/*.yaml  (law team)
```

## Core principle: language model understands, rules decide

| Concern | Who does it | Where |
|---|---|---|
| Understand free text, find legal issues, extract facts, summarise | LLM (Gemini) or Mock | `services/ai/` |
| Check that model output is trustworthy | Deterministic validation | `services/ai/validation.py` |
| ASK / PROCEED / ESCALATE, reason codes, next question | Deterministic engine | `services/decisions/` |
| Which facts/rules/professionals exist | YAML knowledge base | `knowledge_base/`, `services/knowledge/` |
| Briefing content | Structured state → `CaseBriefing` | `services/briefings/` |

Gemini never sees the decision logic and cannot influence the decision except through facts that pass validation.

## Processing pipeline (`CaseService`)

`POST /api/cases/{id}/messages`:

1. **Persist** the message (own transaction, `analysis_status=PENDING`). Input is never lost.
2. Build `ExtractionInput`: new messages, a bounded window of earlier messages, the *catalog* of issue ids and fact ids from the KB, known facts.
3. **AI extraction** (`AIProvider.extract`) → `ExtractionResult` (strict Pydantic schema). On `AIProviderError` the messages are marked `FAILED`; **no analysis is invented**, the last valid decision stays visible, `POST /analyze` retries.
4. **Validate** (`validate_extraction`): unknown issue/fact ids are dropped; every `evidence_quote` must literally occur (whitespace/case-insensitive) in the referenced stored message, else the item is dropped with a warning; values are coerced to the fact's type, unusable values become `AMBIGUOUS` – never `KNOWN`.
5. **Merge into case state** (`CaseService._merge_fact`) with the rules below.
6. **Decide** (`decisions.engine.decide`) on a `CaseSnapshot`; persist a `decisions` row **only if the outcome changed** (signature hash over action, reasons, rules, missing facts, next question, KB version).
7. Sync the handover recommendation, bump `case.version`, commit.

### Fact merge rules (human control)
* New AI fact, no row → `KNOWN` / `AMBIGUOUS`, origin `AI_EXTRACTED`, evidence + source message stored.
* Existing value differs, AI-sourced and unconfirmed → `CONTRADICTORY` (both values kept) – never silently replaced.
* A **human correction** (`PATCH /facts`) or confirmed value is never overwritten by later AI output (the attempt is logged in `history` as `ai_conflict_suppressed`).
* A direct answer to a question (`answers_fact_id`) resolves ambiguity/contradiction.
* Deferring a question needs a reason, keeps the fact `MISSING`, and only changes question *order*, not the requirement.

## Decision engine (`decisions/engine.py`)

Pure function `decide(kb, snapshot) -> DecisionResult`; same state + same KB version ⇒ same result (tested).

```
active issues  = DETECTED issues known to the KB
unsupported    = UNSUPPORTED issues + DETECTED ids unknown to the KB
missing        = required facts (required | required_if fires) not KNOWN / NOT_APPLICABLE
ctx            = has_user_input, active_issue_count, unsupported_issue_count,
                 min_classification_confidence, contradictory_fact_count, missing_required_count
triggered      = global rules + escalation rules of active issues whose condition is TRUE

triggered or KB global rules unavailable → ESCALATE (missing facts kept as secondary reason)
no input yet                              → ASK (NO_INPUT)
missing                                   → ASK (MISSING_REQUIRED_FACTS [+ AMBIGUOUS/CONTRADICTORY])
otherwise                                 → PROCEED
```

Fail-safes: an invalid YAML file is not loaded ⇒ its issue is "unknown" ⇒ ESCALATE; an unusable global rule file ⇒ ESCALATE (`KB_GLOBAL_RULES_UNAVAILABLE`); unknown condition values never fire rules (three-valued logic, see `docs/KNOWLEDGE_BASE.md` §4).

`DecisionResult` carries: action, main + all reason codes, triggered rules (with text), every evaluated rule with outcome (`FIRED/NOT_FIRED/UNKNOWN`), legal findings, missing facts, next question, recommended professionals, KB version, timestamp.

## Knowledge base loading

`load_knowledge_base(dir)` parses each YAML with Pydantic (`extra="forbid"`), then cross-validates references. It **never raises on content errors**; it returns a `KnowledgeBase` with per-file reports. `kb.version` = SHA-256 over all YAML paths+bytes (`kb-<10 hex>`), stored with every decision and briefing. Hot reload via `POST /api/knowledge-base/reload` (dev convenience).

## Data model (SQLite via SQLAlchemy 2 + Alembic)

`cases` · `case_messages` · `case_issues` · `case_facts` (value JSON, status, origin, evidence, source message, `confirmed`, `deferred_reason`, `conflicting_values`, `history`) · `decisions` (full payload + KB version) · `briefings` (versioned payload) · `handoffs` (`RECOMMENDED → HANDOFF_REQUESTED → HANDOFF_COMPLETED`; completion requires a note and a prior request).

* Migrations only (`alembic upgrade head` at startup, `AUTO_MIGRATE=true`); foreign keys enforced (`PRAGMA foreign_keys=ON`); UTC timestamps.
* JSON columns keep the schema stable while the legal content evolves. Moving to PostgreSQL means changing `DATABASE_URL` and re-running the migration; nothing SQLite-specific is used besides the pragma.

## Briefing

`build_briefing()` maps validated state to the typed `CaseBriefing` (11 sections, order from the `expert_briefing_v1` template). Reported vs inferred is explicit per fact (`provenance`: `REPORTED_BY_AI_EXTRACTION`, `ANSWER_RECORDED`, `CORRECTED_BY_USER`, plus `confirmed`). Sources come from rule references; their verification status is always taken from the `SourceRegistry` (currently `UNVERIFIED`). A briefing is **immutable**; changes produce a new version, and `briefing_stale` tells the UI when the case moved on.

## Frontend

`features/*` per screen, `lib/api.ts` (typed fetch client), `lib/queries.ts` (TanStack Query hooks + one `useInvalidateCase`), `types/api.d.ts` generated from the FastAPI OpenAPI schema (`npm run gen:api`; CI fails if stale). **No business logic in React**: the UI renders `DecisionResult`/`FactView`; it only formats.

## Subsystems

**Gemini robustness.** Structured output (`response_json_schema`); `finish_reason == MAX_TOKENS` is its own error (`ai_output_truncated`) and the JSON is never repaired. At most one targeted retry per extraction (truncation: higher output limit and "be compact"; schema violation: only the offending field paths, never values or case text). Output limits `AI_MAX_OUTPUT_TOKENS_PER_CALL=4096` / retry 8192, timeout 60 s. Every attempt is recorded in `ai_usage`; the input is kept on any failure. Background: a long case once produced about 2.5k output tokens against a 2.5k limit and a cut-off JSON, not a wrong schema.

**Case-description PDF import.** `POST /api/intake/pdf-text` extracts text with `pypdf` into the editable field. Nothing is stored, no AI call, no OCR. Limits and error codes `pdf_*` are in [API.md](API.md). Text from a PDF is treated like typed text: instructions inside it cannot change the outcome.

**Sprachbrücke (multilingual QR intake).** The backend state (`bridge_sessions`) is the single source of truth; both devices poll every 2 s. `BridgeService.sync()` is the only place where the current question changes: it asks `CaseService.current_decision()` for `next_question` and creates a new question instance when the fact ID changes; stale answers are rejected (`409 stale_question`), repeated `request_id`s are idempotent. Phone answers are proposals: the worker accepts, corrects, re-asks or skips, only then they enter the case. No safety-critical question is shown on the phone when the safety state is `IMMEDIATE`. States: `WAITING_FOR_CONNECTION → WAITING_FOR_QUESTION → QUESTION_ACTIVE → AWAITING_WORKER_REVIEW → …`, plus `PAUSED`, `COMPLETED`, `EXPIRED`. Translation runs in the background with a cache; failures are visible and retryable, never silent. Security: QR contains a 256-bit token in the URL fragment (`/bridge#t=…`), only its SHA-256 hash is stored, 120 min validity, one active session per case, rate limits, `Cache-Control: no-store`, no tokens or answers in logs. A token only permits `GET /api/bridge/state`, `POST /api/bridge/language`, `POST /api/bridge/answer`. In `-Lan` mode, requests from non-local sources (client IP or any `X-Forwarded-For` hop) may only use `/api/bridge/*` and `/api/health` (`RESTRICT_REMOTE_ACCESS`); the API itself stays on `127.0.0.1`. Migration `0005` adds `bridge_sessions`, `translation_cache` and origin fields on `case_messages`. Limits: plain local HTTP, polling instead of push, locks are process-local, machine translation is no substitute for an interpreter on legally important points.

**Referral engine v1.2.** Roles are resolved per municipality (160 Zurich municipalities) in a fixed order, with cantonal and national fallbacks. Contacts and the verification state of each body are shown as stored (150 municipal social services are `to_verify`); nothing is invented. Handover is a recorded state, nothing is sent.

**Fedlex integration.** Official federal-law wording is retrieved from `fedlex.data.admin.ch` (HTTPS only, host allowlist, manual redirects, size/time limits, `defusedxml`, validated SR/ELI identifiers; requests contain only public law references, never case data) and cached. Three independent status levels: retrieval (`RETRIEVED`, `RETRIEVED_STALE`, `NOT_FOUND`, `ERROR` …), wording comparison (`MATCHED`, `MISMATCH`, `NO_COMPARABLE_TEXT`, `NOT_COMPARED`; quoted fragments are normalised and searched deterministically, no LLM) and interpretation (`NOT_REVIEWED` unless the law team recorded a review). A retrieved article never proves a legal consequence in a concrete case, so there is no blanket "legally verified". The package imports nothing from the AI layer. Configuration: `FEDLEX_*` in `.env.example`.

## Security / privacy posture (local prototype)
No authentication (clearly labelled), CORS limited to the dev origin, inputs validated by Pydantic, YAML via `safe_load`, no `eval`, no raw HTML rendering, secrets only via environment (`SecretStr`, never returned by the API), logs contain case numbers and error codes but not message content. See `README.md` → "Limitations".
