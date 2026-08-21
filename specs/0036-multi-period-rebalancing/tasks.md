# Tasks: Multi-Period Rebalancing (Dynamic Programming)

- **Spec:** 0036-multi-period-rebalancing (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Standard-library only; no dependency added.
- No modification to `optimization_solvers.py` (`0013`) — composition only.
- Deterministic: the same inputs always return the same trade path and
  cost.
- `max_trade` enforced by construction, not a post-hoc check.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `solve_multi_period_rebalancing` and `RebalancingPlan`. | REQ-001, REQ-002, REQ-003, REQ-004, NFR-001, NFR-002, NFR-003 | done | `DPProblem` construction, forward policy walk to reconstruct the path. |
| T-002 | Write `tests/test_multi_period_rebalancing.py`. | REQ-001, REQ-002, REQ-003, REQ-004, NFR-001 | done | One test per acceptance criterion (AC-001 – AC-006). |
| T-003 | Wire catalogs and handoff docs. | REQ-005 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-004 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_immediate_move_to_target_when_free_AC_001` | done |
| AC-002 | `test_no_trade_when_prohibitively_expensive_AC_002` | done |
| AC-003 | `test_multi_period_path_to_target_AC_003` | done |
| AC-004 | `test_max_trade_never_exceeded_AC_004` | done |
| AC-005 | `test_total_cost_matches_realized_path_cost_AC_005` | done |
| AC-006 | `test_deterministic_AC_006` | done |
| AC-007 | Direct inspection of `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | done |

## Follow-ups

- A genuinely multi-dimensional (small number of correlated positions)
  version, once a concrete workflow needs more than one dimension
  (carried as an open question in `spec.md`).
- Convex/nonlinear transaction and tracking-error cost curves, if a
  concrete workflow needs them beyond the linear rates this slice
  supports.

This closes out every solver in the `0013` toolkit having at least one
shipped application: `0007`/`0034` (QP + MILP), `0035` (flow), `0036`
(DP).
