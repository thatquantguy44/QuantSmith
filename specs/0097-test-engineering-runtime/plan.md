# Plan: Test Engineering Runtime (Python and C++)

- **Spec:** 0097-test-engineering-runtime (`spec.md`)
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-03

> HOW. Requires the Draft spec; `tasks.md` tracks status.

## Approach

One small module per concern, all returning plain dictionaries so an agent or CI can read them as JSON. A single result model (`TestResult`,
`RunReport`) sits under every runner; `run_command` is the only place a process is started. Each probe reports what it cannot show. Mutation
runs in a copied tree and uses coverage to split "no test runs this" from "a test runs this but does not check it". Flakiness uses explicit
node ids in a seeded order, so no plugin is needed and a failure reproduces from the printed seed.

## Architecture & Components

```
src/quantsmith/test_engineering/
  report.py            TestResult, CommandResult, RunReport (verdict), ToolMissing
  junit.py             JUnit / GoogleTest XML -> TestResult (size cap)
  sanitizers.py        ASan / UBSan / LSan / TSan / MSan text -> findings
  runners.py           run_command (argv, process-group kill, output cap), run_pytest, run_ctest, run_gtest_binary
  detect.py            detect_stack, toolchain
  coverage_adapter.py  pytest under coverage -> executed / missing lines
  edgecases.py         boundary catalogs, probe_function, generate_pytest_source
  cpp_harness.py       signature parser, harness generator, probe_cpp (sanitizers, one process per case)
  mutation.py          AST operators, run_mutation
  flaky.py             check_pytest, check_gtest, to_node_id
  cli.py               quantsmith-test-engineering
tests/test_test_engineering.py
```

## Interfaces & Data Contracts

- Every subcommand prints one JSON object; exit `0` clean, `1` findings, `2` could not run (`{"error": "tool_missing" | "bad_input", "message"}`).
- `RunReport.verdict`: `passed | failed | no_tests | timeout | error`.
- Probe findings: `{kind, param, label, detail}`; C++ outcomes: `{case_id, param, label, status, returncode, sanitizer: [...]}` with status `ok | exception | sanitizer | crash | timeout | nonzero_exit`.
- Mutation: `{killed, survived, uncovered, score, survivors[], uncovered_mutants[], coverage_used}`; `score` is `None` when the baseline fails or nothing is covered.
- Flakiness: `{verdict: flakiness_found | no_flakiness_observed, classification{}, flaky[], order_dependent[{test, seed}], hash_seed_dependent[]}`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Zero tests never passes; compile failure never success; seeds recorded |
| P5 Reversibility | yes | Additive; mutation on a copy |
| P6 Observability | yes | Raw tails, notes, and limits in every report |
| P9 Security & data | yes | Argv only, caps, no network; owner-authorised use stated |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `detect.py` | T-001 |
| REQ-002 | `runners.run_command`, `require_tool` | T-002 |
| REQ-003 | `report.py`, `junit.py`, runners | T-002 |
| REQ-004 | `sanitizers.py` | T-003 |
| REQ-005 | `edgecases.probe_function` | T-004 |
| REQ-006 | `edgecases.generate_pytest_source` | T-004 |
| REQ-007 | `cpp_harness.py` | T-005 |
| REQ-008 | `mutation.py`, `coverage_adapter.py` | T-006 |
| REQ-009 | `flaky.py` | T-007 |
| REQ-010 | `cli.py` | T-008 |
| REQ-011 | `pyproject.toml`, `uv.lock`, agents, indexes | T-009 |
| NFR-001 | argv, caps, copy | T-002, T-006 |
| NFR-002 | `note` fields | T-004, T-005, T-006, T-007 |
| NFR-003 | stdlib; optional `coverage` | T-006 |
| NFR-004 | gates, lockfile, full suite | T-010 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Shuffle | Explicit node ids in seeded order | A random-order plugin | No dependency; reproducible from the seed |
| C++ cases | One process per case | One process, all cases | A crash or sanitizer abort would hide later cases |
| C++ types | A closed list, others rejected | Guess a value for unknown types | A guessed value is a false test |
| Mutation engine | Own AST operators | `mutmut` / `cosmic-ray` dependency | Small, auditable, runs on a copy; revisit if scale demands |
| Coverage | Optional | Required | Mutation still runs without it, with `coverage_used: false` |

## Validation Strategy

`tests/test_test_engineering.py` (real pytest, real `clang++` with sanitizers, real mutation runs; CTest and GoogleTest via fixtures and a stand-in binary, labelled as such). Gates, ruff, `uv lock --check`, full suite.

## Rollout, Observability & Rollback

Additive. Rollback: delete the package, test, spec, and entry point, and revert the `coverage` extra and lockfile.

## Follow-on scope: items 6–9 (item 6 built as `0098`; 7–9 not built)

| # | Item | Sketch | Depends on | Decision needed |
| --- | --- | --- | --- | --- |
| 6 | **Built as `0098-model-testing-helpers`** (no Hypothesis; seeded generators instead). Original sketch: property, differential and metamorphic helpers | Hypothesis strategies derived from type hints and the edge catalog; differential runner comparing two implementations (old vs new, Python vs C++) on shared inputs; a small library of metamorphic relations (scaling, permutation, idempotence, monotonicity) for numeric and quant functions | `edgecases.py`; Hypothesis (new optional extra) | Add Hypothesis to the `dev` extra? Which quant relations first? |
| 7 | Diff-aware test selection | Map `git diff` hunks to functions and to tests that cover them (coverage contexts), run those first and the rest on a schedule; reuse the mutation line filter to mutate only changed lines | `coverage_adapter.py`, `mutation.line_range` | Per-test coverage cost; fall back to full run when the map is stale |
| 8 | Python fuzz harness | Coverage-guided or Hypothesis-stateful fuzzing of parsers and data loaders with a corpus directory, crash minimisation and replay; C++ fuzz targets (libFuzzer) reuse the sanitizer parser | `cpp_harness.py`, `sanitizers.py` | Atheris dependency vs Hypothesis only; corpus storage under `knowledge_local/` |
| 9 | Orchestrated workflow | One `workflow` subcommand and a workflow doc: detect → run → flaky → edge probes → mutate → report, writing a single evidence report that the `test_engineering_orchestrator` agent consumes | items 1–5 | Report format; thresholds that turn findings into a failing gate |

These become their own specs (`0098` onward) when scheduled.
