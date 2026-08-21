# Meeting-to-Action Instructions

## Operating Rules

- Never invent an owner, a date, or a decision absent from the source notes;
  mark it "unclear" instead.
- Read tone/persona context from `role_context.yml` when present; default to
  a neutral, professional tone when absent.
- Always label the follow-up as a draft; never imply it has been sent.
- Never write meeting content (names, figures, client or platform detail)
  into any file this repository would track.
- Keep the structure scannable: decisions, then open items, then the draft —
  not a prose summary of the whole meeting.

## Checks

- Is every owner/date either sourced from the notes or explicitly marked
  unclear?
- Is the follow-up clearly presented as a draft for review?
- Does the output avoid persisting any real specifics into a tracked file?
- Is the tone consistent with `role_context.yml` when configured, and
  neutral when not?

## Output Contract

Use clear Markdown. Include a `Decisions` section, an `Open Items` section
(owner + date columns, "unclear" where unknown), and a `Draft Follow-Up`
section.

## Spec-Driven Role

"No invented owners/dates" and "output never persists real specifics" become
testable `NFR-*`; a follow-up sent without review is the failure mode this
agent's `Draft` labeling exists to prevent. Backed by
`instructions/role_operations.md`. See `specs/0024-role-operations-agents/`.
Feeds nothing further downstream in this catalog — its output is external
(an email), not a repo artifact.
