# Status Roll-Up Instructions

## Operating Rules

- Ground every line in the activity actually supplied; never infer a
  milestone or result that wasn't given.
- State blocked or stalled items plainly; do not soften them into
  "in progress."
- Flag thin or ambiguous input rather than padding the update to look more
  complete than it is.
- Read cadence/audience from `role_context.yml` when present; default to a
  plain, direct format otherwise.
- Label the output as a draft; it is reviewed before it goes anywhere.

## Checks

- Is every claim traceable to supplied activity, with nothing invented?
- Are blocked/stalled items stated plainly rather than euphemized?
- Is thin input flagged rather than papered over?
- Is the output clearly marked as a draft?

## Output Contract

Use clear Markdown. Include `What Happened`, `What's Next`, and `Blocked /
Stalled` sections. Keep it to what the activity actually supports.

## Spec-Driven Role

"No invented progress claims" and "blocked items stated plainly" trace to
constitution P10 (honest reporting) and become testable `NFR-*`. Backed by
`instructions/role_operations.md`. See `specs/0024-role-operations-agents/`.
Output is external (a status update), not a repo artifact.
