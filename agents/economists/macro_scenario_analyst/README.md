# Macro Scenario Analyst Agent

## Purpose

The Macro Scenario Analyst Agent builds forward macro stress scenarios
(hard landing, stagflation, geopolitical shock, and similar) with
quantified indicator paths — not just a narrative — so `risk` and
`backtest_review` have something concrete to stress-test against.

## Use When

- A strategy or portfolio needs stressing against a forward macro
  scenario, not just its own backtest sample.
- `instructions/risk_management.md`'s stress-testing requirement needs a
  concrete scenario to test against.
- A workflow needs to reason about "what if the regime breaks" rather
  than only the current, classified regime.

## Inputs

- The current regime classification, for a baseline to deviate from.
- The scenario category in scope (recession, stagflation, geopolitical
  shock, policy error, or a user-specified one).
- Any known historical analog to ground the scenario in, when relevant.

## Outputs

- A named scenario with a quantified indicator path: which indicators
  move, in what direction, and roughly how much — not only a prose
  description.
- The economic logic connecting the scenario's trigger to its indicator
  path.
- A rough plausibility/likelihood characterization, stated as a judgment,
  not a precise probability the input doesn't support.
- A named handoff to `risk` (for stress testing) or `backtest_review` (for
  scenario-based robustness testing).

## Example Requests

- "Build a stagflation scenario with a quantified indicator path for
  stress testing."
- "What would a hard-landing scenario look like from the current regime?"
- "Characterize a geopolitical-shock scenario's macro transmission."

## Required Review Themes

- Every scenario has a quantified indicator path, not just a narrative.
- The trigger-to-indicator-path logic is stated explicitly.
- Likelihood is a stated judgment, never a fabricated precise probability.
- The scenario is clearly framed as forward-looking and hypothetical, not
  a prediction presented as fact.
