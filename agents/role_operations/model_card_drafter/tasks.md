# Model Card Drafter Tasks

## Draft A New Model Card

Input: everything currently known about a model — purpose, data,
methodology, validation results, limitations, monitoring plan.

Output: a populated `templates/docs/model_card.md` draft, with every
uncovered section marked as a gap.

## Update An Existing Card

Input: a model card draft plus new information (new validation results, a
data change, a methodology change).

Output: the updated sections, with anything genuinely new flagged as
changed and anything still missing left marked as a gap.

## Identify Gaps

Input: a model card draft.

Output: the "Open Questions / Gaps" summary — every section still marked
as a gap and what's needed to close it, so a reviewer knows exactly what's
left before the card is ready.
