# Python Test Engineer Tasks

## Write Unit Tests For A Function Or Module

Input: Python code needing test coverage.

Output: pytest tests (fixtures, parametrized cases) grounded in the code's
actual contract, plus named remaining gaps.

## Add A Property-Based Test

Input: code with a real invariant (round-trip, ordering, idempotency).

Output: a Hypothesis property test expressing that invariant, plus a note on
why example-based tests alone wouldn't have caught a violation.

## Review An Existing Suite

Input: an existing pytest test file or directory.

Output: flaky-pattern, mocking-boundary, and coverage-honesty findings,
each tied to a specific test.
