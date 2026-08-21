# Plan: Role Operations Agents (Phase 2)

- **Spec:** 0029-role-operations-agents-phase2 (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Add three agents to the existing `agents/role_operations/` group, reusing
its established configuration mechanism (`role_context.yml`, spec `0024`)
and guardrail set (no fabrication, data-provenance disclosure, spec `0025`)
without modifying either — Phase 2 is additive, not a redesign.

## Architecture & Components

```text
agents/role_operations/
  demo_narrative_packager/   -- prototype results -> narrative + one-pager
       reads: role_context.yml (audience/tone), instructions/data_provenance.md
  tough_question_rehearsal/  -- demo material -> persona Q&A prep sheet
       reads: role_context.yml (stakeholder personas)
       consumes: demo_narrative_packager's output (typical sequence)
  experiment_ledger/         -- every prototype variant -> append-only log
       feeds alongside: rapid_scaffolder (0024)
```

## Interfaces & Data Contracts

No new schema. `demo_narrative_packager` and `tough_question_rehearsal`
read the same `role_context.yml` fields Phase 1 already declared
(`communication`, `stakeholders.personas`); `experiment_ledger`'s entry
shape (config/result/status/timestamp) is defined in its own
`instructions.md` Output Contract, not a shared template in this slice.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P10 Honest reporting | yes | All three agents' core job is refusing to launder a gap (an unanswerable question, a missing result, a rejected variant) into something that looks complete. |
| P9 Security & data | yes | Same `role_context.yml`/no-tracked-real-data rules as Phase 1, unchanged. |
| P4 Correct by construction | yes | `experiment_ledger`'s append-only, no-curation rule prevents survivorship bias from ever entering the record, rather than relying on a later audit to catch it. |
| P5 Reversibility | yes | Docs/contracts-only change, isolated on a branch. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Three agent directories, four-file contract each | T-001 |
| REQ-002 | `demo_narrative_packager/instructions.md` | T-001 |
| REQ-003 | `tough_question_rehearsal/instructions.md` | T-001 |
| REQ-004 | `experiment_ledger/instructions.md` | T-001 |
| REQ-005 | `agents/role_operations/README.md`, `agents/README.md`, `specs/README.md` | T-002 |
| NFR-001 | Four-file contract + `Spec-Driven Role` per agent | T-001 |
| NFR-002 | Validation gates | T-003 |
| NFR-003 | "Never invent" as an explicit operating rule per agent | T-001 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope this slice | 3 agents (Phase 2 only) | Ship Phase 2 and 3 together | Phase 3 touches governance-facing artifacts (model cards, audit trails); the original roadmap's sequencing — build trust on lower-stakes work first — still applies, and Phase 1 alone doesn't yet constitute enough of a track record to skip ahead. |
| `role_context.yml` schema | Unchanged | Extend it now for anticipated Phase 3 fields | Extending a schema for fields no current agent reads yet is speculative; Phase 3's actual field needs will be clearer once its agents are designed. |
| Sequencing agent | None added | Add an orchestrator agent to sequence narrative → rehearsal | Two agents with a documented typical order (stated in the group README's "Where They Fit") is enough; a coordinating agent for two steps is unneeded process. |

## Validation Strategy

Run `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index`,
then `git diff --check`. AC-001 through AC-005 are covered by direct
inspection of each agent's `instructions.md` and the three catalog files.
AC-006 is covered by the gate run itself.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; no existing agent or gate changes behavior.

## Open Questions

- Does `role_context.yml`'s schema need to grow once Phase 3's
  governance-evidence shape is designed (carried from `0024`)?
