# Tasks: Backtest Engine

- **Spec:** 0044-backtesting (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-12

## Definition of Done (applies to every task)

- Standard library only; no dependency added.
- No look-ahead is structural (`j = i + rebalance_lag`, `lag >= 1`), not
  an assertion.
- Net return is always gross minus costs, exactly; gross is never
  reported alone.
- A probabilistic Sharpe accompanies every Sharpe.
- Deterministic: the same inputs always produce the same result and text.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `BacktestConfig`, `PeriodResult`, `BacktestResult`, `run_backtest`, `probabilistic_sharpe_ratio`, `render_backtest_report`. | REQ-001 – REQ-007, NFR-001, NFR-002 | done | PSR via Bailey & López de Prado; normal CDF from `math.erf`. |
| T-002 | Write `tests/test_backtesting.py`. | REQ-001 – REQ-007, NFR-001, NFR-003 | done | One test per acceptance criterion (AC-001 – AC-010); AC-009 checks `backtest-check.sh`'s own theme regexes. |
| T-003 | Generate and commit the example report. | REQ-008 | done | `specs/0044-backtesting/backtest_report.md`, produced by `render_backtest_report`, verified against the CI-enforced gate (AC-011). |
| T-004 | Wire catalogs and handoff docs. | REQ-009 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-005 | Run validation gates. | NFR-004 | done | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`, `backtest`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_no_lookahead_offset_AC_001` | done |
| AC-002 | `test_zero_lag_rejected_AC_002` | done |
| AC-003 | `test_net_equals_gross_minus_costs_AC_003` | done |
| AC-004 | `test_unchanged_weights_cost_nothing_AC_004` | done |
| AC-005 | `test_financing_charged_on_shorts_only_AC_005` | done |
| AC-006 | `test_drawdown_and_equity_curve_AC_006` | done |
| AC-007 | `test_probabilistic_sharpe_AC_007` | done |
| AC-008 | `test_active_return_vs_benchmark_AC_008` | done |
| AC-009 | `test_report_satisfies_gate_themes_AC_009` | done |
| AC-010 | `test_deterministic_AC_010` | done |
| AC-011 | `hooks/stages/run-stage.sh backtest` against the committed example | done |
| AC-012 | Direct inspection of the three catalogs | done |

## Follow-ups

- **The real vertical slice** (the second half of this build): consume
  `gold_fred_point_in_time` from the local SQLite output of
  `joshualutkemuller/fred-bronze-to-gold-pipeline`, using its
  `realtime_start` / `realtime_end` vintages for a genuinely
  point-in-time macro backtest. Blocked on a `FRED_API_KEY` held by the
  operator — never by this repository (P9).
- Compose `0028`'s `financing_cost_analysis` for per-name borrow rates
  instead of a flat annual rate, once a real short book is simulated
  (carried as an open question in `spec.md`).
- Revisit the numpy decision if and when a workload needs a large
  cross-section over long history (RISK-004).
