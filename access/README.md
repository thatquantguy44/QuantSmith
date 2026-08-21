# Viewer Access Control

Per-person read visibility over `memory/` and `research/`, driven by one
committed file: `access/roster.yml`. Design is `specs/0058-viewer-access-
control/`; enforcement code is `src/quantsmith/pipelines/access_control.py`.

## How it works

Every memory record and research item carries an `access_level`: `public`,
`internal`, or `restricted` (ordered — a viewer at a given clearance sees
that level and everything below it). `access/roster.yml` maps a pseudonymous
viewer handle to a clearance. Both the Knowledge Console CLI (`python -m
quantsmith.knowledge_console print|research|query`) and
`workflow_memory.query()` apply it at read time.

**Opt-in.** `roster.yml` ships with zero entries, which means enforcement is
inactive and every viewer sees everything — identical to the behavior before
this spec existed. Enforcement turns on the moment the roster names its
first person, and it then applies to *everyone*, not only the people listed:
anyone unlisted falls back to `default_clearance`.

**Fail closed on ambiguity.** An item with an unrecognized `access_level`,
or a viewer with an unrecognized clearance, is always resolved toward *less*
visibility, never more.

## Setting it up

1. Find your own handle:

   ```sh
   python -m quantsmith.pipelines.workflow_memory_cli whoami
   ```

   It's the same handle spec 0049 already attributes your written records
   to — derived from your local identity (env override, `identity.yml`, git
   config, or OS user) hashed with a repo-wide salt, never reversible back to
   who you are from the roster file alone.

2. Add yourself and your teammates to `access/roster.yml`:

   ```yaml
   default_clearance: public

   people:
     - handle: u-xxxxxxxxxxxxxxxxxxxxxxxx
       label: "descriptive-role-not-a-real-name"
       clearance: internal
   ```

3. Before merging a roster change, preview its effect without becoming that
   viewer:

   ```sh
   python -m quantsmith.knowledge_console preview-access --viewer-override <handle-or-level>
   ```

   `<handle-or-level>` is either a roster handle or a bare clearance level
   (`public`/`internal`/`restricted`).

## What this is not

Not authentication. There is no login, no session, no proof that the person
running the process is who the resolved handle claims — this is a
convention for a local-per-person deployment among a trusted team, the same
trust model spec 0049's write-side attribution already relies on. A
shared/multi-tenant deployment with real auth is a separate, larger piece of
work (see `specs/0058-viewer-access-control/spec.md`'s Non-Goals).

## Rules

- **Pseudonymous handles only.** Never put a raw name, email, or username in
  `roster.yml` — the same rule spec 0048/0049 already enforce for record
  `author` fields. The `access-check` gate scans for this.
- **No silent widening.** Every unrecognized or malformed value in this file
  resolves toward less access, never more (fail-closed).
- **Reversible.** Deleting `roster.yml`, or emptying its `people:` list,
  fully disables enforcement with no code change.
