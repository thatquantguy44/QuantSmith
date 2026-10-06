# Validation on the SDK's own solvers

- **Spec:** 0098-model-testing-helpers
- **Date:** 2026-10-06
- **Targets:** `solve_lp` (spec `0013`, `quantsmith.pipelines.optimization_solvers`) and `solve_portfolio` (spec `0007`, `quantsmith.pipelines.portfolio_construction`).
- **Oracle:** `scipy.optimize.linprog` (HiGHS), optional; tests skip without SciPy. All data are synthetic and come from recorded seeds.
- **Where:** the permanent evidence is `tests/test_model_helpers_on_sdk_solvers.py`. Larger exploratory runs made while building are marked *exploratory*; they are not
  re-run by CI.

## Results

| Check | Target | In the suite | Exploratory (larger) | Result |
| --- | --- | --- | --- | --- |
| Constructed optimum, KKT of the returned point, objective scaling, constraint relaxation (`check_solver_on_instances`, `x ≥ 0`) | `solve_lp` | 60 instances at each of 3, 4 and 6 variables × 4 checks | 100 instances at 4 and 6 variables | Every check passed; no defect |
| Differential against `scipy.optimize.linprog` on degenerate integer data, equality rows, `min` and `max` | `solve_lp` | 300 problems | 600 problems | Status (optimal, infeasible, unbounded) and objective agreed on every problem; no defect |
| KKT certificate of the returned weights (budget equality, box bounds) | `solve_portfolio` | 10 problems of 3–8 names; 3 with a turnover penalty | 100 problems of 3–8 names | Satisfied at `1e-6` every time; worst stationarity residual `5.4e-16`, worst primal violation `2.2e-16`. `γΣ` is positive semi-definite, so the KKT pass certifies a global optimum |
| Discrimination: does KKT fail when the solver stops early? | `solve_portfolio` | one problem | — | Stationarity residual `4.9e-2` at 1 iteration, `3.5e-2` at 3, `2.3e-4` at 20, `5.6e-17` at the default 4000: it fails when unconverged and passes when converged |
| Asset-permutation equivariance (solve then permute versus permute then solve) | `solve_portfolio` | 8 problems | — | Agreed to `rtol 1e-7` |
| Weakly decreasing portfolio variance in risk aversion `γ` | `solve_portfolio` | 8 values of `γ` in `[0.5, 20]` | — | Held; the wrong direction (`increasing`) was reported `violated`, so the relation can fail |
| Own non-negative least squares against `scipy.optimize.nnls` | the KKT multiplier recovery | 100 random problems | 300 | Residual norms agree to `1.6e-14` |

## Answers to the spec's open questions

- *Does `solve_portfolio`'s projected-gradient solution meet KKT at a tolerance a reviewer would accept?* Yes, at `1e-6` and in practice at
  machine precision, on well-conditioned problems of 3–8 names at the default 4000 iterations. It does **not** at 1–20 iterations, so the check is
  sensitive to the iteration count.
- *Which quant relations first?* Asset-permutation equivariance and risk-aversion monotonicity worked on the first try and are in the suite.

## Defects in the SDK found

None. `solve_lp` and `solve_portfolio` passed every check on this sample. That is a statement about this sample, not a proof of correctness.

## Defects in this build that validation exposed (all fixed, each with a regression test)

1. `compare_implementations` through the command line collapsed `--target` and `--reference` into one entry when they named the same function,
   reporting a confusing "give at least two implementations". It now says the two must be different.
2. A shuffled-label placebo with fewer than 19 fits cannot reach `p ≤ 0.05` even for a perfect model, and reported `violated`. It now reports
   `inconclusive` and says how many placebo fits are needed.
3. A stand-in QP solver built on SciPy SLSQP at `ftol=1e-14` reported no optimum on scaled problems ("positive directional derivative", below
   SLSQP's noise floor). The runner correctly counted it as a failure; the stand-in now uses `1e-12`.
4. Two of this suite's own assertions were vacuous or tested nothing (a stray `or` that made an assertion always true, and a "symmetric output"
   permutation case that did not exercise symmetry). Found on review, replaced with assertions that can fail.

## Limits of this validation

Two solvers, small convex problems (3–8 variables), synthetic data. `solve_lp` was tested only in its `x ≥ 0` form and `solve_portfolio` only
long-only with a budget equality and box bounds (the gross cap never binds there). Not covered: `solve_milp`, `min_cost_flow`, `solve_dp`,
infeasible or unbounded inputs through the instance runner (the runner builds feasible, bounded, non-degenerate problems), ill-conditioned or
large problems, and non-convex objectives (KKT would show a stationary point only). The checks find evidence of a defect when they fail; passing
is not a proof of correctness.
