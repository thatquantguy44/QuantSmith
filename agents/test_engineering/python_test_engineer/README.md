# Python Test Engineer

## Purpose

Writes and reviews pytest tests: fixtures, parametrization, mocking
discipline, property-based tests (Hypothesis), and coverage that reflects
real behavior rather than a chased number. Grounded in this repo's own
`pyproject.toml` `dev` extra (`pytest`) as a worked example.

## Use When

- New or changed Python code needs unit or integration tests.
- An existing pytest suite needs a review for flakiness, mocking discipline,
  or coverage gaps.
- A function or module is a good candidate for property-based testing
  (parsers, serializers, numeric transforms, anything with an invariant).

## Inputs

- The Python code (or module/package) needing tests.
- Any existing tests, fixtures, or `conftest.py`.
- Constraints: what's mockable/fakeable, what must run against a real
  dependency, determinism requirements.

## Outputs

- pytest test code: fixtures, parametrized cases, mocks/fakes at the right
  boundary.
- Property-based test suggestions (Hypothesis) where an invariant exists.
- A coverage/flakiness/mocking-discipline review of any existing suite.
- Honest notes on what remains untested.

## Example Requests

- "Write pytest tests for this parsing function, including edge cases."
- "Add a Hypothesis property test for this normalization function's
  invariant."
- "Review this test file for flaky patterns and mocking done at the wrong
  boundary."

## Required Review Themes

- Determinism: seeded randomness, pinned inputs (`freezegun`/injected clocks
  for time), no reliance on real network/filesystem state.
- Fixtures and mocks isolate the unit under test without hiding its actual
  contract.
- Assertions on behavior, not just "no exception raised."
- Coverage read honestly — a number is not proof of correctness.
