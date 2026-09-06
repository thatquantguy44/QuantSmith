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
| T-001 | Implement the typed orchestration run envelope schema, parser, serializer, reference validator, and artifact-hash checks. | REQ-001, REQ-009, REQ-010, NFR-001, NFR-002, NFR-005 | done | Implemented in `src/quantsmith/orchestration/`; package-location decision resolved in `spec.md` and `plan.md`. |
| T-002 | Implement the prompt manifest schema, examples, validator, and field-level failure fixtures. | REQ-002, REQ-010, NFR-001, NFR-005, NFR-006 | done | Covers prompt role layers, variables, hashes, provider constraints, allowed tools/plugins, and unauthorized request failures. |
| T-003 | Implement the context manifest schema, examples, validator, access checks, as-of/effective-time checks, freshness checks, and exclusion records. | REQ-003, REQ-009, NFR-001, NFR-002, NFR-003, NFR-006 | done | Reuses existing access/source/PIT semantics by reference; context validates before prompt composition. |
| T-004 | Implement the assumption ledger schema, validator, disposition history, review/expiry checks, and dependent-artifact checks. | REQ-004, NFR-001 | done | Assumptions require owner, evidence, confidence/status, review or expiry, dependents, invalidation trigger, and disposition history. |
| T-005 | Implement the evaluation harness schema and runner for layer-specific checks over envelope, prompt, context, assumptions, tool/plugin calls, model outputs, quant gates, and final artifacts. | REQ-005, REQ-009, REQ-010, NFR-001 | done | Each required layer needs a deterministic check, fixture-backed check, or explicit exception. |
| T-006 | Implement the audit event schema, JSONL validator, event relationship checks, and helper for append-only event emission. | REQ-006, REQ-010, NFR-001, NFR-004, NFR-005, NFR-006 | done | JSONL events validate IDs, monotonic timestamps, parent references, fixture hashes, and override/approval reasons. |
| T-007 | Implement the reproducible replay command and replay report contract, including fixture mode and non-reproducible dependency reporting. | REQ-007, REQ-010, NFR-001, NFR-002, NFR-005 | done | `quantsmith-orchestration replay` distinguishes deterministic replay, fixture substitution, and non-reproducible provider calls. |
| T-008 | Add gate coverage through `hooks/stages/run-stage.sh` for prompt manifests, context manifests, assumption ledgers, evaluation harnesses, audit events, and replay metadata. | REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-008, REQ-009, NFR-001, NFR-003, NFR-004, NFR-006 | done | Composite `orchestration` gate wired into `run-stage.sh`; validator emits field-level sub-findings. |
| T-009 | Add templates, examples, README/spec/handoff documentation, and integration notes for deterministic and fixture-backed LLM-eligible runs. | REQ-009, REQ-011 | done | Added `templates/orchestration/`, two hash-checked examples, README/spec index/handoff updates, and gate-count sync. |
| T-010 | Add acceptance tests and validation evidence for every AC, run targeted gates, `git diff --check`, and full pytest if runtime or CLI code changes. | NFR-001, NFR-006 | done | Evidence recorded below. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_run_envelope_resolves_artifacts_and_hashes_AC_001` | done |
| AC-002 | `test_prompt_manifest_rejects_unversioned_hashless_or_unauthorized_AC_002` | done |
| AC-003 | `test_context_manifest_blocks_access_stale_and_future_known_context_AC_003` | done |
| AC-004 | `test_assumption_ledger_requires_owner_evidence_review_and_dependents_AC_004` | done |
| AC-005 | `test_evaluation_harness_covers_every_required_layer_AC_005` | done |
| AC-006 | `test_audit_events_reject_malformed_relationships_and_unreasoned_overrides_AC_006` | done |
| AC-007 | `test_replay_command_reproduces_deterministic_fixture_AC_007` | done |
| AC-008 | `test_replay_uses_llm_fixture_or_reports_non_reproducible_call_AC_008` | done |
| AC-009 | `test_orchestration_gates_are_discoverable_through_run_stage_AC_009` | done |
| AC-010 | `test_foundation_references_existing_surfaces_without_owning_them_AC_010` | done |
| AC-011 | `test_examples_include_deterministic_and_fixture_backed_envelopes_AC_011` | done |
| AC-012 | Repository gate evidence: `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `secret-scan`, targeted tests, and full pytest if applicable | done |

## Implementation Notes

- Runtime package: `src/quantsmith/orchestration/`.
- CLI: `python -m quantsmith.orchestration` and `quantsmith-orchestration`.
- Gate: `hooks/stages/run-stage.sh orchestration`.
- Examples: `examples/orchestration/deterministic_quant_run/` and
  `examples/orchestration/fixture_backed_llm_run/`.

## Validation Evidence

- `PYTHONPATH=src python3 -m quantsmith.orchestration validate --discover examples/orchestration` -> validated 2 orchestration envelopes.
- `PYTHONPATH=src python3 -m quantsmith.orchestration replay --envelope examples/orchestration/deterministic_quant_run/run_envelope.json --json` -> status `replayed`, no findings, no non-reproducible dependencies.
- `PYTHONPATH=src python3 -m quantsmith.orchestration replay --fixture-mode --envelope examples/orchestration/fixture_backed_llm_run/run_envelope.json --json` -> status `replayed`, fixture substitution recorded for `evt-llm-003`.
- `PYTHONPATH=src pytest -q tests/test_orchestration_foundation.py` -> 12 passed.
- `QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh orchestration` -> no findings.
- `PYTHONPATH=src pytest -q` -> 521 passed, 1 skipped, 4 sandbox-only localhost bind errors; rerun outside sandbox completed 525 passed, 1 skipped.
- `QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh spec orchestration docs-link agent-catalog spec-index readme-sync doc-counts handoff-sync ownership persistent-knowledge source-catalog secret-scan` -> no findings.
- `git diff --check` -> no whitespace findings.
- `python3 -m py_compile src/quantsmith/orchestration/foundation.py src/quantsmith/orchestration/replay_cli.py src/quantsmith/orchestration/__init__.py src/quantsmith/orchestration/__main__.py` -> no syntax findings.
