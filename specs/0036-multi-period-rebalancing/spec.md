# Spec: Multi-Period Rebalancing (Dynamic Programming)

- **ID:** 0036-multi-period-rebalancing
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`specs/0013-optimization-solvers/` shipped `solve_dp`, a deterministic
finite-horizon backward-induction solver, but nothing has been built on it
yet. `specs/0034-cardinality-constrained-portfolio/` and
`specs/0035-funding-ladder/` closed the SDK's standing `P0` gap for the
MILP and flow solvers; this spec does the same for the last one —
completing every solver in the `0013` toolkit with at least one
application. `0007`'s continuous QP already trades off a turnover penalty
against return/risk in a *single* rebalance decision (`lambda_to`); this
spec addresses the genuinely different problem of a position rebalanced
*over multiple periods*, where trading toward a target sooner costs more
now but leaves less tracking-error cost later — a sequential decision
`solve_dp`'s backward induction is built for.

`solve_dp` requires a discrete, enumerable state space (`states:
Sequence[State]`, `State = Hashable`) — it cannot represent a continuous
portfolio-weight vector directly. This spec's honest scope is therefore a
**single position on a discretized grid** (e.g. a position size, a factor
tilt, or a cash-ladder level expressed as one number), not a full
multi-asset continuous rebalancing problem — matching how `0034`/`0035`
each picked the tractable, composable formulation their underlying solver
actually supports rather than the maximally general one.

## Goals

- Add `src/quantsmith/pipelines/multi_period_rebalancing.py`:
  `solve_multi_period_rebalancing` — builds a `DPProblem` over a
  discretized position grid (states = grid points; actions = moving to
  another grid point within a per-period trade limit) and solves it via
  `0013`'s `solve_dp` directly (no reimplementation).
- At each period, trade off a transaction cost (proportional to trade
  size) against a tracking-error cost (proportional to distance from
  target), both at caller-supplied per-unit rates — not a fixed built-in
  trade-off.
- Respect a maximum trade size per period; the optimal path may take
  multiple periods to reach the target when a single period's move is
  capped.
- Report the full trade path (position after each period) and the trade
  taken at each period, plus the total cost — not just a final position.

## Non-Goals

- No continuous, multi-asset portfolio state. This is a single
  discretized position dimension; a full multi-asset rebalancing DP would
  need a state space exponential in the number of assets, which is out of
  scope for a dependency-free reference solver (the same class of
  limitation `solve_milp`'s own docstring already discloses: "intended for
  small problems").
- No stochastic dynamics (uncertain future prices/costs). `solve_dp`
  itself only supports deterministic transitions; this spec inherits that
  limitation rather than working around it.
- No infeasibility case. Unlike `0034`/`0035`'s LP/MILP/flow solvers,
  "stay at the current position" (zero trade) is always a valid action at
  every state, so a well-formed problem here always has a defined optimal
  policy — there is no analogous `"infeasible"` status to report.
- No securities-financing modeling, consistent with the standing
  direction already recorded for `0034`/`0035`.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `solve_multi_period_rebalancing` shall build a `DPProblem` over a discretized position grid and solve it via `solve_dp`, choosing at each period the next grid position minimizing cumulative transaction and tracking-error cost. | must |
| REQ-002 | No action shall move the position further than `max_trade` from its current value in a single period. | must |
| REQ-003 | The result shall report the position path (one value per period), the trade taken at each period, and the total cost. | must |
| REQ-004 | Transaction cost and tracking-error cost shall each be driven by a caller-supplied per-unit rate, not a fixed internal trade-off. | must |
| REQ-005 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same grid, start position, target, and cost rates always return the same trade path and cost. |
| NFR-002 | Composition, not reimplementation | No new backward-induction logic; the module only builds the `DPProblem` and calls `solve_dp`. |
| NFR-003 | Dependency isolation | Standard-library only, consistent with `0007`/`0013`/`0034`/`0035`. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When | Then | Covers |
| --- | --- | --- | --- |
| AC-001 | Given a start position away from target and zero transaction cost, when solved, then the plan moves to the closest reachable grid position to target in the first period and stays there. | REQ-001, REQ-004 |
| AC-002 | Given a start position away from target and a transaction cost high enough that trading is never worthwhile, when solved, then the plan makes no trade in any period. | REQ-001, REQ-004 |
| AC-003 | Given a gap to target larger than `max_trade`, when solved, then the plan reaches the target over multiple periods, moving at most `max_trade` per period. | REQ-002 |
| AC-004 | Given any solved plan, when the trade path is inspected, then no single period's trade exceeds `max_trade`. | REQ-002 |
| AC-005 | Given a solved plan, when the reported total cost is compared against the sum of realized per-period transaction and tracking-error costs along the reported path, then they match. | REQ-003 |
| AC-006 | Given the same grid, start position, target, and cost rates, when solved twice, then the trade path and total cost are identical both times. | NFR-001 |
| AC-007 | Given `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md`, when inspected, then each lists spec `0036` and `multi_period_rebalancing.py`. | REQ-005 |

## Data & Dependencies

No data dependencies. Standard-library only; imports `solve_dp` and
`DPProblem` from `optimization_solvers.py` (`0013`) directly — no new
dependency, no modification to that module.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The single-dimension, discretized-grid scope is mistaken for a general multi-asset rebalancing tool. | A user expects it to handle a full portfolio and is surprised by the one-dimensional state. | Stated explicitly and repeatedly (Problem & Context, Non-Goals) as a single discretized position dimension; the function signature itself (`grid: Sequence[float]`) makes the one-dimensional scope structurally visible. |
| RISK-002 | Grid discretization coarseness silently changes the answer (a coarse grid can't represent a precise target). | A caller reads the reported plan as exact when it is bounded by grid resolution. | The module doesn't snap or interpolate silently — the target and start position are used as supplied, and the reachable positions are exactly the caller's own grid; no hidden rounding beyond what the caller's grid choice already implies. |
| RISK-003 | A caller expects an "infeasible" outcome for some cost/grid combination, matching `0034`/`0035`'s pattern, and is confused when none is ever returned. | Confusion about the result contract's consistency across the three optimizer applications. | Stated explicitly as a Non-Goal: "stay put" is always a valid, zero-cost-of-trading action, so this problem class structurally has no infeasible case — documented as a deliberate difference, not an oversight. |

## Assumptions & Open Questions

- Assumption: a single discretized position dimension is the right first
  scope for `solve_dp`, matching `0034`/`0035`'s own precedent of picking
  the tractable formulation their specific solver actually supports.
- Assumption: linear (proportional) transaction and tracking-error costs
  are a sufficient first cost model; convex/nonlinear cost curves are a
  candidate follow-up, not this slice.
- Open question: would a genuinely multi-dimensional (small number of
  correlated positions) version be worth building later, accepting the
  state-space growth, once a concrete workflow needs more than one
  dimension?

## Exceptions

None.
