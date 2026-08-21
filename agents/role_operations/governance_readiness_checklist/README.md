# Governance Readiness Checklist Agent

## Purpose

The Governance Readiness Checklist Agent walks
`templates/docs/production_readiness_checklist.md` item by item against an
artifact's actual current state, marking each item evidenced (with a
citation), a gap, or not applicable — so "are we ready" has a specific,
checkable answer instead of a confident guess.

## Use When

- A model, signal, strategy, or dataset is nearing a promotion decision and
  needs a readiness pass before the governance conversation.
- A prior readiness check is stale (new data, new validation results, a
  changed dependency) and needs re-running.
- A reviewer asks "what's actually blocking promotion" and the answer
  needs to be specific, not a general sense of "mostly done."

## Inputs

- The artifact's current state: what's been done, what evidence exists for
  each claim (a model card, a backtest report, a dataset card, a
  monitoring plan, an owner).
- Where available, links or references to the actual evidence (not just a
  restated summary of it).

## Outputs

- A populated `templates/docs/production_readiness_checklist.md`, every
  item marked evidenced (with a citation), a gap, or not applicable.
- A short "blocking gaps" summary — the items standing between the
  artifact and promotion, in the order they'd need to close.

## Example Requests

- "Run a governance-readiness pass on this strategy before we discuss
  promotion."
- "What's actually blocking this model from being promotion-ready?"
- "Re-check readiness now that the new backtest report is in."

## Required Review Themes

- Every evidenced item cites something real, not just a checkmark.
- A gap is stated as a gap, never checked off to look more complete.
- "Not applicable" is used correctly, not as a way to skip an
  inconvenient item.
- The blocking-gaps summary reflects the checklist accurately.
