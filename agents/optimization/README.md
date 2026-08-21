# Optimization Agents

The Optimization group covers mathematical programming, sequential decisioning, allocation, routing, scheduling, resource, and finance-specific optimization problems.

## Group Workflow

```text
optimization_orchestrator -> problem_formulation -> specialist optimizer -> solver_diagnostics_sensitivity -> risk/testing/deployment
```

A registered plugin model (`model_plugin_registration/`) slots in as an
alternative to a specialist optimizer: `problem_formulation` scopes the
problem, `model_plugin_registration` ingests and reviews the registration
before the plugged-in model runs in place of a built-in solver, and
`solver_diagnostics_sensitivity` reviews its output the same way either way.

## Agents

| Agent | Handles |
| --- | --- |
| `optimization_orchestrator/` | Routes optimization requests across formulation, solver, domain, validation, and deployment agents. |
| `problem_formulation/` | Turns an ambiguous business objective into variables, objective functions, constraints, data contracts, and acceptance criteria. |
| `model_plugin_registration/` | Ingests a registered internal-model manifest entry, checks contract compliance, and flags unverifiable claims before routing to it. |
| `linear_programming/` | Designs and reviews LPs for allocation, blending, transportation, cash, collateral, and capacity problems. |
| `quadratic_programming/` | Handles convex QPs such as mean-variance portfolios, tracking error minimization, ridge-style penalties, and turnover-aware allocation. |
| `conic_optimization/` | Covers SOCP/SDP-style risk, norm, robust, covariance, and chance-constraint formulations when linear or quadratic forms are too weak. |
| `mixed_integer_optimization/` | Handles binary/integer decisions, fixed charges, lot sizes, cardinality, assignment, facility, and portfolio inclusion constraints. |
| `nonlinear_optimization/` | Designs smooth constrained nonlinear programs and reviews gradients, scaling, local minima, and KKT diagnostics. |
| `global_optimization/` | Covers nonconvex search, multi-start, branch-and-bound, Bayesian optimization, evolutionary methods, and heuristic baselines. |
| `stochastic_optimization/` | Handles uncertain objectives and constraints using scenarios, sample-average approximation, recourse, and simulation-backed objectives. |
| `robust_optimization/` | Designs uncertainty sets, worst-case constraints, stress-aware objectives, and robust counterparts for fragile estimates. |
| `dynamic_programming/` | Handles sequential decisions, Bellman recursions, approximate DP, inventory/rebalancing policies, and finite-horizon control. |
| `network_flow/` | Models min-cost flow, max-flow, matching, circulation, funding ladders, collateral chains, and graph-constrained routing. |
| `routing_scheduling/` | Covers vehicle/job/crew scheduling, order routing, latency-aware placement, batching, and calendar/market-window constraints. |
| `inventory_supply_chain/` | Optimizes stock, replenishment, allocation, service levels, safety stock, and multi-echelon supply decisions. |
| `portfolio_construction/` | Handles portfolio weights, constraints, factor exposure, turnover, tracking error, tax lots, capacity, and rebalancing. |
| `collateral_margin_optimization/` | Covers eligibility, haircuts, margin, cheapest-to-deliver collateral, substitutions, liquidity buffers, and regulatory constraints. |
| `execution_optimization/` | Optimizes trading schedules, participation, venue choice, order slicing, market impact, slippage, and fill-risk trade-offs. |
| `resource_capacity_optimization/` | Handles compute, staffing, capital, balance sheet, quota, API, cloud, and throughput allocation under constraints. |
| `pricing_revenue_optimization/` | Covers bid/ask, rebates, fee schedules, markdowns, elasticity, acceptance probabilities, and revenue-vs-risk trade-offs. |
| `simulation_optimization/` | Uses Monte Carlo, digital twins, response surfaces, and common-random-number comparisons when closed-form objectives are unavailable. |
| `solver_diagnostics_sensitivity/` | Reviews solver status, infeasibility, duals, shadow prices, slacks, degeneracy, scaling, and sensitivity analysis. |

## Inputs

- Current `spec.md`, `plan.md`, `tasks.md`, or handoff memo when available.
- Business decision, objective, constraints, and risk limits.
- Data contracts, source provenance, point-in-time assumptions, and refresh cadence.
- Runtime expectations for `src/quantsmith/`, notebooks, adapters, or downstream systems.

## Outputs

- Specialist routing plan.
- Spec-ready requirements, risks, acceptance criteria, and task suggestions.
- Method, baseline, validation, monitoring, and deployment recommendations.
- Handoffs to lifecycle agents, data agents, risk, testing, reporting, and adapters.

## Rules

- Keep each specialist narrow and inspectable.
- Promote broad or risky work into `specs/NNNN-slug/` before implementation.
- Use adapters for provider/runtime boundaries and `src/quantsmith/` for executable code.
- Treat this group as decision support and workflow design unless a spec authorizes implementation.
