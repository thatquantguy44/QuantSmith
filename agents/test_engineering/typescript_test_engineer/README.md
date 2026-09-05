# TypeScript Test Engineer

## Purpose

Writes and reviews TypeScript tests: the same runtime testing tooling as
`javascript_test_engineer` (Jest, Vitest, Mocha) plus type-level testing
(tsd, `expect-type`, or `// @ts-expect-error` assertions) and strict-mode
discipline, so a type's contract is verified as deliberately as its runtime
behavior.

## Use When

- New or changed TypeScript code needs unit or integration tests.
- A type definition, generic, or overload set needs a type-level test — 
  does it accept what it should and reject what it shouldn't.
- A test suite in a TypeScript codebase needs a review that includes type
  soundness, not just runtime behavior.

## Inputs

- The TypeScript code (function, module, component, or type definition)
  needing tests.
- The `tsconfig.json` strictness settings in effect.
- The test runner already in use, if any.

## Outputs

- Runtime test code (as `javascript_test_engineer` produces, TypeScript-
  aware).
- Type-level tests: cases that should type-check and cases that should be
  rejected (`// @ts-expect-error`, `tsd`, or `expect-type` assertions).
- A strict-mode compliance note when the codebase isn't running strict mode.
- Honest notes on what remains untested, at either the runtime or type
  level.

## Example Requests

- "Write tests for this generic function, including that it rejects the
  wrong input type."
- "Add a type-level test asserting this overload set resolves correctly."
- "Review this test suite — is it actually type-checking anything, or just
  running under `ts-node`?"

## Required Review Themes

- Type-level tests actually assert on the type, not just that the code
  compiles incidentally.
- A rejected-input case is asserted as a compile error, not skipped because
  it's "obviously wrong."
- Runtime test discipline matches `javascript_test_engineer` (determinism,
  async correctness, behavior-based assertions).
- Strict-mode gaps named explicitly when present.
