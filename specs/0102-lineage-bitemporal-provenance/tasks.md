# Tasks: Lineage and bitemporal provenance

- **Spec:** 0102-lineage-bitemporal-provenance (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-10

> Every task cites a requirement; every acceptance criterion is named by a test.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests exist and pass deterministically.
- No read returns a fact recorded after its knowledge time; no recording leaves
  partial state.
- No secrets, credentials, or private data introduced; runtime code lives under
  `src/quantsmith/`.
- Docs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Agent | Notes |
| --- | --- | --- | --- | --- | --- |
| T-001 | Implement `content_hash`, `DatasetVersion`, immutable version registry. | REQ-001, NFR-001 | done | `provenance/lineage_capture` | Canonical JSON. |
| T-002 | Implement `register_source` and validate-then-mutate `record_run`. | REQ-002, NFR-003 | done | `provenance/lineage_capture` | No orphan outputs. |
| T-003 | Implement `trace`, `impact`, `trace_column`, `verify`, `cite`. | REQ-003, REQ-004, NFR-003 | done | `provenance/lineage_capture` | Gaps, not guesses. |
| T-004 | Implement `to_openlineage`. | REQ-005 | done | `provenance/lineage_capture` | OpenLineage-shaped. |
| T-005 | Implement `BitemporalStore` (record, retract, as_of, snapshot, revisions). | REQ-006, REQ-007, NFR-002 | done | `provenance/bitemporal_data` | Monotonic knowledge clock. |
| T-006 | Implement `lookahead_violations`. | REQ-008, NFR-002 | done | `provenance/bitemporal_data` | Feeds `backtest_review`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `tests/test_provenance.py::test_content_hash_and_immutability_AC_001` | done |
| AC-002 | `tests/test_provenance.py::test_run_validation_AC_002` | done |
| AC-003 | `tests/test_provenance.py::test_trace_impact_and_column_lineage_AC_003` | done |
| AC-004 | `tests/test_provenance.py::test_verify_and_cite_AC_004` | done |
| AC-005 | `tests/test_provenance.py::test_openlineage_event_AC_005` | done |
| AC-006 | `tests/test_provenance.py::test_bitemporal_append_only_AC_006` | done |
| AC-007 | `tests/test_provenance.py::test_as_of_revisions_and_retraction_AC_007` | done |
| AC-008 | `tests/test_provenance.py::test_lookahead_violations_AC_008` | done |

## Follow-ups

- Durable backend (SQLite/Parquet) and a `quantsmith-lineage` CLI.
- Record lineage automatically from the `0011` and `0101` runners.
- Move `0045`'s FRED vintages onto `BitemporalStore`.
- Vendor licensing and entitlements (`0108`).
