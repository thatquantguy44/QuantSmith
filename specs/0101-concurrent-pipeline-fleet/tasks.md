# Tasks: Concurrent pipeline fleet

- **Spec:** 0101-concurrent-pipeline-fleet (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-10

> Every task cites a requirement; every acceptance criterion is named by a test.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests exist and pass deterministically (repeat runs green).
- No limit is exceeded under concurrency or retries; no lossy mapping is silent.
- No secrets, credentials, or private data introduced; runtime code lives under
  `src/quantsmith/`.
- Docs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Agent | Notes |
| --- | --- | --- | --- | --- | --- |
| T-001 | Implement `Fleet` validation and deterministic topological order. | REQ-001 | done | `data_engineering/pipeline_concurrency` | Unfittable slot demand rejected. |
| T-002 | Implement `_Admission` and `_select` (all-or-nothing, priority, overtake guard). | REQ-002, REQ-003, NFR-001 | done | `data_engineering/pipeline_concurrency` | Shared by plan and run. |
| T-003 | Implement `run_fleet` with bounded retries through admission and `upstream_failed` cascade. | REQ-004, NFR-001, NFR-003 | done | `data_engineering/pipeline_concurrency` | Error class only. |
| T-004 | Implement `simulate` and `SchedulePlan` (lower bound, utilization, wait attribution). | REQ-005, NFR-002 | done | `data_engineering/pipeline_concurrency` | Deterministic. |
| T-005 | Implement `stagger_offsets`. | REQ-006 | done | `data_engineering/pipeline_concurrency` | Name-stable. |
| T-006 | Implement `to_dagster` and `to_mage` with `warnings`; write the Dagster and Mage profiles and the Mage scheduler adapter. | REQ-007, NFR-003 | done | `tooling/dag_orchestration` | Verify keys per installed version. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `tests/test_pipeline_fleet.py::test_construction_validation_AC_001` | done |
| AC-002 | `tests/test_pipeline_fleet.py::test_limits_hold_under_hundreds_of_pipelines_AC_002`, `::test_slot_weights_respected_AC_002` | done |
| AC-003 | `tests/test_pipeline_fleet.py::test_priority_order_AC_003`, `::test_no_starvation_of_wide_job_AC_003` | done |
| AC-004 | `tests/test_pipeline_fleet.py::test_retries_and_failure_isolation_AC_004`, `::test_retries_stay_within_limits_AC_004`, `::test_dependencies_respected_AC_004` | done |
| AC-005 | `tests/test_pipeline_fleet.py::test_simulation_deterministic_and_attributed_AC_005`, `::test_simulation_names_the_bottleneck_AC_005` | done |
| AC-006 | `tests/test_pipeline_fleet.py::test_stagger_offsets_AC_006` | done |
| AC-007 | `tests/test_pipeline_fleet.py::test_dagster_export_AC_007`, `::test_mage_export_AC_007` | done |

## Follow-ups

- Durable queue backend and a `quantsmith-fleet plan|export` CLI.
- Airflow (`pools`, `max_active_runs`) and Prefect (global concurrency limits)
  exporters.
- Feed `0019` observed durations into `est_seconds` automatically.
