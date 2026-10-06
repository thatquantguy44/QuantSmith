# Plan: Model Testing Helpers (Metamorphic, Differential, and Model Checks)

- **Spec:** 0098-model-testing-helpers (`spec.md`)
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-06

> HOW. Requires the Draft spec; `tasks.md` tracks status.

## Approach

Extend `quantsmith.test_engineering` with modules that test model *behaviour*. Every check returns a plain dictionary (JSON-ready) with
`status`, the measured numbers, the seed that reproduces it, and a `limits` statement, so a person, CI or the orchestrator agent reads it the
same way as a `0097` report. All randomness comes from a local `numpy.random.Generator` built from a recorded seed, with independent
sub-streams per case, so a failure reproduces from `(seed, case)` and the global NumPy state is never touched.

The most useful idea is a *constructed* problem: choose the answer first, then build the problem around it. For a convex LP/QP, pick `x*`,
pick which constraints are active and their multipliers, and solve for the objective coefficients that make `x*` satisfy the KKT conditions.
The optimum is then known without an oracle, and an independent KKT check can certify what a solver returns. Regression data is built the
same way from known coefficients. Where an independent oracle exists (SciPy), tests use it as a second opinion, never as a library dependency.

Evaluated callables run under a per-case timeout with every exception captured. A relation or comparison that could not evaluate any case is
`inconclusive` (exit `2`), never a pass.

## Architecture & Components

```
src/quantsmith/test_engineering/
  _guard.py              call_guarded(fn, args, timeout_s) -> (kind, value | exception); positional-argument twin of edgecases._call
  generators.py          rng_for, InputSpec/parse_input_spec, generate_inputs, spd_matrix, return_panel,
                         regression_dataset, ConvexInstance + convex_instance (known optimum by KKT construction)
  metamorphic.py         Relation constructors (scaling, translation, permutation, idempotence, monotone, symmetry) + check_relation
  differential.py        compare_implementations
  optimization_checks.py kkt_check, kkt_check_quadratic, check_solver_on_instances (known optimum, KKT, scaling, relaxation)
  regression_checks.py   check_coefficient_recovery, check_feature_scaling_equivariance, check_row_permutation_invariance,
                         check_residual_orthogonality, check_regression
  ml_checks.py           check_determinism, check_shuffled_label_placebo, check_noise_features, check_beats_baseline,
                         holdout_split, r2_score, accuracy
  cli.py                 + metamorphic, differential subcommands (lazy imports, like the 0097 ones)
tests/test_model_testing_helpers.py
```

## Interfaces & Data Contracts

- Status vocabulary: relation-type checks return `holds | violated | inconclusive | nothing_checked`; `compare_implementations` returns
  `agree | disagree | inconclusive | nothing_compared`. Exit codes: `0` holds/agree, `1` violated/disagree, `2` inconclusive/nothing/bad input.
- Common fields: `seed`, `cases`, `status`, `limits`, and, on failure, `counterexample` / `worst_case` with the case index so
  `rng_for(seed, case)` regenerates it.
- Callable conventions: relation and differential checks call `fn(x)` where `x` is a NumPy array (or any object when `inputs=` is given);
  regression `fit(X, y) -> coef` with the intercept first when `intercept=True`; ML `fit_predict(X_train, y_train, X_test) -> predictions`;
  solver `solve(instance) -> (x, objective) | None`.
- `ConvexInstance`: `Q` (zero for LP), `q`, `A`, `b`, `nonneg`, `x_star`, `objective_star`, `unique_x`, `seed`; methods `scaled(k)`, `relaxed(delta)`,
  `objective(x)`, `gradient(x)`. Form: minimise `½x'Qx + q'x` subject to `Ax ≤ b` (and `x ≥ 0` when `nonneg`).
- KKT: minimise `f`, constraints `g(x) ≤ 0`, `h(x) = 0`; `∇f + G'λ + H'ν = 0`, `λ ≥ 0`, `λᵢgᵢ = 0`. With no supplied multipliers the active set is
  `{i : gᵢ ≥ −tol_active}` and `(λ, ν)` come from a non-negative least squares fit (own implementation, Lawson–Hanson) so no SciPy is needed.
  Reported: `primal_violation`, `stationarity_residual`, `multiplier_sign_violation`, `complementarity_violation`, `satisfied`, `failed[]`,
  `certifies_optimality` (true only when the problem is declared convex).
- ML defaults: chronological holdout (last `test_fraction`), so time-ordered data is never shuffled into the training set; placebo permutes
  **training labels only** and scores against the true held-out labels; `p = (1 + #{placebo ≥ real}) / (1 + n_placebo)`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Constructed problems have known answers; chronological holdout default; zero cases never `holds`; seeds recorded |
| P5 Reversibility | yes | Additive modules; no dependency change; delete the modules, test and CLI additions to roll back |
| P6 Observability | yes | Measured residuals, worst cases, seeds and `limits` in every report |
| P9 Security & data | yes | In-process callables under timeout, owner-authorised use stated, no network, no writes |
| P10 Honest reporting | yes | `inconclusive` and `nothing_checked` are distinct from a pass; KKT certifies only convex problems; agreement is not correctness |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `generators.py` | T-001 |
| REQ-002 | `metamorphic.py`, `_guard.py` | T-002 |
| REQ-003 | `differential.py` | T-003 |
| REQ-004 | `regression_checks.py` | T-005 |
| REQ-005 | `optimization_checks.py`, `ConvexInstance` | T-004 |
| REQ-006 | `ml_checks.py` | T-006 |
| REQ-007 | `cli.py` | T-007 |
| REQ-008 | worked examples in `tests/`, `validation.md` | T-008 |
| REQ-009 | indexes, agents, `instructions/test_engineering.md`, `docs/sdk_plan.md` | T-009 |
| NFR-001 | `rng_for`, local generators | T-001 |
| NFR-002 | `limits` field in every report | T-002, T-003, T-004, T-005, T-006 |
| NFR-003 | numpy only in library; oracles behind `importorskip` | T-004, T-008 |
| NFR-004 | `_guard.call_guarded` | T-001, T-002 |
| NFR-005 | gates, lockfile, full suite | T-010 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Input generation | Seeded NumPy generators | Hypothesis | No dependency; a failure reproduces from a seed; shrinking is the cost, revisited if needed |
| Known answers | Construct the problem around the optimum (KKT) | Hand-solved examples only; an oracle only | Scales to many random instances without an oracle; an independent oracle still cross-checks in tests |
| Optimality check | KKT with multipliers recovered by own NNLS | `scipy.optimize` in the library | Keeps the library on numpy; NNLS is small and is itself tested against SciPy |
| Relation selection | User picks, docs say when each applies | Infer from the function | Inference would be a guess; a wrong relation gives a false failure (RISK-001) |
| Placebo | Permute training labels, score on true held-out labels | Permute test labels | Tests whether skill depends on the feature–label relationship, which is the claim |
| CLI | `metamorphic`, `differential` only | CLI for every check | The model checks need arrays and structured callables, not a command-line grammar |
| Solver contract | `solve(instance) -> (x, objective) \| None` | Per-solver adapters in the library | One tiny wrapper per solver in the caller's test; the library stays solver-agnostic |

## Validation Strategy

`tests/test_model_testing_helpers.py`: each check is run on a case that must pass and a case that must fail (a mutation-style proof that the
check can detect what it claims to detect), plus determinism, global-state and zero-case tests. Own NNLS and `ConvexInstance` optima are
cross-checked against SciPy (`importorskip`). Worked examples apply the helpers to `solve_lp` and `solve_portfolio`; results go in
`validation.md`. Gates, ruff, `uv lock --check`, full suite.

## Rollout, Observability & Rollback

Additive. Rollback: delete the new modules, the test file, the two CLI subcommands, and this spec; revert the doc and agent edits.

## Follow-on scope (not built)

| Item | Sketch |
| --- | --- |
| Hypothesis strategy adapter | Strategies from type hints and the `0097` edge catalog, with shrinking, once Hypothesis is a dependency |
| Stochastic-model statistics | Mean-within-standard-error and distribution tests for simulators and Monte Carlo |
| More certificates | LP/QP duality gap, MILP bound checks, cvxpy status and duals |
| scikit-learn / statsmodels examples | `check_estimator` bridge and worked regression comparisons |
| CLI for model checks | Once a file-based instance format is agreed |
