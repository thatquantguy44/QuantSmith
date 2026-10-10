# Tasks: Change-safe data engineering

- **Spec:** 0111-change-safe-data-engineering (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-10

> Every task cites a requirement; every acceptance criterion is named by a test.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests pass deterministically.
- Nothing is dropped silently; every skipped, late, drifting, or blocked item is reported.
- No secrets, credentials, or private data introduced; runtime code lives under
  `src/quantsmith/`.
- Docs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Agent | Notes |
| --- | --- | --- | --- | --- | --- |
| T-001 | Implement idempotent, order-safe CDC application. | REQ-001, NFR-001 | done | `data_engineering/streaming_cdc` | Full images converge in any order. |
| T-002 | Implement watermarked event-time windows, late handling, bitemporal revisions. | REQ-002, REQ-003, NFR-002 | done | `data_engineering/streaming_cdc` | Uses `0102` `BitemporalStore`. |
| T-003 | Implement schema compatibility, mode checks, backward reads, drift detection. | REQ-004, REQ-005, REQ-006 | done | `data_engineering/schema_evolution` | Avro-style widening. |
| T-004 | Implement reprocessing plan, fleet execution, compare, and atomic swap. | REQ-007, REQ-008, REQ-009, NFR-003 | done | `data_engineering/backfill_reprocessing` | Uses `0101` and `0102`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `tests/test_change_safety.py::test_cdc_idempotent_and_order_safe_AC_001`, `::test_full_image_cdc_converges_in_any_order_AC_001` | done |
| AC-002 | `tests/test_change_safety.py::test_windows_emit_on_watermark_and_account_for_late_AC_002` | done |
| AC-003 | `tests/test_change_safety.py::test_restatements_are_bitemporal_AC_003` | done |
| AC-004 | `tests/test_change_safety.py::test_change_classification_AC_004` | done |
| AC-005 | `tests/test_change_safety.py::test_mode_enforcement_and_backward_reads_AC_005` | done |
| AC-006 | `tests/test_change_safety.py::test_drift_detection_AC_006` | done |
| AC-007 | `tests/test_change_safety.py::test_plan_covers_exactly_the_downstream_AC_007` | done |
| AC-008 | `tests/test_change_safety.py::test_execute_writes_new_versions_with_lineage_AC_008`, `::test_failure_isolation_AC_008` | done |
| AC-009 | `tests/test_change_safety.py::test_compare_and_atomic_swap_AC_009`, `::test_failed_run_blocks_swap_AC_009` | done |

## Follow-ups

- Sliding and session windows; a schema-registry adapter (Confluent/Glue).
- Persist publication pointers as warehouse views; wire `0019` freshness to swaps.
- Slices B (dbt, Spark, Ray/Dask, Airflow/Prefect exporters) and C (lakehouse
  formats, FinOps, reference-data pack) of `0107`.
