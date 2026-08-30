# Institutional Memory Instructions

## Operating Rules

- Store knowledge as a durable, versioned artifact, not as conversational recall.
- Capture provenance: who decided or learned it, when, why, and on what evidence.
- Classify honestly: decision, lesson, definition, or FAQ — do not overstate as fact.
- Link each artifact to related knowledge and to its canonical source.
- Feed captured knowledge back into ingestion/curation so it is searchable.
- On supersedence, mark the old artifact superseded and keep its history.
- Preserve access level and confidentiality of the captured content.

## Checks

- Is the artifact durable, versioned, and stored where it can be found?
- Is provenance (who/when/why/evidence) captured?
- Is its type (decision/lesson/definition/FAQ) and scope stated honestly?
- Is it linked to related knowledge and fed back into the base?
- Is supersedence handled with history preserved?
- Is access level preserved?

## Output Contract

Use clear Markdown. Include a `Provenance` section (who/when/why/evidence) and a
`Links & Supersedence` section. Choose the artifact type explicitly and keep scope
claims honest.

## Spec-Driven Role

Decisions captured here often originate as spec choices: a decision record can cite
the `REQ-*`/`RISK-*` it resolved, and a superseding decision amends the spec first
(constitution P1). Durable-artifact discipline is the SDK's "artifacts over memory"
principle; honest scope is P10. Reuse `templates/spec/` and
`templates/docs/incident_postmortem.md` where the artifact fits them. See
`instructions/knowledge_base.md` for the shared standard. This group also serves the persistent workflow memory store (`memory/`); see `instructions/workflow_memory.md`. Use the `workflow_memory.py` runtime (spec `0048`/`0049`) for durable records: `decision` type records are bounded by `first_seen` in point-in-time queries; mark a superseded decision with `status: superseded` and `superseded_by: <new-id>` rather than overwriting it.
