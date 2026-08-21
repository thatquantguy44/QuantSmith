# Tasks: Optimization solvers by mathematical form

- **Spec:** 0013-optimization-solvers (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-08

> Reference example. Every task cites a requirement; every acceptance criterion is
> named by a test. Routing agents are noted per task.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests exist and pass deterministically.
- Every solver reports an explicit status; infeasible/unbounded are never a silent
  number.
- No secrets, credentials, or private data introduced; runtime code lives under
  `src/quantsmith/`.
- Docs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Agent | Notes |
| --- | --- | --- | --- | --- | --- |
| T-001 | Implement `solve_lp` (two-phase simplex, Bland's rule) with infeasible/unbounded status. | REQ-001, REQ-002, NFR-001, NFR-002, NFR-003 | done | `linear_programming` | Standard form with slacks + artificials. |
| T-002 | Implement `solve_milp` (branch-and-bound on the LP relaxation). | REQ-003, NFR-001, NFR-002 | done | `mixed_integer_optimization` | Node-bounded; integral integer vars. |
| T-003 | Implement `min_cost_flow` (successive shortest augmenting paths). | REQ-004, NFR-001, NFR-003 | done | `network_flow` | Min-cost max-flow or a required flow. |
| T-004 | Implement `DPProblem` / `solve_dp` (finite-horizon backward induction). | REQ-005, NFR-001 | done | `dynamic_programming` | Optimal value and policy, min or max. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

The runtime is a standard-library-only reference in
`src/quantsmith/pipelines/optimization_solvers.py`. Convex QP is provided separately
by `0007-portfolio-construction`. A production build may swap in a mature solver
(HiGHS, OR-Tools) behind the same interfaces; the statuses and semantics are unchanged.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `tests/test_optimization_solvers.py::test_lp_optimum_AC_001` | done |
| AC-002 | `tests/test_optimization_solvers.py::test_lp_infeasible_and_unbounded_AC_002` | done |
| AC-003 | `tests/test_optimization_solvers.py::test_milp_integer_solution_AC_003` | done |
| AC-004 | `tests/test_optimization_solvers.py::test_min_cost_flow_AC_004` | done |
| AC-005 | `tests/test_optimization_solvers.py::test_dp_backward_induction_AC_005` | done |
| AC-006 | `tests/test_optimization_solvers.py::test_deterministic_AC_006` | done |

## Follow-ups

- Add conic/SOCP, global, and nonlinear forms (need a cone/NLP method or an optional
  dependency).
- Build application specs on these solvers: cardinality-constrained
  portfolio (MILP), funding-ladder min-cost flow, multi-period rebalancing
  DP. (Securities-financing LP work is deliberately out of scope — that
  domain routes to an adopter's own models via `agents/optimization/
  model_plugin_registration/`, spec `0026`, rather than the SDK owning
  the optimization logic itself.)