# Spec: Cardinality-Constrained Portfolio Construction

- **ID:** 0034-cardinality-constrained-portfolio
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`specs/0007-portfolio-construction/` solves a continuous mean-variance QP
and `specs/0013-optimization-solvers/` ships a general LP/MILP/flow/DP
toolkit — but nothing in the SDK has actually built an *application* on
that toolkit since `0007` (QP) and `0012` (execution scheduling). This is
the SDK's only standing `P0` backlog item (`docs/handoff.md` items 1/5).
A cardinality constraint — hold at most K names, out of a larger candidate
universe — is one of the most common real-world portfolio constraints
(operational overhead, monitoring capacity, compliance limits) and is
exactly the kind of constraint `0007`'s continuous QP structurally cannot
express: true cardinality-constrained mean-variance optimization is a
mixed-integer *quadratic* program (MIQP), which is NP-hard and not
something this SDK's dependency-free solvers can solve exactly.

This spec closes the gap honestly rather than pretending it doesn't
exist: it composes the two solvers the SDK already has — `0013`'s
`solve_milp` (a linear-objective mixed-integer solver) selects *which*
names to hold, and `0007`'s `solve_portfolio` (mean-variance QP) sizes
*how much* to hold in each — into a documented two-stage heuristic. This
is a standard, well-understood practitioner technique for cardinality-
constrained portfolios when a true MIQP solver isn't available, not an
invented shortcut; it is stated explicitly as a heuristic, not a claim of
joint global optimality.

## Goals

- Add `src/quantsmith/pipelines/cardinality_portfolio.py`:
  `select_cardinality_support` (MILP: pick at most `max_names` names by
  linear expected-return maximization, subject to budget/box bounds and an
  optional minimum weight per selected name) and
  `cardinality_constrained_portfolio` (orchestrates selection, then calls
  `0007`'s `solve_portfolio` on the reduced-dimension selected support,
  reconstructing a full-length weight vector with an exact zero at every
  unselected name).
- Enforce a minimum weight for a selected name end to end — in both the
  selection stage and the final sizing stage — so a cardinality slot can't
  be "spent" on a position sized down to near-zero.
- Report infeasibility explicitly (a stated status, `weights=None`) rather
  than raising an unclear error or returning a silently wrong result when
  no feasible selection exists.
- Reuse `solve_milp` and `solve_portfolio` directly; no new solver logic
  is invented — this module is composition, not a third solver.

## Non-Goals

- No true joint MIQP solve. The two-stage decomposition is a documented
  heuristic; it can differ from what a real MIQP solver (Gurobi, CPLEX)
  would find jointly optimal. A production build can swap in one behind
  the same interface, the same production-swap note `0013`'s own module
  docstring already makes for its LP/MILP solvers.
- No short positions. `solve_lp`/`solve_milp` assume `x >= 0`; this module
  is explicitly long-only and validates against a negative lower bound
  rather than silently ignoring the request.
- No transaction-cost-aware *selection*. The selection stage maximizes
  linear expected return only; turnover-awareness (via `w_prev`/
  `lambda_to`) still applies in the sizing stage, reusing `0007`'s
  existing turnover penalty unchanged.
- No securities-financing LP application. As already corrected in
  `docs/handoff.md`, that domain routes to an adopter's own models via
  `agents/optimization/model_plugin_registration/` (spec `0026`), not the
  SDK's own solver toolkit.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `select_cardinality_support` shall select at most `max_names` positions via `solve_milp`, maximizing linear expected return subject to budget and box bounds. | must |
| REQ-002 | `cardinality_constrained_portfolio` shall size the selected support via `0007`'s `solve_portfolio` on the reduced dimension, reconstructing a full-length weight vector with an exact zero at every unselected index. | must |
| REQ-003 | An optional `min_weight_selected` shall be enforced both in the selection stage and the sizing stage, so every nonzero final weight is at least `min_weight_selected`. | must |
| REQ-004 | The system shall report infeasibility explicitly (a stated status, `weights=None`) rather than raising an unclear error or returning a wrong result when no feasible selection exists. | must |
| REQ-005 | The system shall be long-only; a request with a negative `lower` bound shall raise a clear error rather than silently misbehave. | must |
| REQ-006 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same inputs always return the same selected support and weights. |
| NFR-002 | Composition, not reimplementation | No new simplex/branch-and-bound/projection logic; the module only calls `solve_milp` and `solve_portfolio`. |
| NFR-003 | Dependency isolation | Standard-library only, consistent with `0007`/`0013`. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a candidate universe larger than `max_names`, when solved, then the number of nonzero-weight names is at most `max_names`. | REQ-001 |
| AC-002 | Given a solved portfolio, when inspected, then every unselected name's weight is exactly `0.0`. | REQ-002 |
| AC-003 | Given `min_weight_selected > 0`, when solved, then every nonzero final weight is `>= min_weight_selected`. | REQ-003 |
| AC-004 | Given a `max_names`/budget/bounds combination with no feasible selection, when solved, then the status is `"infeasible"` and `weights` is `None` — no exception, no silently wrong numbers. | REQ-004 |
| AC-005 | Given a negative `lower` bound, when `select_cardinality_support` or `cardinality_constrained_portfolio` is called, then a `ValueError` is raised naming the long-only restriction. | REQ-005 |
| AC-006 | Given the same inputs, when solved twice, then the selected support and weights are identical both times. | NFR-001 |
| AC-007 | Given a turnover penalty (`w_prev`, `lambda_to`) on the selected support, when solved, then turnover behaves per `0007`'s existing, unmodified turnover-penalty behavior — confirming the composition didn't change `solve_portfolio`'s own behavior. | REQ-002, NFR-002 |
| AC-008 | Given `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md`, when inspected, then each lists spec `0034` and `cardinality_portfolio.py`. | REQ-006 |

## Data & Dependencies

No data dependencies. Standard-library only; imports `solve_milp` from
`optimization_solvers.py` (`0013`) and `solve_portfolio`/`ConstraintSet`
from `portfolio_construction.py` (`0007`) directly — no new dependency,
no modification to either existing module.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The two-stage decomposition (select by linear alpha, then size by QP) is not the true joint MIQP optimum — it can pick a different, suboptimal support than a real mixed-integer *quadratic* solver would. | A user reads the result as globally optimal when it is a documented heuristic. | Stated explicitly and repeatedly (module docstring, this spec's Problem & Context and Non-Goals) as a heuristic decomposition, not a joint solve, matching the same honest-scoping pattern already used for `solve_milp`'s "reference solver, small problems" caveat and `securities_lending`'s greedy-fallback disclosure. |
| RISK-002 | The long-only assumption (inherited from `solve_lp`/`solve_milp`'s `x >= 0`) is easy to overlook if a caller expects short capability. | A caller silently gets a long-only result when they expected shorts, or an unclear failure. | REQ-005/AC-005: a negative `lower` bound raises a clear, named error rather than being silently ignored or producing a nonsensical result. |
| RISK-003 | Selecting purely by linear expected return, with no risk awareness in the selection stage, can pick a support the risk-aware sizing stage then wants to size near zero — "spending" a cardinality slot on a token position. | A selected name contributes negligibly, defeating the point of the cardinality constraint. | REQ-003: `min_weight_selected`, enforced end to end (selection *and* sizing), directly prevents a selected slot from being sized down to near-zero. |

## Assumptions & Open Questions

- Assumption: a documented two-stage heuristic is the right scope for a
  dependency-free reference implementation; a true joint MIQP solve would
  require an optional external solver dependency, which is explicitly out
  of scope until a concrete workflow needs it (mirroring `0013`'s own
  "production build may swap in HiGHS/OR-Tools" note).
- Assumption: enforcing `min_weight_selected` in both stages (not just the
  MILP selection stage) is worth the added constraint row in the reduced
  QP's `ConstraintSet`, since it closes the exact gap RISK-003 describes.
- Open question: once a real usage pattern exists, is a joint-MIQP
  provider (behind an optional dependency, matching the `adapters/
  dashboard_render/` lazy-import pattern for `openpyxl`) worth adding
  alongside this heuristic, rather than replacing it?

## Exceptions

None.
