# API

Base URL `http://localhost:8000` (or the port given to `dev.ps1`) · interactive docs `/docs` · OpenAPI `/openapi.json`. JSON only. No authentication (local demo mode).

## Error format (all endpoints)

```json
{ "error": { "code": "not_found", "message": "Fall nicht gefunden.", "details": null } }
```
`422 validation_error` adds `details: [{ "field": "content", "message": "…" }]`. Other codes: `unknown_fact`, `invalid_value`, `invalid_state`, `empty_patch` (400), `conflict` (409), AI errors `ai_rate_limited` (429), `ai_unavailable` / `ai_invalid_response` (502), `ai_configuration_error` (500).

## Endpoints

### System
| Method & path | Purpose |
|---|---|
| `GET /api/health` | liveness |
| `GET /api/system/status` | AI provider/model, `ai_is_external`, KB version + validity, auth mode, notice |
| `GET /api/ai/usage` | AI usage report: today's calls, tokens, estimated cost, limits, recent calls (no message content); never calls the AI |
| `GET /api/dashboard` | counts derived from stored cases + 6 most recent cases |

### Cases
| | |
|---|---|
| `GET /api/cases?q=&status=OPEN\|CLOSED&action=ASK\|PROCEED\|ESCALATE&sort=updated_desc\|updated_asc\|created_desc` | list; `q` matches display id and title |
| `POST /api/cases` `{title?, description?}` → `CaseDetail` (201) | create; optional first description is analysed immediately |
| `GET /api/cases/{id}` → `CaseDetail` | issues, current decision, handover, analysis state, `briefing_stale` |
| `PATCH /api/cases/{id}` `{title?, status?}` | rename / close / reopen |

`CaseDetail.analysis.status`: `OK` · `PENDING` (messages stored, not analysed) · `FAILED` (AI error, message kept). In those states `current_decision` is the last persisted one or `null`; nothing is fabricated.

### Consultation
| | |
|---|---|
| `GET /api/cases/{id}/messages` | chronological |
| `POST /api/cases/{id}/messages` `{content, kind?: DESCRIPTION\|NOTE, answers_fact_id?, unknown?}` → `{message, analysis, case}` (201) | persists, analyses, re-decides. `answers_fact_id` ties the text to the asked question. **Always 201 if stored, even when `analysis.status=FAILED`.** `409` if the case is closed. |
| `POST /api/cases/{id}/analyze` → `CaseDetail` | retry analysis of `PENDING`/`FAILED` messages |

### Facts
| | |
|---|---|
| `GET /api/cases/{id}/facts` → `FactView[]` | all facts of the active issues (incl. `MISSING`), with `required`, evidence, origin, `confirmed`, `history` |
| `PATCH /api/cases/{id}/facts/{fact_id}` `{value?}` \| `{status: MISSING\|NOT_APPLICABLE}` \| `{confirmed}` + `note?` | human correction (becomes `USER_CORRECTION`, confirmed, never overwritten by AI) |
| `POST …/facts/{fact_id}/defer` `{reason}` / `POST …/undefer` | defer a question (reason ≥ 3 chars); fact stays open |

### Decisions & handover
| | |
|---|---|
| `GET /api/cases/{id}/current-decision` → `DecisionResult \| null` | live deterministic evaluation |
| `GET /api/cases/{id}/decisions` → `DecisionView[]` | history, newest first; a row exists per *changed* outcome |
| `POST /api/cases/{id}/handover/request` | `RECOMMENDED → HANDOFF_REQUESTED` (user marks that they asked; the system contacts nobody) |
| `POST /api/cases/{id}/handover/complete` `{note}` | `HANDOFF_REQUESTED → HANDOFF_COMPLETED`; `409` otherwise |

### Briefings
| | |
|---|---|
| `GET /api/cases/{id}/briefings` | versions, newest first |
| `POST /api/cases/{id}/briefings` → `BriefingView` (201) | new immutable version; `409` while analysis is incomplete |
| `GET /api/cases/{id}/briefings/{briefing_id}` | one version |
| `GET /api/briefings` | latest briefing per case |

### Knowledge base & evaluation
| | |
|---|---|
| `GET /api/knowledge-base/status` | files, validation errors, counts, sources (+ verification status), professionals |
| `GET /api/knowledge-base/issues` | issue summaries |
| `POST /api/knowledge-base/reload` | re-read YAML (dev convenience) |
| `GET /api/evaluation/scenarios` · `POST /api/evaluation/run` | run KB scenarios against the engine (no AI); returns per-scenario expected/actual and mismatches |

## TypeScript types
`apps/web/src/types/api.d.ts` is generated from the OpenAPI schema: `cd apps/web && npm run gen:api`. CI regenerates it and fails on drift.

### Case-description PDF import
| | |
|---|---|
| `POST /api/intake/pdf-text` (raw PDF bytes) → `{text, pages, truncated}` | extracts the text of a written case description; stores nothing, no AI call. Errors `pdf_*` (422): empty, wrong type, too large, too many pages, encrypted, corrupt, no text |

### Sprachbrücke (design and security: [ARCHITECTURE.md](ARCHITECTURE.md#subsystems))
| | |
|---|---|
| `GET/POST /api/cases/{id}/voice-bridge`, `/pause`, `/resume`, `/end`, `/answer/accept`, `/answer/reask`, `/skip`, `/retry-translation` | social-worker side (local machine only) |
| `GET /api/bridge/state`, `POST /api/bridge/language`, `POST /api/bridge/answer` (header `X-Bridge-Token`) | phone side; the only endpoints reachable from other devices |
