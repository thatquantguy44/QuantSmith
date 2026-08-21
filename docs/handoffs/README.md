# Handoffs

This directory holds handoff documents — durable records that let the next person
pick up work without reconstructing context. Unlike `docs/handoff.md` (the current
snapshot of the whole SDK), files here track **specific streams of work**, most
importantly the queue of features to build next.

## Contents

- `future_features.md` — the running backlog of features to build. Add new ideas
  here as they arise; promote one to a full `specs/NNNN-slug/` when work starts.
  and meme draft workflow.

## How To Use

1. When a new feature is proposed, add a row to `future_features.md` with a short,
   spec-ready description, its rough priority, and status `proposed`.
2. When work begins, create `specs/NNNN-slug/` from `templates/spec/`, assign IDs,
   and set the row's status to `in-progress` with a link to the spec. Workflow
   packs that are intentionally root-level may keep their specs under
   `<workflow_pack>/specs/`.
3. When it ships, set the status to `done` (or remove the row) and note the spec.

Keep entries short — the detail belongs in the spec, not here.
