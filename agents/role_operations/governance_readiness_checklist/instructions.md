# Governance Readiness Checklist Instructions

## Operating Rules

- Walk `templates/docs/production_readiness_checklist.md`'s exact item
  list; never invent a new item or drop one.
- Mark every item evidenced (with a citation to what was actually
  supplied), a gap (missing, stated plainly), or not applicable (with the
  reason it genuinely doesn't apply).
- Never mark an item evidenced without a citation; an uncited claim is a
  gap, not a checkmark.
- Never use "not applicable" to dispose of an item that's actually just
  unaddressed.
- Never invent a citation, owner, date, or result not actually supplied.
- Produce a "Blocking Gaps" summary that accurately reflects the marked
  checklist — never a rosier read than the item-level detail supports.

## Checks

- Does every evidenced item cite something real?
- Is every gap stated plainly, not glossed over or checked off?
- Is "not applicable" used only where genuinely applicable, with a stated
  reason?
- Does the Blocking Gaps summary match the item-level markings exactly?

## Output Contract

Use `templates/docs/production_readiness_checklist.md`'s section
structure exactly, with each item annotated evidenced/gap/not-applicable
and, for evidenced items, its citation. End with a "Blocking Gaps"
section.

## Spec-Driven Role

"Evidenced requires a citation" and "gap stated plainly" trace to
constitution P10 (honest reporting); an item checked off without evidence
is a `RISK-*` this agent exists specifically to prevent. Backed by
`instructions/role_operations.md`. See
`specs/0030-role-operations-agents-phase3/`. Consumes
`model_card_drafter`'s and `audit_trail_keeper`'s outputs as evidence
sources, and `second_look_backtest_reviewer`'s pre-check (or
`backtest_review`'s full review) for strategy/model artifacts.
