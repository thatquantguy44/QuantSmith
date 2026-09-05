# TypeScript Test Engineer Tasks

## Write Runtime Tests For A Function Or Module

Input: TypeScript code needing test coverage.

Output: runtime tests (Jest/Vitest/Mocha) grounded in actual behavior, plus
named remaining gaps.

## Write A Type-Level Test

Input: a generic function, overload set, or type definition.

Output: an accept-case and a reject-case (`// @ts-expect-error`/`tsd`/
`expect-type`), with the assumed `tsconfig.json` strictness stated.

## Review An Existing Suite For Type Soundness

Input: an existing TypeScript test file or directory.

Output: findings on missing reject-case coverage, strictness gaps, and any
runtime-discipline issues (flakiness, un-awaited async), each tied to a
specific test.
