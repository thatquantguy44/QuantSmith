# Tough-Question Rehearsal Instructions

## Operating Rules

- Ask genuinely skeptical, persona-appropriate questions, not generic
  filler each persona would never actually raise.
- Ground every suggested answer in the supplied material; flag a question
  the material can't answer instead of inventing a plausible response.
- Use `role_context.yml`'s stakeholder personas when configured; default
  to risk reviewer / technical partner / client sponsor otherwise.
- Keep the output usable as an actual prep sheet — concise and scannable,
  not a long transcript.
- Never write real platform, client, or personal detail into any file this
  repository would track.

## Checks

- Are questions genuinely persona-appropriate and skeptical, not generic?
- Is every suggested answer grounded in the material, with unanswerable
  questions flagged rather than invented answers?
- Does persona coverage match `role_context.yml` when configured?
- Is the output concise enough to actually use as prep?

## Output Contract

Use clear Markdown. Group by persona, each with a `Question` and
`Suggested Answer` (or `Not yet answerable — <what's missing>`).

## Spec-Driven Role

"No invented answers" and "unanswerable questions flagged" trace to
constitution P10 (honest reporting) and become testable `NFR-*`. Backed by
`instructions/role_operations.md`. See
`specs/0029-role-operations-agents-phase2/`. Output is external (a prep
sheet), not a repo artifact.
