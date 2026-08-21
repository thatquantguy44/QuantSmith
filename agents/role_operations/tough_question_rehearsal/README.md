# Tough-Question Rehearsal Agent

## Purpose

The Tough-Question Rehearsal Agent gives demo material a fast, honest
stress test: it drafts the questions a skeptical risk reviewer, a
technical partner, and a client sponsor would each ask, with a suggested
answer for every one — so the night before a client or committee meeting
is spent rehearsing, not guessing what will get asked.

## Use When

- A demo or proposal is scheduled and the presenter wants a prep sheet.
- A finding seems too clean and needs the skeptical questions surfaced
  before someone else asks them.
- Different stakeholder personas (risk, technical, client) are expected in
  the room and need distinct question sets.

## Inputs

- The demo material (narrative, one-pager, results) to rehearse against.
- Optionally, `role_context.yml` for the actual stakeholder personas
  expected.

## Outputs

- Questions grouped by persona (risk reviewer, technical partner, client
  sponsor, or whatever `role_context.yml` names), each with a suggested
  answer.
- Questions the material cannot yet answer, flagged explicitly rather than
  given a plausible-sounding invented answer.
- A prep sheet, not a transcript — concise, scannable before a meeting.

## Example Requests

- "Rehearse tough questions for tomorrow's client demo."
- "What would a risk reviewer push back on in this proposal?"

## Required Review Themes

- Questions are realistic and persona-appropriate, not generic filler.
- Suggested answers are grounded in the supplied material; a question the
  material can't answer is flagged, not answered with an invented claim.
- Persona coverage matches `role_context.yml`'s stakeholder personas when
  configured.
