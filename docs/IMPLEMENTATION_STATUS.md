# Implementation status

Honest status per area. *Tested* = covered by automated tests that were executed (results: [FINAL_SUBMISSION_AUDIT.md](FINAL_SUBMISSION_AUDIT.md)). Nothing here claims legal correctness: all seven tenancy issues have `content_status: DRAFT` (not legally approved).

## Implemented and tested

| Area | Evidence |
|---|---|
| Knowledge-base schema, loader, cross-validation, validator CLI, content-hash version; referral file v1.2 validation (160 municipalities) | `test_conditions_and_kb.py`, `test_referral_v12.py` |
| Rule-condition language (`all/any/not`, typed operators, three-valued logic, no `eval`) and deterministic decision engine (ESCALATE > ASK > PROCEED, reason codes, rule trace, fail-safes) | `test_conditions_and_kb.py`, `test_decision_engine.py`, 128 YAML scenarios |
| Seven tenancy issues (loaded, classifiable, questions, rules, escalation) | `test_issue01.py`, `test_issues_2_7.py`, `test_classification_regression.py` |
| Scope control: unsupported areas, mixed cases, synthetic issues excluded from classification | `test_scope_mixed_domains.py`, `test_release_scenarios.py` |
| Case pipeline, fact merge (contradiction, ambiguity, human-correction protection), persistence, handover state, versioned briefings | `test_api_flow.py`, `test_briefing_alignment.py`, `test_report.py` |
| Further fact collection after ESCALATE | `test_intake_after_escalation.py` |
| AI output validation, failure handling, truncated/invalid Gemini answers (one bounded retry, no repair), cost control | `test_ai_layer.py`, `test_analysis_robustness.py`, `test_cost_control.py` |
| Safety signals and referral routing (Zurich municipalities, verification status) | `test_safety.py`, `test_referral_v12.py` |
| Fedlex retrieval, cache and wording comparison | `test_fedlex.py` |
| PDF import of a written case description (text only, nothing stored) | `test_pdf_import.py`, `intake.test.tsx`, `pdf_import.spec.ts` |
| Multilingual QR Sprachbrücke (one session per case, worker confirmation, reconnect, translation errors, remote restriction) | `test_voice_bridge.py`, `test_bridge_stability.py`, `bridge*.test.tsx`, `voice_bridge.spec.ts` |
| Question wording audit for all seven issues | `test_question_quality.py` |
| Frontend flows (case list, phases 1–3, question types, facts, briefing) | Vitest and Playwright (`apps/web/src/test`, `apps/web/e2e`) |
| Migrations from an empty database | `test_migrations.py` |
| Windows launcher (`scripts/dev.ps1`, incl. `-Lan`) | run manually; `scripts/check.ps1` runs all automated checks |

## Implemented, not externally verified

* **Gemini in longer sessions**: the pipeline was exercised live only with a few calls (one long synthetic case after the truncation fix). Output quality on other texts may differ; validation and rules stay deterministic.
* **Real smartphone**: the Sprachbrücke is tested with separate browser contexts and over the LAN address from the same machine; a real phone test is the team's manual check.
* **GitHub Actions** workflow is written but has not been observed running on GitHub. `scripts/dev.sh` was not executed.
* **PDF layout on paper** was not reviewed (PDF generation is tested).

## Mock only

* `MockAIProvider` is keyword-based (issue patterns in `issue_keywords.py`, a few unsupported areas, answers to asked questions) and marks translations as `[XX · Mock]`. It demonstrates the pipeline; it is not language understanding.

## Pending legal-team input

* All seven issues are `DRAFT`; open review points per issue: [ISSUE_COVERAGE_MATRIX.md](ISSUE_COVERAGE_MATRIX.md), [KNOWLEDGE_BASE.md §12](KNOWLEDGE_BASE.md#12-offene-entscheide-für-das-law-team).
* Global thresholds (confidence < 0.5, more than 3 issues) are technical placeholders.
* No Swiss deadline is computed or asserted anywhere.
* Referral data: 150 municipal social services are marked `to_verify`; the law team must verify them individually.
* The legal/ethical framework document (Sub-Challenge 2) is not part of the code base.

## Not implemented

* Authentication, authorisation, audit log, retention policy (local demo mode is labelled as such).
* Semantic citation checking; Bundesgericht retrieval (BGE stay at dossier status).
* Real contact with professionals: "handover" is a recorded state, nothing is sent.
* Document upload of evidence (only the written case description can be imported as text).
* Out of scope by decision: mental-health scoring, emergency workflows, automatic notifications.
* Dark mode, server-side per-case pinning of a knowledge-base version, editing the case title in the UI.

## Known limitations

* Fact values are per case, not per issue: issues that share a fact ID share the answer (intended).
* A decision is re-evaluated live with the current knowledge base; the decision history keeps what was true at the time (with its version).
* SQLite and a single API process; the Sprachbrücke keeps its locks in process memory.
* The Sprachbrücke uses plain HTTP on the local network (synthetic data only) and polls every 2 seconds.
