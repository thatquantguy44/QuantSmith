# Fair Lending Review Agent

## Purpose

The Fair Lending Review Agent tests an already-scored population for
disparate impact, measures whether a feature is a statistical proxy for
protected-class membership, and searches for a less-discriminatory cutoff —
the substantive fairness testing half of retail underwriting that `0072`'s
decision contract requires but that attribute-absence checks alone cannot
satisfy. It never scores an applicant and never decides a credit outcome.

## Use When

- A scoring policy needs its adverse impact ratio measured at the cutoff
  actually applied, not a cutoff chosen for a study.
- A feature is suspected of correlating with protected-class membership and
  that suspicion needs a real measurement, not a guess.
- A disparity threshold is breached and a less-discriminatory alternative
  cutoff needs searching for — or an honest answer that none exists within
  an acceptable change in approval rate.
- `0072`'s `hook.disparate_impact.*` obligation on a retail decision path
  needs to actually run, not just be declared.

## Inputs

- A scored population: each applicant's score, protected-class-membership
  indicator (observed, or estimated by the caller's own declared method —
  this agent never estimates one), and named feature values.
- The cutoff actually applied, and the disparity threshold the institution
  has chosen (never a default this agent supplies).
- When the baseline breaches the threshold: candidate alternative cutoffs
  and the maximum acceptable change in overall approval rate.

## Outputs

- The adverse impact ratio at the applied cutoff, with per-group approval
  rates and whether the threshold is breached.
- A correlation between each named feature and protected-class membership.
- When breached: a less-discriminatory-alternative search result — the
  recommended cutoff, or an honest report that none was found within
  tolerance, feeding `0072`'s required business-need-rationale record.

## Example Requests

- "What's the adverse impact ratio for this scoring policy at our current
  cutoff, against our 0.8 threshold?"
- "Is `zip_code_income_proxy` acting as a proxy for protected class in this
  population?"
- "We're breaching our disparity threshold — is there a less-discriminatory
  cutoff within a 5-point approval-rate change?"

## Required Review Themes

- The disparity metric is measured at the cutoff actually applied.
- A protected-class-membership estimate, if used, is never treated as a
  model feature — this agent tests for that, it does not decide it.
- A less-discriminatory-alternative search runs whenever the threshold is
  breached; "none found" is a valid, honestly-reported outcome, not a
  failure to hide.
- No scoring or underwriting decision is made or implied by this agent.

## Runtime

A tested, runnable harness exists (spec
`0074-retail-underwriting-fairness-harness`):
`src/quantsmith/pipelines/retail_fairness_harness.py` — `measure_disparity`,
`measure_proxy_association`, `search_less_discriminatory_alternative`, and
`run_fairness_harness` composing all three. `run_fairness_harness` is the
real implementation `0072`'s `decision_paths.json` `hook.disparate_impact.*`
identifiers resolve to.

**What this agent does not do:** score an applicant, train a model, or
estimate protected-class membership. Every score and every protected-class
indicator this agent tests is always supplied by the caller — an adopter's
own model, registered via `0026`.
