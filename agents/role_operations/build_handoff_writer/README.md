# Build Handoff Writer Agent

## Purpose

The Build Handoff Writer Agent turns a project's actual current state into
a draft `templates/docs/handoff_memo.md` — goal, current state, key
decisions, validation status, known risks, next actions — so a handoff
never depends on the next owner reconstructing context from scattered
notes and memory.

## Use When

- Ownership of a project, model, or artifact is changing (a new owner, a
  reviewer taking over, a role transition).
- Work is pausing for a stretch and needs a written state to resume from
  later, even if the same person resumes it.
- A stage gate (e.g. handing a prototype to `implementation`, or a
  strategy to production) needs a written record of what's done and what
  isn't.

## Inputs

- The project or artifact's goal and current state.
- Key decisions made, with rationale — pulled from `audit_trail_keeper`'s
  decision log where one exists.
- What's been validated, what's failed, what hasn't been run yet.
- Known risks and limitations.
- Open questions and next actions, with owners where known.

## Outputs

- A populated draft of `templates/docs/handoff_memo.md`, using its exact
  section structure.
- Every unresolved item stated explicitly — never omitted to make the
  handoff look more finished than it is.
- A `Reviewer Notes` section flagging what the next owner should look at
  first.

## Example Requests

- "Write a handoff memo for this project — I'm passing it to someone
  else."
- "Draft a handoff before I step away from this for a few weeks."
- "This prototype is moving to implementation — write the handoff."

## Required Review Themes

- Current state and validation status are stated accurately, not
  optimistically.
- Every unresolved item and known risk appears — nothing convenient is
  left out.
- Key decisions cite their rationale, reusing `audit_trail_keeper`'s log
  where available rather than re-deriving it.
- Next actions have an owner and priority where known, and are marked
  unassigned where not.
