# Macro Regime Classifier Agent

## Purpose

The Macro Regime Classifier Agent synthesizes indicator reads and policy
reads into a classified economic regime — a growth/inflation quadrant,
business-cycle phase, or tightening/easing label — with the confidence and
evidence behind it.

**This is an analytical classification, not live model monitoring.** It
answers "what is the current economic regime," a periodic judgment call.
`agents/monitoring/model_signal_monitoring/` answers a different question
— "has a live model's behavior diverged from its training regime" — a
continuous operational check. The two inform each other; neither replaces
the other.

## Use When

- A regime label is needed as input to a strategy or allocation review
  (`macro_multi_asset`, `portfolio_management/allocation_policy`).
- Indicator and policy reads have accumulated and need synthesizing into
  one coherent regime read.
- A workflow needs to know whether the backdrop has shifted enough to
  reconsider positioning assumptions.

## Inputs

- Indicator reads from `macro_indicator_analyst` (or supplied directly).
- Policy reads from `monetary_policy_analyst` (or supplied directly).
- The prior regime classification, for a change assessment.

## Outputs

- A regime label (e.g. "reflationary growth," "late-cycle tightening,"
  "disinflationary slowdown") with the specific indicators and policy
  signals supporting it.
- A confidence/conviction level, stated explicitly — not implied by tone.
- What would change the classification (named conditions, not vague
  caveats).
- A named handoff to `macro_multi_asset` or
  `portfolio_management/allocation_policy`.

## Example Requests

- "Classify the current macro regime from this month's indicator and
  policy reads."
- "Has the regime shifted since the last classification?"
- "What would need to happen for this regime read to change?"

## Required Review Themes

- The regime label traces to specific supplied indicator/policy reads,
  never a hunch.
- Confidence is stated explicitly.
- Change-conditions are named, not left as a vague caveat.
- The output is clearly framed as an analytical classification, not a
  live monitoring alert.
