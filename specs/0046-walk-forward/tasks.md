# Tasks: Walk-Forward Backtest Harness

- **Spec:** 0046-walk-forward (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-12

## Definition of Done (applies to every task)

- Standard library plus `return_forecasting` (`0006`) and `backtesting`
  (`0044`); neither is modified.
- Fold splitting is `make_folds`', not a second implementation.
- `fit_predict` is called once per fold and evaluated on held-out test
  periods only.
- The fold distribution is the headline; no single number stands alone.
- Deterministic: the same inputs always produce the same result and text.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `FoldBacktest`, `WalkForwardResult`, `walk_forward_backtest`, `render_walk_forward_report`. | REQ-001 – REQ-007, NFR-001, NFR-002 | done | Fold slicing preserves `rebalance_lag`; pooled series built from held-out periods only. |
| T-002 | Write `tests/test_walk_forward.py`. | REQ-001 – REQ-007, NFR-001, NFR-003 | done | One test per acceptance criterion (AC-001 – AC-009); AC-001 pins delegation to `make_folds`, AC-003 pins lag alignment. |
| T-003 | Generate and commit the example report. | REQ-008 | done | `specs/0046-walk-forward/backtest_report.md`, produced by `render_walk_forward_report`, verified against the `backtest` gate (AC-010). |
| T-004 | Wire catalogs and handoff docs. | REQ-009 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-005 | Run validation gates. | NFR-004 | done | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`, `backtest`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_folds_delegate_to_make_folds_AC_001` | done |
| AC-002 | `test_fit_predict_called_once_per_fold_disjoint_AC_002` | done |
| AC-003 | `test_fold_alignment_preserves_lag_AC_003` | done |
| AC-004 | `test_fold_distribution_reported_AC_004` | done |
| AC-005 | `test_pooled_out_of_sample_series_AC_005` | done |
| AC-006 | `test_wrong_weight_count_raises_AC_006` | done |
| AC-007 | `test_report_satisfies_gate_themes_AC_007` | done |
| AC-008 | `test_deterministic_AC_008` | done |
| AC-009 | `test_too_few_periods_raises_AC_009` | done |
| AC-010 | `hooks/stages/run-stage.sh backtest` against the committed example | done |
| AC-011 | Direct inspection of the three catalogs | done |

## Follow-ups

- A **deflated Sharpe ratio** correcting for the number of variants
  tried — the honest completion of the multiple-testing story, and the
  guard against selecting a variant on these fold results (carried as an
  open question in `spec.md`).
- Anchored and rolling walk-forward variants, if the contiguous
  expanding-train shape `make_folds` provides proves too restrictive.
- **The FRED run**, still blocked on `fred_local.db` from the operator:
  with `0044`, `0045`, and this harness in place, a genuinely
  point-in-time, out-of-sample macro backtest is a wiring exercise.
