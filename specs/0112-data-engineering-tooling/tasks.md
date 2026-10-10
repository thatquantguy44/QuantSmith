# Tasks: Data-engineering tooling

- **Spec:** 0112-data-engineering-tooling (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-10

> Every task cites a requirement; every acceptance criterion is named by a test.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests pass deterministically.
- Every lossy mapping is warned; heuristics are labeled.
- No secrets, credentials, or private data introduced; runtime code lives under
  `src/quantsmith/`.
- Docs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Agent | Notes |
| --- | --- | --- | --- | --- | --- |
| T-001 | Implement `to_airflow` and `to_prefect`; add Airflow and Prefect profiles. | REQ-001, REQ-002, NFR-001 | done | `tooling/dag_orchestration` | Verify keys per installed version. |
| T-002 | Implement `review_manifest` with per-node test attribution. | REQ-003, REQ-004 | done | `tooling/dbt` | Manifest v10+. |
| T-003 | Implement partition planning, skew, salting, and the determinism lint. | REQ-005, REQ-006, REQ-007, NFR-002 | done | `tooling/spark`, `tooling/ray_dask` | Lint is a heuristic. |
| T-004 | Add `tooling/dbt`, `tooling/spark`, `tooling/ray_dask` agents; regenerate registry and skills. | REQ-003, REQ-005, REQ-007, NFR-003 | done | `implementation` | Added to the project skill selection. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `tests/test_data_eng_tooling.py::test_airflow_export_AC_001` | done |
| AC-002 | `tests/test_data_eng_tooling.py::test_prefect_export_AC_002` | done |
| AC-003 | `tests/test_data_eng_tooling.py::test_dbt_review_rules_AC_003` | done |
| AC-004 | `tests/test_data_eng_tooling.py::test_tests_attach_to_their_own_model_AC_004` | done |
| AC-005 | `tests/test_data_eng_tooling.py::test_partition_planning_and_skew_AC_005` | done |
| AC-006 | `tests/test_data_eng_tooling.py::test_salting_plan_AC_006` | done |
| AC-007 | `tests/test_data_eng_tooling.py::test_determinism_lint_AC_007` | done |

## Follow-ups

- CLI wrappers (`quantsmith-dbt-review`, `quantsmith-fleet export --target`).
- Spark `EXPLAIN` parsing for shuffle sizing; Ray Data block-size guidance in code.
- Slice C of `0107`: lakehouse formats, FinOps, reference-data pack.
