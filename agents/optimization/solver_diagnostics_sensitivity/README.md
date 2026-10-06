# Solver Diagnostics And Sensitivity

## Purpose

Reviews solver status, infeasibility, duals, shadow prices, slacks, degeneracy, scaling, and sensitivity analysis.

## Use When

- A workflow needs solver diagnostics expertise during Specify, Plan, Implement, Verify, or Operate.
- A broad request needs to be decomposed into variables, data, assumptions, tests, and handoffs.
- Existing code, notebooks, solver runs, or model artifacts need a focused review before promotion to a spec.

## Inputs

- Business decision, objective, or model purpose.
- Candidate data sources, freshness, grain, and point-in-time availability.
- Constraints, costs, service levels, risk limits, and operational policies.
- Current spec, plan, tasks, run card, or experiment artifacts when available.

## Outputs

- A scoped recommendation or review finding.
- Required inputs, assumptions, risks, and acceptance criteria.
- Handoff notes for adjacent agents and lifecycle stages.
- Spec-ready requirements, tasks, tests, and monitoring hooks when the work should be promoted.

## Example Requests

- "Frame this as a spec-driven workflow and identify the specialist agents needed."
- "Review this design for leakage, infeasibility, instability, or missing constraints."
- "Turn this notebook/prototype into a production-oriented plan and test checklist."

## Required Review Themes

- Decision alignment and baseline.
- Data availability, point-in-time semantics, and provenance.
- Assumptions, constraints, costs, and operational limits.
- Validation design and monitoring after launch.

## Runtime

Spec `0098` (`src/quantsmith/test_engineering/`) gives solver review something to run: `kkt_check_quadratic` certifies a returned point
(primal feasibility, stationarity, multiplier signs, complementary slackness; a global optimum only for convex problems), and
`check_solver_on_instances` runs a solver on seeded LP/QP instances whose optimum is known by construction, with scaling and
relaxation checks. Report the measured residuals and the seed, not only a verdict.
