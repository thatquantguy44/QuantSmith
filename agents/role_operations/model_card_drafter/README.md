# Model Card Drafter Agent

## Purpose

The Model Card Drafter Agent turns what's already known about a model —
purpose, data, methodology, validation results, limitations — into a draft
`templates/docs/model_card.md`, so the card exists as a living draft from
early on instead of being reconstructed from memory right before a review.

## Use When

- A model is far enough along to draft its first model card.
- A model card needs refreshing after a material change (new data,
  features, methodology, or validation results).
- A reviewer or governance process requires a model card before promotion,
  and it doesn't exist yet or is stale.

## Inputs

- Model description, purpose, and the decision it supports.
- Training/validation/test data description, date windows, point-in-time
  assumptions.
- Methodology, configuration, baseline, benchmark.
- Validation results, robustness and sensitivity findings.
- Known limitations and risks.
- Monitoring plan and reproducibility details, where available.

## Outputs

- A populated draft of `templates/docs/model_card.md`, using its exact
  section structure.
- An explicit gap marker on every section the input didn't cover — never a
  fabricated value or a silently blank field.
- A short "what's still needed" summary listing every gap found.

## Example Requests

- "Draft a model card for this signal from what I've told you."
- "Update the model card with the new validation results."
- "What's missing from this model card before it's ready for review?"

## Required Review Themes

- Every populated field traces to something actually supplied.
- Every uncovered section is marked as a gap, not fabricated or left
  ambiguously blank.
- Limitations and risks sections are substantive, reflecting what was
  actually stated — not boilerplate.
- Point-in-time assumptions are stated plainly, not defaulted or assumed.
