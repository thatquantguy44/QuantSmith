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

## Mutation testing of the helpers (the `0097` runtime run on the `0098` code)

The helpers were mutation-tested with `quantsmith-test-engineering mutate` against `tests/test_model_testing_helpers.py` (the slower solver tests were left out
of the loop). Every run reported `import_check: verified`, meaning the tests imported the mutated copy. That check exists because the first attempt did not:
see `0097/validation.md`. `generators`, `ml_checks` and `optimization_checks` were sampled at 120 mutants each (of 154, 162 and 238); the other five modules
were run in full. Mutants outside the sample were not assessed.

| Module | First run, killed / survived (score) | After round 1 | Final |
| --- | --- | --- | --- |
| `_compare` | 28 / 12 (0.70) | 49 / 1 (0.98) | 49 / 1 (0.98) |
| `_guard` | 5 / 2 (0.71) | 6 / 1 (0.86) | 6 / 1 (0.86) |
| `differential` | 28 / 10 (0.74) | 36 / 1 (0.97) | 37 / 0 (1.00) |
| `generators` | 66 / 52 (0.56) | 103 / 15 (0.87) | 109 / 9 (0.92) |
| `metamorphic` | 75 / 28 (0.73) | 95 / 8 (0.92) | 95 / 8 (0.92) |
| `ml_checks` | 76 / 25 (0.75) | 90 / 13 (0.87) | 93 / 10 (0.90) |
| `optimization_checks` | 78 / 31 (0.72) | 89 / 23 (0.79) | 92 / 20 (0.82) |
| `regression_checks` | 61 / 33 (0.65) | 73 / 21 (0.78) | 73 / 21 (0.78) |
| **Total** | **417 / 193 (0.684)** | **541 / 83 (0.867)** | **554 / 70 (0.888)** |

After the final run, three more survivors that were real gaps (not equivalent) were closed with assertions and each was re-checked on its own line with the
same tool, all killed: `ml_checks` L108 (the reported worst deviation when only a middle run differs), `optimization_checks` L41 (the NNLS iteration cap
is exact: it does one iteration of work before stopping) and `regression_checks` L70 (`cases=0` reports `evaluated == 0`). These are not in the table.

### Defects and hazards the mutation results exposed

1. **`compare_values` let a finite value agree with an infinity.** At default tolerances `rtol * |inf|` is `inf`, so `|a - b| <= inf` held: `5.0` agreed with
   `inf` and `+inf` agreed with `-inf`, and `compare_implementations` reported `agree` when the reference overflowed. With `rtol=0` the same arithmetic gave
   `0 * inf = nan` and two equal infinities disagreed. This was in already-pushed code. An infinite or NaN expected value is now matched only by itself.
2. **`compare_implementations` ranked its worst case backwards.** A finite deviation outranked an infinite one, so an exception-versus-return mismatch could
   never be the worst case. The largest deviation now wins and a non-numeric difference counts as infinite.
3. **A leaked timer was undetectable.** Mutating the `setitimer(..., 0)` that disarms the timeout to `1` left a one-second timer armed after every guarded call, which
   would later kill the host process with `SIGALRM`, and no test noticed. There is now a test that no timer or handler is left behind.
4. **Untested branches:** the non-convergent NNLS path and the residual it reports, the combined inequality and equality KKT recovery, the relative stationarity
   tolerance, the numerical convexity tolerance, the failure-list caps, malformed solver results, and several relation edge cases (scalar input, bad axis, empty
   input, out-of-range index).

### The 67 survivors that remain (after the three above) and why they are accepted

| Kind | Count | Why accepted |
| --- | --- | --- |
| Default argument values (`timeout_s=10.0`, `n_obs=200`, `seed=0`, ...) | 15 | A different default is a different valid default; the tests exercise explicit values |
| RNG stream ids and seed-space sizes (`rng_for(seed, i, 1)`, `2 ** 31 - 1`) | 18 | Any value gives a valid independent stream; the tests assert properties, not particular draws |
| `reshape(-1)` | 11 | NumPy treats any negative dimension as "infer", so `-2` behaves like `-1` |
| Ranges of random distributions (`uniform(0.5, 2.0)`, ...) | 7 | The properties hold for any positive range; the tests pin the ranges' observable bounds where they matter |
| Iteration caps, numerical tolerances and one division guard in NNLS, KKT and the orthogonality measure | 10 | Numerical thresholds with no behaviour to pin short of a boundary case; the inner NNLS step changes the path to the answer, not the answer |
| `max(0, repeats)` loop bounds in the determinism and noise-feature checks | 2 | With zero repeats the loop runs once and still ends `nothing_checked` |
| The `0.5 * common + sqrt(0.75) * idio` sign in `return_panel` | 1 | The idiosyncratic term is symmetric, so its sign does not change the distribution |
| `rows.shape[0] >= n and rank == n` in `convex_instance` | 2 | `shape[0]` to `shape[1]` is equivalent because the rank test already implies enough rows. `and` to `or` differs only for a rank-deficient active set, which a continuous Gaussian `A` produces with probability zero; this one is almost surely equivalent, not provably |
| The three-standard-deviation threshold for `placebo_scores_high` | 1 | A tunable statistical threshold, documented, not pinned at its boundary |

A mutation score measures how tightly the tests pin behaviour, not whether the code is right: equivalent mutants cannot be killed and the sampled modules were
not exhaustively assessed.

## Limits of this validation

Two solvers, small convex problems (3–8 variables), synthetic data. `solve_lp` was tested only in its `x ≥ 0` form and `solve_portfolio` only
long-only with a budget equality and box bounds (the gross cap never binds there). Not covered: `solve_milp`, `min_cost_flow`, `solve_dp`,
infeasible or unbounded inputs through the instance runner (the runner builds feasible, bounded, non-degenerate problems), ill-conditioned or
large problems, and non-convex objectives (KKT would show a stationary point only). The checks find evidence of a defect when they fail; passing
is not a proof of correctness.
