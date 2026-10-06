# Spec: Model Testing Helpers (Metamorphic, Differential, and Model Checks)

- **ID:** 0098-model-testing-helpers
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-06

> WHAT and WHY only. Item 6 of the `0097` roadmap, widened from "property, differential and metamorphic helpers" to include
> checks that know what a regression, an ML model and an optimizer should satisfy. Design is in `plan.md`.

## Problem & Context

The `0097` runtime tests *code*: it finds the input that crashes a function, the mutation no test notices, the test that flakes. It cannot
tell whether a *model* is right. A regression, a classifier and a solver can run cleanly, pass every hand-written example and still be wrong:
the coefficients are biased, the "skill" survives shuffled labels, the "optimum" is not optimal. Today the SDK's own model tests are
hand-solved cases and leakage-fold checks; nothing compares a solver with an independent oracle, certifies an optimum, or checks that a model
beats a placebo. A lead data scientist testing models needs these checks to be seeded, reproducible, and honest about what they cannot show.

## Goals

- Generate seeded test inputs for numeric and quant functions, including problems whose correct answer is known by construction.
- Check metamorphic relations (scaling, translation, permutation, idempotence, monotonicity, symmetry) on any numeric callable.
- Compare two or more implementations of the same computation on shared inputs.
- Check regressions for coefficient recovery and the algebraic properties OLS must have.
- Check optimizers: certify an optimum with KKT conditions, compare with a known optimum, and test scaling and relaxation relations.
- Check ML models for determinism, skill over a label-shuffled placebo, absence of skill on noise, and a better-than-baseline score.
- Apply the helpers to the SDK's own LP and portfolio solvers and record what they find.

## Non-Goals

- No Hypothesis, scikit-learn, SciPy, cvxpy or other new runtime dependency. Optional libraries serve only as test oracles.
- No stateful or shrinking property testing, no statistical test suite for stochastic simulators, no gradient checks for deep models, no MILP
  optimality certificate, no leakage detector (the `leakage` gate and `0044` cover look-ahead).
- No claim that a passing check proves a model correct. Output is evidence for a human reviewer.
- No automatic choice of which relations apply to a model; the user selects them and the docs say when each does and does not apply.
- No command line for the regression, optimization and ML checks (they take arrays and callables); only `metamorphic` and `differential`.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall provide seeded generators for vectors, matrices, symmetric positive-definite matrices, return panels, regression datasets with known coefficients, and convex LP/QP instances with a known optimum, using a local random generator (never global state) and recording the seed with every output. | must |
| REQ-002 | The SDK shall check the metamorphic relations scaling, translation, permutation (invariant and equivariant), idempotence, monotonicity and symmetry (even and odd) on a callable over seeded inputs, reporting `holds`, `violated`, `inconclusive` or `nothing_checked`, the largest violation, a counterexample, and the seed; a callable that raises or hangs is reported, never counted as holding. | must |
| REQ-003 | The SDK shall compare two or more implementations on shared seeded inputs within `rtol`/`atol`, reporting `agree`, `disagree`, `inconclusive` or `nothing_compared`, the worst case, and the seed; an exception in one implementation only is a disagreement, a finite value never agrees with an infinite one, the worst case is the mismatch with the largest deviation (a non-numeric difference counts as infinite), and agreement is never reported as correctness. | must |
| REQ-004 | The SDK shall check a regression `fit` for coefficient recovery (exact on noiseless data, within standard errors on noisy data), feature-scaling equivariance, row-permutation invariance, and residual orthogonality, and state which checks do not apply to penalised estimators. | must |
| REQ-005 | The SDK shall certify a candidate solution with KKT conditions (primal feasibility, stationarity with recovered or supplied multipliers, multiplier signs, complementary slackness), run a solver against seeded constructed instances (known optimum, KKT of the returned point, objective-scaling and constraint-relaxation relations), and say that a KKT pass certifies optimality only for convex problems. | must |
| REQ-006 | The SDK shall check an ML `fit_predict` for determinism, for skill over a label-shuffled placebo (permutation p-value), for no skill when features are replaced by noise, and for a score above a stated baseline, using a time-ordered holdout by default. | must |
| REQ-007 | The `quantsmith-test-engineering` command shall provide `metamorphic` and `differential` subcommands that load callables by `package.module:function`, print JSON, exit `0` (holds/agree), `1` (violated/disagree) or `2` (could not run or inconclusive). | should |
| REQ-008 | The helpers shall be exercised against the SDK's own `solve_lp` and `solve_portfolio` (with `scipy.optimize.linprog` as an optional oracle), and every finding, including a defect in the SDK, shall be recorded in `validation.md`. | must |
| REQ-009 | The SDK shall list the spec in the indexes, update the agents and standards that should name the helpers, and add no dependency. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Same seed, same inputs, same report; the global NumPy random state is never read or changed. |
| NFR-002 | Honesty | Every report carries a `limits` statement (relations hold on sampled inputs, not for all inputs; agreement is not correctness; KKT certifies only convex problems; a permutation p-value has resolution 1/(n+1)). |
| NFR-003 | Dependencies | Library code needs only `numpy` (already required); SciPy, scikit-learn and cvxpy are never imported by the library and appear only in tests behind `importorskip`. |
| NFR-004 | Safety | Each evaluated callable runs under a per-case timeout (POSIX) with every exception captured; callables run in this process, so use only code you own or may test; no network; no file writes. |
| NFR-005 | Gates | All gates pass, no existing test regresses, and `uv lock --check` is unchanged. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a seed, when any generator runs twice, then the output is identical; given two seeds, then it differs; and the global NumPy state is unchanged. A constructed LP/QP instance reports a known optimum that an independent oracle confirms. | REQ-001, NFR-001 |
| AC-002 | Given a degree-1 homogeneous function and a non-homogeneous one, when scaling is checked, then the first holds and the second is `violated` with a counterexample. Likewise for permutation, translation, idempotence, monotonicity and symmetry; zero cases is `nothing_checked`; a raising or hanging callable is `inconclusive`. | REQ-002, NFR-004 |
| AC-003 | Given equal, perturbed and exception-raising implementations, when compared, then they `agree`, `disagree` (worst case named) and `disagree` respectively; the same exception type from both is agreement; a finite value against an infinite one (or `+inf` against `-inf`) is a disagreement at any tolerance; the worst case ranks a non-numeric mismatch above a numeric one; zero cases is `nothing_compared`. | REQ-003 |
| AC-004 | Given a least-squares fit and a deliberately biased fit, when regression checks run, then the first passes all four checks and the second fails recovery and orthogonality; a ridge fit is not failed for properties it is documented not to have. | REQ-004 |
| AC-005 | Given the constructed optimum of an LP and a QP, when KKT is checked, then it is satisfied; given a perturbed or infeasible point, then it fails and names the failed condition; given a correct solver and a broken one, then the instance runner passes the first and fails the second with the reproducing seed. | REQ-005 |
| AC-006 | Given a model with real signal, pure-noise data, a model that reads test labels, and an unseeded model, when ML checks run, then the signal model beats its placebo (`p ≤ 0.05`), the noise data does not, the label-reader is flagged, and the unseeded model fails determinism. | REQ-006 |
| AC-007 | Given the command line, when `metamorphic` and `differential` run, then each prints JSON with the exit codes above, and a bad target or relation exits `2` with `bad_input`. | REQ-007 |
| AC-008 | Given `solve_lp` and `solve_portfolio`, when the helpers run against them, then results (including any failures) are recorded in `validation.md` with the seed and tolerance. | REQ-008 |
| AC-009 | Given the repository, when gates, ruff, `uv lock --check` and the full suite run, then no gate has findings and no previously passing test fails; the indexes and agents agree. | REQ-009, NFR-002, NFR-003, NFR-005 |

## Data & Dependencies

Depends on `0097` (`quantsmith.test_engineering`, the timeout pattern, the CLI), `0013`/`0007` (the SDK solvers used as first targets), and
`numpy`. Test data is synthetic and generated from seeds. Optional oracles in tests: `scipy.optimize.linprog` and `scipy.optimize.nnls`
(`quant` extra, installed by CI's `--all-extras`).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A relation is applied to a model it does not hold for (scaling on a ridge fit), producing a false failure that erodes trust. | Findings ignored. | Each relation and check documents when it applies; penalised estimators are excluded by name; a `violated` result prints the relation's assumption. |
| RISK-002 | A passing relation or agreeing implementations are read as correctness. | False assurance. | `limits` in every report; differential agreement never says "correct"; docs say shared bugs agree. |
| RISK-003 | KKT tolerances too tight for iterative solvers (projected gradient) or too loose for exact ones. | False fail or false pass. | Tolerances are explicit parameters, defaults documented, and the report shows the measured residuals rather than only a verdict. |
| RISK-004 | Random-instance tests flake. | Lost trust in the suite. | Every instance derives from a recorded seed; tests use fixed seeds; statistical checks use stated multiples of the standard error. |
| RISK-005 | Evaluating a callable runs untrusted code. | Arbitrary code runs on the host. | Same stance as `0097` `edges`: owner-authorised use stated; no network; no writes. |

## Assumptions & Open Questions

- Assumption: POSIX target (SIGALRM timeouts, main thread), as in `0097`.
- Decision (answers `0097/plan.md` item 6): **Hypothesis is not added.** Seeded NumPy generators are reproducible from a recorded seed and need no
  dependency; shrinking is the one thing lost. Revisit with a thin strategy adapter if shrinking proves necessary.
- Decision: quant relations come first through the generic library plus worked examples on the SDK's solvers (asset-permutation equivariance,
  risk-aversion monotonicity, objective scaling, constraint relaxation).
- Open question: whether `solve_portfolio`'s projected-gradient solution meets KKT at a tolerance a reviewer would accept (answered by REQ-008).
- Open question: which scikit-learn and statsmodels estimators to add as worked regression examples once those libraries are in the project.

## Exceptions

None.
