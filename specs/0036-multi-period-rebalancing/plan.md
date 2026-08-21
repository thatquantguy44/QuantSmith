# Plan: Multi-Period Rebalancing (Dynamic Programming)

- **Spec:** 0036-multi-period-rebalancing (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Add one new, dependency-free module,
`src/quantsmith/pipelines/multi_period_rebalancing.py`, that builds a
`DPProblem` over a discretized position grid and calls `0013`'s
`solve_dp` directly — the same composition-not-reimplementation pattern
`0034`/`0035` established for `solve_milp`/`min_cost_flow`.
`optimization_solvers.py` is not modified.

## Architecture & Components

```text
multi_period_rebalancing.py
  RebalancingPlan   -- position_path, trades, total_cost

  solve_multi_period_rebalancing(
      grid, start_position, target, horizon, max_trade,
      transaction_cost_per_unit, tracking_cost_per_unit, discount=1.0,
  ) -> RebalancingPlan

    states  = grid                     (one state per discretized position)
    actions(state) = [g for g in grid if abs(g - state) <= max_trade]
                                        ("stay put" always included: g == state)
    step(state, next_position) = (
        next_position,
        transaction_cost_per_unit * abs(next_position - state)
          + tracking_cost_per_unit * abs(next_position - target),
    )
    terminal_value(state) = tracking_cost_per_unit * abs(state - target)
    sense = "min"

    -> DPProblem(horizon, states, actions, step, terminal_value, discount, sense)
    -> solve_dp(problem)                                     [0013, unmodified]
    -> walk policy forward from (0, start_position) for `horizon` periods
       to reconstruct position_path / trades; total_cost = values[start_position]
```

## Interfaces & Data Contracts

`RebalancingPlan` is the one new (frozen) dataclass — position path,
per-period trades, and total cost. No external schema; `grid` is a plain
`Sequence[float]` supplied by the caller, used exactly as given (no
snapping or interpolation).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | `max_trade` is enforced by action-set construction (`actions(state)` only ever contains grid points within `max_trade`), not a post-hoc check — an over-sized trade is structurally impossible to select. |
| P10 Honest reporting | yes | The one-dimensional, discretized-grid scope is stated explicitly and repeatedly rather than implying a general multi-asset capability; the deliberate absence of an "infeasible" status is explained, not left to look like an inconsistency with `0034`/`0035`. |
| P8 No silent trade-offs | yes | RISK-001 through RISK-003 are named in the spec, each with a stated mitigation. |
| P5 Reversibility | yes | New, additive module; `optimization_solvers.py` is unmodified. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `DPProblem` construction + `solve_dp` call | T-001 |
| REQ-002 | `actions(state)` bounded by `max_trade` | T-001 |
| REQ-003 | `RebalancingPlan.position_path` / `.trades` / `.total_cost`, forward policy walk | T-001 |
| REQ-004 | `transaction_cost_per_unit` / `tracking_cost_per_unit` parameters in `step`/`terminal_value` | T-001 |
| REQ-005 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | T-003 |
| NFR-001 | No randomness; deterministic problem construction and `solve_dp` call | T-001 |
| NFR-002 | Composition only — direct imports of `solve_dp`/`DPProblem`, no reimplementation | T-001 |
| NFR-003 | Standard-library only | T-001 |
| NFR-004 | Validation gates | T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| State space | A single discretized position dimension | A multi-asset continuous or discretized vector state | `solve_dp`'s `states` must be an enumerable, hashable sequence; a multi-asset state space grows exponentially with the number of assets and grid resolution, making it intractable for a small, dependency-free reference solver. Matches `0034`/`0035`'s own precedent of the tractable formulation over the maximally general one. |
| Action representation | Actions are target grid positions (`g in grid`), not trade deltas | Actions as raw trade-size deltas, applied via arithmetic to the current state | Representing actions as target positions guarantees the next state always lands exactly on a grid point (no floating-point snapping needed); deltas would require re-snapping the arithmetic result back onto the grid, adding a rounding step that could silently pick the "wrong" nearby grid point. |
| Cost sign / `sense` | `sense="min"`, `step`/`terminal_value` return positive costs directly | `sense="max"` with negated rewards | `solve_dp` supports `sense="min"` natively; returning cost directly (not `-cost`) keeps the module's own arithmetic and its tests' assertions simpler and less error-prone than a sign-flip convention. |
| Infeasibility | None — not modeled, since it structurally cannot occur | Add a synthetic `"infeasible"` status for API consistency with `0034`/`0035` | Manufacturing an infeasible case that can never actually trigger would be dishonest scaffolding; the spec instead explains directly why this solver class doesn't need one (P10). |

## Validation Strategy

`tests/test_multi_period_rebalancing.py`, one test per acceptance
criterion (AC-001 through AC-007), following `0007`/`0013`/`0034`/`0035`'s
own per-AC test naming convention. Then `hooks/stages/run-stage.sh spec
agent-catalog docs-link spec-index`, the full `pytest tests/ -q`, and
`git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is
reverting the single commit; `optimization_solvers.py` is unmodified, so
nothing downstream is affected by a rollback. This closes out every
solver in the `0013` toolkit having at least one shipped application
(`0007`/`0034` for QP+MILP, `0035` for flow, `0036` for DP).

## Open Questions

- Would a genuinely multi-dimensional (small number of correlated
  positions) version be worth building later, accepting the state-space
  growth, once a concrete workflow needs more than one dimension?
