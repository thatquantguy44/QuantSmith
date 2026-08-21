# Plan: Role Operations Agents (Phase 1)

- **Spec:** 0024-role-operations-agents (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-09

## Approach

Add `agents/role_operations/` (group README + four agents) and the
configuration mechanism it depends on: a committed, placeholder-only
template, a documented local-file resolution order, and a gate that makes
"never commit real specifics" a checked property instead of a convention.
Follow the `templates/knowledge/knowledge_sources.yml` /
`hooks/stages/knowledge-check.sh` pattern already established in this repo,
adapted for the fact that (unlike knowledge-source pointers) a filled-in
`role_context.yml` is itself likely to hold sensitive detail, not just a
path to it — hence gitignoring it by default and adding a deterministic
tracked-file check.

## Architecture & Components

```text
templates/role_operations/role_context.yml   (committed, placeholders only)
  -- adopter copies to --> ./role_context.yml (repo root, gitignored, local)
       resolution: $QF_ROLE_CONTEXT -> ./role_context.yml -> none configured

agents/role_operations/
  meeting_to_action    -- notes/transcript -> decisions, owners, draft follow-up
  status_rollup        -- activity -> draft status update
  rapid_scaffolder     -- idea -> repo skeleton, data-contract stub, baseline plan
       -> hands off to research_analyst | implementation
  prior_art_scanner    -- hypothesis -> related approaches, open questions
       -> hands off to research_analyst

hooks/stages/role-context-check.sh
  1. deterministic: role_context.yml tracked/staged? -> warn/block
  2. informational: resolve and report the active context's shape (key count only)
  3. advisory heuristic: template hygiene (email/SSN-shaped pattern scan)
```

## Interfaces & Data Contracts

- `role_context.yml` schema (documented in the template's comments):
  `role`, `platform`, `data_sources`, `governance`, `stakeholders`,
  `communication` top-level keys, each holding placeholder/category-level
  values only in the committed template.
- Agent inputs/outputs are Markdown contracts and session-level text
  (meeting notes in, follow-up draft out) — no persisted schema beyond the
  config file itself.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P9 Security & data | yes | This spec exists specifically to operationalize P9 for a new, real-content-shaped config file: gitignored by default, plus a gate that checks git-tracking status deterministically rather than relying on convention alone. |
| P10 Honest reporting | yes | Every agent's operating rules forbid fabricating names, numbers, decisions, or citations; `status_rollup` and `meeting_to_action` explicitly require flagging unclear/blocked items rather than softening them. |
| P4 Correct by construction | yes | Agents degrade gracefully with no configuration (NFR by design) rather than failing or guessing when `role_context.yml` is absent. |
| P5 Reversibility | yes | Docs/contracts-only change, isolated on a branch. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `agents/role_operations/{meeting_to_action,status_rollup,rapid_scaffolder,prior_art_scanner}/` | T-001 |
| REQ-002 | `templates/role_operations/role_context.yml` + resolution order docs | T-002 |
| REQ-003 | `hooks/stages/role-context-check.sh` | T-003 |
| REQ-004 | `agents/README.md`, `specs/README.md`, root `README.md`, `.gitignore` | T-004 |
| NFR-001 | Four-file contract + `Spec-Driven Role` per agent | T-001 |
| NFR-002 | Validation gates | T-005 |
| NFR-003 | Placeholder-only template, gitignore, gate | T-002, T-003, T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope this slice | 4 agents (Phase 1) | All 14 roles from the underlying plan at once | Matches the plan's own advice ("resist building all fourteen before the first has earned its keep") and keeps the review surface proportionate to a not-yet-proven pattern. |
| Config safety mechanism | Gitignore by default + deterministic git-tracking gate check | Documentation-only convention ("please don't commit this") | A convention alone relies on nobody ever force-adding the file; a deterministic check is the same class of guarantee `secret-scan` gives for credentials, and costs one more `grep`-equivalent, not a new dependency. |
| Where `role_context.yml` lives | Repo root, git-root-relative, mirroring `knowledge_sources.yml` | A dedicated `local/` or `.local/` directory | Consistency with the existing, already-documented `knowledge_sources.yml` resolution pattern reduces the number of conventions an adopter has to learn. |
| PII detection | Narrow heuristic (email/SSN-shaped), explicitly advisory | A general-purpose PII/NER-style detector | No such detector is a repo dependency today, and a false sense of completeness is worse than an honestly narrow, documented heuristic — same posture as the `leakage` gate. |

## Validation Strategy

Run `hooks/stages/role-context-check.sh` directly in all three states (no
file, untracked local file, force-added file) to confirm AC-002/AC-003, then
`hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index
secret-scan role-context`, then `git diff --check` for whitespace. AC-001 and
AC-004 are covered by direct inspection of the template and each agent's
`instructions.md`. AC-005 is covered by the full gate run.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit. The `role-context` gate is additive (a new stage name in
`run-stage.sh`'s `ALL` list) and does not change any existing gate's
behavior.

## Open Questions

- Should Phase 2 (demo packaging, tough-question rehearsal, experiment
  ledger, build-handoff writer) follow immediately, or should this slice run
  for a while first to validate the configuration mechanism holds up in
  practice?
