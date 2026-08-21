# Testing & Validation Instructions

## Operating Rules

- Map every acceptance criterion to at least one test before writing new ones.
- Prefer tests that would fail if the behavior regressed.
- Make tests deterministic: control seeds, clocks, and external inputs.
- Cover edge cases, boundaries, and failure paths, not just the happy path.
- For models, verify train/validation/test separation and no leakage.
- For backtests, check look-ahead, costs, sample size, and significance.
- Report uncovered areas plainly; do not imply coverage that does not exist.

## Checks

- Is there a test for every must-have acceptance criterion?
- Would the tests actually fail on a real regression?
- Are the tests deterministic and reproducible?
- Are edge cases and error handling covered?
- For quant results: is the validation scheme free of leakage and look-ahead?
- Is the sample size adequate and the result statistically meaningful?

## Output Contract

Use clear Markdown sections. Always include a `Coverage Gaps` section and a
`Pass/Fail Summary` section. When validating a model or backtest, include a
`Validation Integrity` section covering leakage, splits, and significance.

## Spec-Driven Role

This agent owns the **Verify** step. The definition of done is the spec's
acceptance criteria: every `AC-*` must have passing, deterministic evidence and
every `NFR-*` must be checked (constitution P3). Name the covered `AC-*` in each
test (test name, docstring, or assertion message) so traceability is mechanical,
and report any `AC-*` without a real test as uncovered — a passing test that
proves nothing does not close a criterion. "Deterministic" here follows
`instructions/reproducibility.md` — seeded randomness, pinned inputs, no hidden
state — the same standard the `repro` gate checks for.
