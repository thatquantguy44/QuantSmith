# quantsmith.test_engineering

Runtime for the test-engineering agents (spec `0097`): Python and C++, JSON out, no shell, no network.

```sh
quantsmith-test-engineering detect --root .
quantsmith-test-engineering run    --tool pytest --root . -- -k fast
quantsmith-test-engineering edges  --target pkg.mod:func --allow ValueError --write-tests tests/test_func_edges.py
quantsmith-test-engineering cpp    --header lib.hpp --signature "int add(int a, int b)" --root .
quantsmith-test-engineering mutate --target src/pkg/mod.py --root .
quantsmith-test-engineering flaky  --tool pytest --root . --runs 5 --shuffles 3
```

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

Limits worth remembering: probing and mutation **execute your code**, so use them only on code you own or may test;
boundary values find undefined behaviour, not wrong answers; a mutation survivor may be an equivalent mutant; "no
flakiness observed" is not "deterministic". `coverage` is optional (without it, mutation reports no uncovered split).
