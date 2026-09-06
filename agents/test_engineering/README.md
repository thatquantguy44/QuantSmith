# Test Engineering Agents

## Purpose

Language-specific test-authoring expertise: idiomatic unit and integration
test structure, mocking and fixture discipline, coverage that means
something, property-based testing, and — for compiled/memory-unsafe code —
fuzzing and sanitizer discipline. Backed by `instructions/test_engineering.md`.

This group answers "how do I test this in this language, well." It does not
answer "is this acceptance criterion actually covered" (`testing_validation`'s
job) or "may this pipeline stage release" (`quality-guard-agent`'s job) — see
**Where This Doesn't Duplicate** below.

## Roster

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `test_engineering_orchestrator/` | Routes a testing request to the right language agent(s) by detected stack; consolidates their output | `python_test_engineer`, `cpp_test_fuzz_engineer`, `javascript_test_engineer`, `typescript_test_engineer` |
| `python_test_engineer/` | pytest: fixtures, parametrization, mocking discipline, property-based tests (Hypothesis), coverage without coverage-chasing | `testing_validation` |
| `cpp_test_fuzz_engineer/` | GoogleTest/Catch2 unit tests, fuzz harnesses (libFuzzer/AFL++), sanitizer discipline (ASan/UBSan/MSan/TSan), corpus/crash triage — authorized targets only | `testing_validation` |
| `javascript_test_engineer/` | Jest/Vitest/Mocha unit and integration tests, mocking/async discipline, DOM/component testing patterns | `testing_validation` |
| `typescript_test_engineer/` | Same runtime tooling as `javascript_test_engineer`, plus type-level testing (tsd/expect-type) and strict-mode discipline | `testing_validation` |

Each language agent also hands its consolidated result to `quality-guard-agent`
when a pipeline-stage release decision is in play, not only to
`testing_validation`.

## Use When

- New or changed code needs unit/integration tests written or reviewed in a
  specific language.
- A C++ (or other memory-unsafe) component needs a fuzz harness, sanitizer
  coverage, or crash triage.
- A test suite needs a coverage/flakiness/mocking-discipline review before
  handoff to `testing_validation` for AC mapping.
- It's unclear which language agent applies — ask
  `test_engineering_orchestrator`, which detects the stack and routes.

## Where This Doesn't Duplicate

- **`testing_validation`** maps acceptance criteria to test evidence and
  reviews quant-specific validity (leakage, look-ahead, sample size,
  determinism of the *result*, not the test's own determinism). This group
  writes/reviews the tests; `testing_validation` decides whether they close
  an `AC-*`.
- **`quality-guard-agent`** is a runtime pipeline gate — schema/contract/PII/
  naming policy, approve-or-reject a stage. This group never makes that
  release call; it hands off passing (or failing) test/fuzz evidence for
  `quality-guard-agent` to weigh.

## Example Requests

- "Write pytest tests for this module, including edge cases and a property-
  based test for the parser."
- "Build a libFuzzer harness for this C++ deserialization function and tell
  me what sanitizers to enable."
- "Review this Jest suite for mocking discipline and flaky-test risk."
- "I have a mixed Python/TypeScript repo — which test agent should I use for
  each part?" (ask `test_engineering_orchestrator`)

## Required Review Themes

- Determinism: seeded randomness, pinned inputs, no hidden state or run-order
  dependence.
- Assertions on actual behavior, not merely "it didn't crash."
- Mocking/fakes only at a boundary the test intends to cross.
- For `cpp_test_fuzz_engineer`: authorized, sandboxed targets only; sanitizers
  enabled by default; crashes minimized and triaged before being reported.
- Honest reporting of what remains untested, unfuzzed, or unconfirmed —
  never a fabricated pass, coverage number, or "no crashes found."
