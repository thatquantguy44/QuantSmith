# Tasks: Pipeline Builder — Intent Compiler, Readiness Review, Manifest Emission

- **Spec:** 0042-pipeline-builder (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-12

## Definition of Done (applies to every task)

- Standard library plus `data_pipeline` only; no dependency added.
- `data_pipeline.py` (`0011`) is imported, never modified.
- DAG validity is decided by `0011`'s own toposort, not a second
  implementation.
- Declared properties are reported as declared, never as verified.
- Deterministic: the same intent always yields the same findings and text.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `StepIntent`, `PipelineIntent`, `ReadinessFinding`, `CompiledPipeline`, `review_readiness`, `compile_intent`, `render_pipeline_manifest`, `to_pipeline`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002 | done | Placeholder-`Pipeline` validation inherits `0011`'s cycle / unknown-dep / duplicate-name rejection. |
| T-002 | Write `tests/test_pipeline_builder.py`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-003 | done | One test per acceptance criterion (AC-001 – AC-010); AC-006 checks the gate's own six regexes. |
| T-003 | Generate and commit the example manifest. | REQ-006 | done | `specs/0042-pipeline-builder/pipeline_manifest.md`, produced by `render_pipeline_manifest`, verified against the live gate (AC-011). |
| T-004 | Wire catalogs, handoff docs, agent, and standard. | REQ-007 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`, `agents/data_engineering/pipeline_builder/instructions.md`, `instructions/pipeline_engineering.md`. |
| T-005 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `readme-sync`, `pipeline-contract`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_dag_order_respects_dependencies_AC_001` | done |
| AC-002 | `test_cycle_is_blocking_finding_not_exception_AC_002` | done |
| AC-003 | `test_unknown_dependency_is_blocking_AC_003` | done |
| AC-004 | `test_missing_contract_flagged_per_step_AC_004` | done |
| AC-005 | `test_all_findings_collected_AC_005` | done |
| AC-006 | `test_manifest_satisfies_gate_keywords_AC_006` | done |
| AC-007 | `test_manifest_states_declared_not_verified_AC_007` | done |
| AC-008 | `test_to_pipeline_runs_on_0011_runner_AC_008` | done |
| AC-009 | `test_to_pipeline_refuses_unshippable_or_unbound_AC_009` | done |
| AC-010 | `test_deterministic_AC_010` | done |
| AC-011 | `hooks/stages/run-stage.sh pipeline-contract` against the committed example | done |
| AC-012 | Direct inspection of `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | done |

## Follow-ups

- Consume a `sources/<id>.yml` entry (`0027`) for a source step's
  connection metadata instead of a caller-supplied string (carried as an
  open question in `spec.md`).
- An executable runtime for `agents/data_engineering/pipeline_deployment/`
  — the remaining handoff edge this spec deliberately stops at.
