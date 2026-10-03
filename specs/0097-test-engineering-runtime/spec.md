# Spec: Test Engineering Runtime (Python and C++)

- **ID:** 0097-test-engineering-runtime
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-03

> WHAT and WHY only. Gives the contract-only test-engineering agents (`test_engineering_orchestrator`, `python_test_engineer`, `cpp_test_fuzz_engineer`) something real to run. Items 6–9 of the roadmap are scoped in `plan.md`, not built here.

## Problem & Context

The repository has three test-engineering agents that describe how to test Python and C++ but no code behind them: nothing detects a
project's stack, runs its tests in a uniform way, probes a function at its edges, asks whether the tests would notice a bug, or checks
whether a green suite is actually stable. A lead data scientist starting on a new codebase needs those five things on day one. Each has
well-known failure modes the runtime must not hide: zero collected tests reported as a pass, a mutation score inflated by code no test
runs, a "no flakiness" verdict from a single run, and a C++ crash in one boundary case masking the others.

## Goals

- Detect the stack (languages, frameworks, test directories, available tools) and suggest commands without running anything.
- Run pytest, CTest and GoogleTest binaries through one result model with an honest verdict.
- Generate edge-case probes for Python functions and C++ functions, with sanitizers for C++.
- Mutation-test a Python file and separate weak assertions from uncovered code.
- Classify tests as stable, flaky, order-dependent, or hash-seed-dependent from repeated, shuffled and reseeded runs.
- Expose all of it as one command line printing JSON, with exit codes a CI job can use.

## Non-Goals

- No JavaScript or TypeScript runtime (detected and reported as unsupported); no Java or Go.
- No property-based, differential or metamorphic helpers, diff-aware test selection, fuzz harness, or end-to-end workflow (items 6–9, scoped in `plan.md`).
- No claim that findings prove a defect or that their absence proves correctness; the output is evidence for a human.
- No network access, no installation of tools, no modification of the project under test (mutation runs on a temporary copy).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The runtime shall detect Python and C++ projects (and report JavaScript/TypeScript as unsupported) with evidence, frameworks, test directories, suggested commands, sanitizer flags, registered CTest tests and the available toolchain, skipping build and virtual-environment directories and symlinks, without executing project code. | must |
| REQ-002 | The runtime shall run pytest, CTest and GoogleTest binaries as argv lists (never through a shell) with a timeout that kills the whole process group, an output cap, and a clear `ToolMissing` error when a tool is absent. | must |
| REQ-003 | The runtime shall report per-test results in one model (`passed`, `failed`, `error`, `skipped`) parsed from JUnit or GoogleTest XML with a size cap, and a verdict of `passed`, `failed`, `no_tests`, `timeout` or `error` in which zero tests is never `passed`. | must |
| REQ-004 | The runtime shall parse AddressSanitizer, UndefinedBehaviorSanitizer, LeakSanitizer, ThreadSanitizer and MemorySanitizer output into findings with sanitizer, kind, location and frames. | must |
| REQ-005 | The runtime shall probe a Python function one parameter at a time across a boundary catalog (integers, floats including NaN and infinities, strings, bytes, dates, decimals, containers, `None`), with a per-call timeout, and flag undocumented exceptions, crash-like exceptions on valid input, hangs, non-finite results from finite inputs, and mutation of an input; exceptions the caller documents shall not be flagged. | must |
| REQ-006 | The runtime shall generate characterization tests from a probe that record current behaviour and say they do not assert correctness. | should |
| REQ-007 | The runtime shall compile a C++ function's boundary-value harness with sanitizers and run each case in its own process, reporting compile failure as `built: false` (never as success), unsupported parameter types as an error, and crash, timeout, nonzero exit and sanitizer findings per case. | must |
| REQ-008 | The runtime shall apply single-point AST mutations (arithmetic, comparison, boolean, `not`, condition negation, constants, boolean constants, return value, augmented assignment) to one Python file inside a temporary copy, refuse a failing baseline, skip docstrings, and report mutants as killed, survived or uncovered, with the score computed over covered mutants only. | must |
| REQ-009 | The runtime shall classify tests as `stable`, `flaky`, `order_dependent`, `hash_seed_dependent` or `always_fails` from repeated runs, seeded shuffled runs of explicit node ids, and varied `PYTHONHASHSEED`, and for GoogleTest from repeats and `--gtest_shuffle` with fixed seeds; reproduction details (seed) shall be reported, a shuffled run that cannot execute shall be reported rather than ignored, and a run with no tests shall never read as stable. | must |
| REQ-010 | The runtime shall provide the `quantsmith-test-engineering` command with `detect`, `run`, `edges`, `cpp`, `mutate` and `flaky` subcommands that print JSON and exit `0` (nothing to flag), `1` (findings) or `2` (could not run), and pass arguments after `--` to the test runner. | must |
| REQ-011 | The SDK shall add `coverage` to the `dev` extra with a refreshed `uv.lock`, update the three test-engineering agents to name the runtime, and list the spec in the indexes. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Safety | Argv only, no shell; process-group kill on timeout; output and XML size caps; the project tree is never modified. |
| NFR-002 | Honesty | Every report states what it cannot show (boundary values find undefined behaviour not wrong answers; stable over N runs is not deterministic; survivors may be equivalent mutants). |
| NFR-003 | Dependencies | Runtime code is standard library; `coverage` is optional and its absence is a stated limitation, not a crash. |
| NFR-004 | Gates | All gates pass and no existing test regresses; the lockfile is current. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given Python, C++ and JavaScript projects, when detected, then each is reported with evidence, build and dependency directories are skipped, and JavaScript is listed as unsupported. | REQ-001 |
| AC-002 | Given a string argv, a hung process and a flood of output, when run, then the string is rejected, the process group is killed on timeout, and output is capped; and a missing tool yields `ToolMissing` and exit `2`. | REQ-002, REQ-010 |
| AC-003 | Given passing, failing and empty test directories, when run, then verdicts are `passed`, `failed` and `no_tests` or `error`; and JUnit and GoogleTest XML (including an oversized file) parse or are rejected as specified. | REQ-003 |
| AC-004 | Given sample sanitizer output for each sanitizer, when parsed, then kind and sanitizer are recovered and clean text yields no findings. | REQ-004 |
| AC-005 | Given functions that divide by zero, index an empty list, raise a documented exception, and mutate their input, when probed, then the first, second and fourth are flagged and the third is not. | REQ-005, REQ-006 |
| AC-006 | Given a C++ header with signed overflow, a null dereference and a safe function, when probed with a compiler present, then the first two report sanitizer findings, the safe one reports none, and a missing symbol reports a compile failure. | REQ-007 |
| AC-007 | Given a tested function, an untested function and an unpinned function, when mutated, then the working tree is unchanged, the untested lines are `uncovered`, a weak assertion produces a survivor, and a failing baseline refuses to score. | REQ-008 |
| AC-008 | Given tests that are flaky, order-dependent and hash-seed-dependent, when checked, then each is classified with its seed, stable tests stay stable, JUnit ids convert to node ids, and an empty directory does not read as stable. | REQ-009 |
| AC-009 | Given the command line, when each subcommand runs, then it prints JSON, exits `0`/`1`/`2` as specified, and forwards arguments after `--`. | REQ-010 |
| AC-010 | Given the repository, when gates, ruff, `uv lock --check` and the full suite run, then no gate has findings and no previously passing test fails; the agents and indexes agree. | REQ-011, NFR-001, NFR-002, NFR-003, NFR-004 |

## Data & Dependencies

Depends on the test-engineering agents (`agents/test_engineering/`), the spec-driven gates, and the `dev` extra. Needs `pytest`; optional
`coverage` (mutation uncovered-versus-survived), a C++ compiler (`clang++` or `g++`) with sanitizers, and CMake/CTest and GoogleTest for those
adapters. Test data is synthetic. Kaggle's software-defect datasets are tabular metrics, not code; real validation corpora (BugsInPy, IDoFT,
ReproFlake) belong in the gitignored `knowledge_local/` if used.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Probing or mutating executes untrusted code. | Arbitrary code runs on the host. | Documented as owner-authorised only; argv only; mutation in a temporary copy; no network. |
| RISK-002 | Mutation score is read as test quality. | False assurance. | Uncovered separated from survived; equivalent-mutant caveat; score over covered mutants only. |
| RISK-003 | Rerun-based flakiness misses rare flakes. | A flaky test is called stable. | Verdict names the number of runs; "no flakiness observed" never "deterministic". |
| RISK-004 | CTest/GoogleTest paths are untested against real tools. | Adapter bugs surface in the field. | Exercised with XML fixtures and a stand-in binary, labelled as such; real-tool test when installed. |
| RISK-005 | Sanitizer output formats change across compiler versions. | Findings missed. | Parsers tolerate unknown lines; raw stderr is kept in the outcome. |
| RISK-006 | Characterization tests are mistaken for correctness tests. | Bugs pinned as expected behaviour. | Generated file states it records current behaviour only. |

## Assumptions & Open Questions

- Assumption: POSIX (macOS/Linux) is the target; process-group kill and SIGALRM timeouts are POSIX-only.
- Open question: which first real codebase to point this at, and whether its tests are deterministic enough for mutation scoring.
- Open question: whether Hypothesis becomes a dependency for item 6 (see `plan.md`).

## Exceptions

None.
