# Tasks: Prompt / Context / Harness Engineering Foundation

- **Spec:** 0070-prompt-context-harness-foundation (`spec.md`, `plan.md`)
- **Last updated:** 2026-09-06

## Definition of Done (applies to every task)

- Work matches the approved spec and plan; deviations are recorded before code
  or content changes.
- Every schema and gate validates offline with deterministic fixtures.
- Prompt, context, assumption, evaluation, audit, and replay artifacts use
  explicit schema versions and stable IDs.
- Context access level, caller clearance, source locator, as-of time, freshness,
  and content hash are validated before prompt composition.
- Hosted LLM, local LLM, MCP, and plugin calls are auditable through metadata and
  fixtures without committing credentials or private payloads.
- Replay reports distinguish exact deterministic replay, fixture replay, and
  non-reproducible dependencies.
- Documentation, indexes, tests, and validation evidence are updated in the same
  change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Implement the typed orchestration run envelope schema, parser, serializer, reference validator, and artifact-hash checks. | REQ-001, REQ-009, REQ-010, NFR-001, NFR-002, NFR-005 | todo | Resolve the package-location open question before coding. |
| T-002 | Implement the prompt manifest schema, examples, validator, and field-level failure fixtures. | REQ-002, REQ-010, NFR-001, NFR-005, NFR-006 | todo | Include prompt role layers, variables, hashes, provider constraints, and allowed tools/plugins. |
| T-003 | Implement the context manifest schema, examples, validator, access checks, as-of/effective-time checks, freshness checks, and exclusion records. | REQ-003, REQ-009, NFR-001, NFR-002, NFR-003, NFR-006 | todo | Reuse existing knowledge, memory, market-research, MCP, and source-catalog semantics by reference. |
| T-004 | Implement the assumption ledger schema, validator, disposition history, review/expiry checks, and dependent-artifact checks. | REQ-004, NFR-001 | todo | Assumptions must have owner, evidence, confidence/status, review/expiry, and invalidation trigger. |
| T-005 | Implement the evaluation harness schema and runner for layer-specific checks over envelope, prompt, context, assumptions, tool/plugin calls, model outputs, quant gates, and final artifacts. | REQ-005, REQ-009, REQ-010, NFR-001 | todo | Each layer needs either a deterministic check or an explicit exception. |
| T-006 | Implement the audit event schema, JSONL validator, event relationship checks, and helper for append-only event emission. | REQ-006, REQ-010, NFR-001, NFR-004, NFR-005, NFR-006 | todo | Overrides and approvals require actor and reason; payloads should be locators/hashes/redacted metadata. |
| T-007 | Implement the reproducible replay command and replay report contract, including fixture mode and non-reproducible dependency reporting. | REQ-007, REQ-010, NFR-001, NFR-002, NFR-005 | todo | Do not claim exact replay for hosted LLM calls without a captured fixture or deterministic local path. |
| T-008 | Add gate coverage through `hooks/stages/run-stage.sh` for prompt manifests, context manifests, assumption ledgers, evaluation harnesses, audit events, and replay metadata. | REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-008, REQ-009, NFR-001, NFR-003, NFR-004, NFR-006 | todo | Choose composite or separate gate names before implementation. |
| T-009 | Add templates, examples, README/spec/handoff documentation, and integration notes for deterministic and fixture-backed LLM-eligible runs. | REQ-009, REQ-011 | todo | Examples should not require network access, credentials, private prompts, or private data. |
| T-010 | Add acceptance tests and validation evidence for every AC, run targeted gates, `git diff --check`, and full pytest if runtime or CLI code changes. | NFR-001, NFR-006 | todo | Record exact commands and outcomes here when implementation is complete. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_run_envelope_resolves_artifacts_and_hashes_AC_001` | todo |
| AC-002 | `test_prompt_manifest_rejects_unversioned_hashless_or_unauthorized_AC_002` | todo |
| AC-003 | `test_context_manifest_blocks_access_stale_and_future_known_context_AC_003` | todo |
| AC-004 | `test_assumption_ledger_requires_owner_evidence_review_and_dependents_AC_004` | todo |
| AC-005 | `test_evaluation_harness_covers_every_required_layer_AC_005` | todo |
| AC-006 | `test_audit_events_reject_malformed_relationships_and_unreasoned_overrides_AC_006` | todo |
| AC-007 | `test_replay_command_reproduces_deterministic_fixture_AC_007` | todo |
| AC-008 | `test_replay_uses_llm_fixture_or_reports_non_reproducible_call_AC_008` | todo |
| AC-009 | `test_orchestration_gates_are_discoverable_through_run_stage_AC_009` | todo |
| AC-010 | `test_foundation_references_existing_surfaces_without_owning_them_AC_010` | todo |
| AC-011 | `test_examples_include_deterministic_and_fixture_backed_envelopes_AC_011` | todo |
| AC-012 | Repository gate evidence: `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `secret-scan`, targeted tests, and full pytest if applicable | todo |

## Draft Notes

This task list starts implementation work but does not claim completion. The
current change creates the Draft spec package and roadmap/index entries only.

## Follow-ups

- Decide package location before implementation: `src/quantsmith/pipelines/` for
  consistency or `src/quantsmith/orchestration/` for a cleaner cross-cutting
  boundary.
- Decide whether gate coverage should be one composite gate or separate
  prompt/context/assumption/evaluation/audit/replay gates.
- Decide the minimum envelope profile for exploratory, non-release-bound work.
