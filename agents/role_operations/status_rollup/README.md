# Status Roll-Up Agent

## Purpose

The Status Roll-Up Agent turns a period's actual activity — commits,
notebooks touched, meeting notes, decisions logged — into a draft status
update, so the recurring reporting cadence stops costing an end-of-week
rebuild from memory.

## Use When

- A weekly, biweekly, or sprint status update is due.
- Activity is scattered across commits, notebooks, and notes and needs
  synthesizing into a coherent narrative.
- A stakeholder or manager needs a "what happened, what's next, what's
  blocked" summary.

## Inputs

- A description or log of the period's activity (commits, notebook changes,
  meeting decisions, experiment results).
- Optionally, `role_context.yml` for the audience and cadence.

## Outputs

- A draft status update: what happened, what's next, what's blocked —
  grounded only in the activity actually supplied.
- Gaps flagged rather than papered over (e.g., "no update available on X").

## Example Requests

- "Roll up this week's commits and notes into a status update."
- "Draft my biweekly update from these experiment results and meeting
  decisions."

## Required Review Themes

- No claimed progress, result, or milestone not supported by the supplied
  activity.
- Blocked or stalled items are stated plainly, not softened into "in
  progress."
- The output is a draft for review, not a submitted report.
