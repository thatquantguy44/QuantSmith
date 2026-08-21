# Tasks: Financing Cost Analysis

- **Spec:** 0028-financing-cost-analysis (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Every `AC-*` has a passing, named test in `tests/test_financing_cost_analysis.py`.
- The module stays standard-library only.
- Reconciliation with `0023` is by value, never by importing its `numpy`-dependent runtime.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Implement the runtime module. | REQ-001..005, NFR-001..003 | done | `src/quantsmith/pipelines/financing_cost_analysis.py`. |
| T-002 | Add the acceptance test module. | REQ-001..005, NFR-001 | done | `tests/test_financing_cost_analysis.py`, 8 tests (AC-001..006, plus two validation/reconciliation tests under AC-001). |
| T-003 | Export from the package. | NFR-002 | done | `src/quantsmith/pipelines/__init__.py`; verified no name collisions. |
| T-004 | Reference the runtime from the agent contract and wire catalogs. | REQ-006 | done | `agents/securities_financing/financing_cost_analysis/{README,instructions}.md`, `agents/securities_financing/README.md`, `agents/README.md`, `specs/README.md`, `src/quantsmith/pipelines/README.md`, `docs/workflows.md`, root `README.md`, `docs/handoff.md`. |
| T-005 | Run validation gates. | NFR-003 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; full `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_decompose_all_legs_AC_001`, `test_position_validation_rejects_bad_side_and_notional_AC_001`, `test_position_from_borrow_rate_reconciles_with_sec_lending_AC_001` | done |
| AC-002 | `test_financing_aware_returns_reports_drag_AC_002` | done |
| AC-003 | `test_flag_understated_backtest_AC_003` | done |
| AC-004 | `test_spread_sensitivity_is_monotonic_in_shock_AC_004` | done |
| AC-005 | `test_capacity_limit_flags_constrained_classification_AC_005` | done |
| AC-006 | `test_check_point_in_time_flags_lookahead_AC_006` | done |
| AC-007 | Direct inspection of the agent contract, `agents/README.md`, `specs/README.md`, `src/quantsmith/pipelines/README.md` | done |

## Follow-ups

- Promote `repo_financing` and `collateral_management` to tested runtimes
  if a concrete workflow needs to derive their inputs rather than supply
  them directly, closing out the `securities_financing` group entirely.
- A specials-aware (non-uniform) rate-shock sensitivity model, once real
  HTB financing data exists to validate one against.
- A parameterized day-count basis (ACT/365, ACT/ACT, 30/360) if a
  non-ACT/360 market becomes a real workflow requirement.
