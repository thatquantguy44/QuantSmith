# Test Engineering

Shared standard for `agents/test_engineering/*`. It covers how to write and
run tests and fuzz harnesses well, in any language; it does not cover
whether an acceptance criterion is actually met (`testing_validation`'s job)
or whether a pipeline stage may release (`quality-guard-agent`'s job).

## Determinism And Flakiness

- A test that passes or fails depending on run order, wall-clock time, network
  availability, or unseeded randomness is not evidence of anything. Seed every
  random generator, freeze or inject time, and isolate network/filesystem
  effects behind a fake or fixture.
- A flaky test is a known defect, not a fact of life. Name it as a defect —
  in the test itself or in the handoff to `testing_validation` — rather than
  retrying until it's green.
- Mirrors `instructions/reproducibility.md`'s standard: seeded randomness,
  pinned inputs, no hidden state.

## Meaningful Assertions Over Coverage-Chasing

- A line-coverage number is not evidence a behavior is correct — it is
  evidence a line executed. Assert on the actual behavior/contract (return
  value, state change, thrown error, emitted event), not merely that a
  function ran without raising.
- A test that exercises code but asserts nothing beyond "it didn't crash" is
  worse than no test: it inflates a coverage number while adding no
  regression protection. Flag these rather than writing them to hit a
  target.
- Mutation testing (`mutmut`/`cosmic-ray` for Python, comparable tools for
  other languages) is a stronger signal than line coverage when it's
  available: a suite that doesn't catch an injected mutant isn't actually
  testing that mutant's behavior. Suggest it as a periodic check, not a
  per-PR gate, unless the requester already runs one.

## Test Structure

- Unit tests isolate one unit's contract; integration tests cross a real
  boundary (a database, a filesystem, another service) deliberately, not by
  accident of a unit test reaching further than intended.
- Mock or fake at a boundary the test owns crossing intentionally; mocking
  the thing actually under test hides the behavior the test exists to catch.
- A test's name states what it verifies, not just what it calls — a future
  failure should be diagnosable from the test name and assertion message
  alone.

## Fuzzing (`cpp_test_fuzz_engineer` And Any Fuzz-Capable Language)

- Fuzzing targets only code the requester owns or is explicitly authorized to
  test, run in a local or sandboxed environment — never a production system,
  never a third party's service, never anything resembling a denial-of-service
  or unauthorized-access attempt. This mirrors this environment's own
  dual-use security-tooling policy: fuzzing and other dual-use testing tools
  are for authorized, defensive use.
- A fuzz harness targets one parsing/deserialization/boundary function at a
  time with a minimal, realistic input corpus — not the whole binary at once.
- Sanitizers (ASan/UBSan/MSan/TSan) catch categories a fuzzer's crash alone
  won't always surface (use-after-free, undefined behavior, uninitialized
  reads, data races); build fuzz targets with them enabled by default.
- A crash is triaged before it's reported: minimize the input, identify the
  faulting function and defect class, and only then hand it off — an
  unminimized crash dump is not useful evidence.

## Honest Reporting

- Never state a test passed, a fuzz run found nothing, or coverage reached a
  stated number without that result actually being produced by a real run.
  An unavailable result is a stated gap, not a filled-in assumption — the
  same real-data-first standard `instructions/data_provenance.md` applies to
  data values, applied here to test evidence.
- Report what remains untested or unfuzzed alongside what was covered; an
  honest "not yet covered" is more useful than an implied "everything's
  fine."

## Scope Boundary

- `test_engineering/*` writes and reviews test/fuzz code and explains how to
  run it. It does not decide whether an acceptance criterion is met — that
  traceability call, and quant-specific validation (leakage, look-ahead,
  significance), stays `testing_validation`'s job.
- `test_engineering/*` does not approve or reject a pipeline stage for
  release — that gate, including schema/contract/PII/naming policy, stays
  `quality-guard-agent`'s job.
- Hand off to one or both once tests/fuzz harnesses exist and run; don't
  substitute a test-engineering opinion for either's decision.

## Spec-Driven Role

Determinism and honest-reporting requirements trace to constitution P10
(honest reporting); fabricated test/fuzz/coverage evidence is a `RISK-*`
this group exists to prevent (`RISK-003`,
`specs/0062-test-engineering-agents/`). The fuzzing authorized-target
boundary traces to `RISK-002` in the same spec and to this environment's
dual-use security-tooling policy.
