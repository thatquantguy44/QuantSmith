# Tasks: FRED Point-In-Time Panel Adapter

- **Spec:** 0045-fred-point-in-time (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-12

## Definition of Done (applies to every task)

- Standard library only (`sqlite3`, `datetime`); no dependency added.
- Read-only: the database is opened in read-only mode, no DDL or DML.
- No credential ever enters this repository (P9).
- A revised series returns its **original** value for an as-of date
  before the revision.
- Deterministic: the same database and arguments always produce the same
  panel.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `PitObservation`, `FredPitError`, `load_observations`, `as_of_value`, `as_of_snapshot`, `build_panel`, `panel_to_returns`. | REQ-001 – REQ-006, NFR-001, NFR-002, NFR-003 | done | Vintage selection by window containment on `realtime_start`/`realtime_end`; `NULL` end treated as open-ended; `is_missing` rows skipped. |
| T-002 | Write `tests/test_fred_point_in_time.py`. | REQ-001 – REQ-006, NFR-001 | done | Temporary SQLite fixture mirroring the upstream DDL, with a revised series, an open-ended vintage, a publication lag, and an `is_missing` row. One test per AC-001 – AC-010. |
| T-003 | Wire catalogs and handoff docs. | REQ-007 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-004 | Run validation gates. | NFR-004 | done | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`, `backtest`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_load_observations_parses_rows_AC_001` | done |
| AC-002 | `test_pre_revision_returns_original_value_AC_002` | done |
| AC-003 | `test_post_revision_returns_revised_value_AC_003` | done |
| AC-004 | `test_before_first_publication_returns_none_AC_004` | done |
| AC-005 | `test_publication_lag_hides_observation_AC_005` | done |
| AC-006 | `test_missing_flag_yields_no_value_AC_006` | done |
| AC-007 | `test_panel_to_returns_AC_007` | done |
| AC-008 | `test_panel_feeds_backtest_AC_008` | done |
| AC-009 | `test_missing_db_or_table_raises_AC_009` | done |
| AC-010 | `test_deterministic_AC_010` | done |
| AC-011 | Direct inspection of the three catalogs | done |

## Follow-ups

- **The real run** — the remaining half of the vertical slice. Requires
  `fred_local.db` produced by the operator via
  `PYTHONPATH=src python -m fred_pipeline run --local --db-path fred_local.db`
  with their own `FRED_API_KEY`. Once that file exists, building a
  point-in-time macro panel and backtesting it is a wiring exercise on
  this module plus `0044`.
- Consume `gold_fred_macro_feature_daily` for pre-computed transforms
  once this path is trusted end to end (carried as an open question in
  `spec.md`).
