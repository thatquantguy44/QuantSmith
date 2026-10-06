# quantsmith.test_engineering

Runtime for the test-engineering agents (spec `0097`): Python and C++, JSON out, no shell, no network.

```sh
quantsmith-test-engineering detect --root .
quantsmith-test-engineering run    --tool pytest --root . -- -k fast
quantsmith-test-engineering edges  --target pkg.mod:func --allow ValueError --hint name=str --write-tests tests/test_func_edges.py
quantsmith-test-engineering cpp    --header lib.hpp --signature "int add(int a, int b)" --root .
quantsmith-test-engineering mutate --target src/pkg/mod.py --root .
quantsmith-test-engineering flaky  --tool pytest --root . --runs 5 --shuffles 3
```

Use `--python PATH` to run a project's tests with the project's interpreter and `--env KEY=VALUE` (repeatable) for
environment-dependent behaviour. Untyped functions need `--hint name=type`; a probe that tested nothing exits `2`.

Exit status: `0` nothing to flag, `1` findings, `2` could not run. From a checkout, use
`python -m quantsmith.test_engineering.cli` if the entry point is not installed.

| Module | Role |
| --- | --- |
| `detect` | languages, frameworks, tools, suggested commands (runs nothing) |
| `runners`, `junit`, `report` | pytest / CTest / GoogleTest through one result model; zero tests is never a pass |
| `edgecases` | boundary catalogs and a one-parameter-at-a-time probe for Python; characterization tests |
| `cpp_harness`, `sanitizers` | boundary harness compiled with ASan/UBSan, one process per case |
| `mutation`, `coverage_adapter` | AST mutants on a temporary copy; uncovered kept apart from survived |
| `flaky` | reruns, seeded shuffles of node ids, `PYTHONHASHSEED` variation |

## Model-behaviour checks (spec `0098`)

Runtime code for testing *models* (regressions, ML, optimizers) rather than code paths. `numpy` only; SciPy is used by the
tests as an oracle, never imported by the library. Every check is seeded and returns a JSON-ready dict with a `status`
(`holds` / `violated` / `inconclusive` / `nothing_checked`), the seed that reproduces it, and a `limits` statement.

```sh
quantsmith-test-engineering metamorphic  --target pkg.mod:fn --relation scaling --param degree=1 --input vector:5
quantsmith-test-engineering differential --target pkg.mod:new --reference pkg.mod:old --input vector:5 --rtol 1e-9
```

Relations: `scaling`, `translation`, `permutation`, `idempotence`, `monotone`, `symmetry`. Inputs: `scalar`, `vector:N`, `matrix:RxC`, `spd:N`.
Exit `0` holds/agree, `1` violated/disagree, `2` inconclusive, no cases, or bad input.

The checks that need arrays and callables are Python API:

```python
from quantsmith.test_engineering.generators import convex_instance
from quantsmith.test_engineering.optimization_checks import check_solver_on_instances, kkt_check_quadratic
from quantsmith.test_engineering.regression_checks import check_regression
from quantsmith.test_engineering.ml_checks import check_shuffled_label_placebo, check_determinism, check_beats_baseline

check_solver_on_instances(my_solver, kind="qp", cases=50)         # known optimum, KKT, objective scaling, constraint relaxation
kkt_check_quadratic(Q, q, x, A_ub=A, b_ub=b, lower=0.0)           # certificate for a returned point (global optimum if convex)
check_regression(fit, penalized=False)                            # recovery, scaling equivariance, row permutation, orthogonality
check_shuffled_label_placebo(fit_predict, X, y)                   # skill must beat a model trained on shuffled labels
```

| Module | Role |
| --- | --- |
| `generators` | seeded inputs; regression data with known coefficients; convex LP/QP built around a chosen optimum |
| `metamorphic`, `differential` | relation and implementation-comparison checks on any callable |
| `optimization_checks` | KKT certificate (own non-negative least squares), solver runner on constructed instances |
| `regression_checks`, `ml_checks` | least-squares properties; determinism, placebo, noise-feature and baseline checks |

Choose relations you can justify: a ridge fit is not scale-equivariant, so `check_regression(penalized=True)` skips what does not apply. A passing
check is evidence, not proof; agreeing implementations can share a bug; KKT certifies a global optimum only for convex problems.
`validation.md` in `specs/0098-model-testing-helpers/` records what these checks found on `solve_lp` and `solve_portfolio` (no defects).

`mutate` runs your tests against a temporary copy and checks that the tests import that copy rather than an installed one (`import_check` in the
report); if the mutated file is provably not the one imported it exits `2` with `mutated_file_not_imported` instead of printing a meaningless score.
`cpp` uses the first installed compiler that can build and run a sanitizer program and lists each one tried (`compilers_tried`).

Limits worth remembering: probing and mutation **execute your code**, so use them only on code you own or may test;
boundary values find undefined behaviour, not wrong answers; a mutation survivor may be an equivalent mutant; "no
flakiness observed" is not "deterministic". `coverage` is optional (without it, mutation reports no uncovered split).
