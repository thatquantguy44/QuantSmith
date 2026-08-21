# Spec: Role Operations Agents (Phase 2)

- **ID:** 0029-role-operations-agents-phase2
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

Spec `0024` shipped Phase 1 of the role-operations roster — the lowest-risk,
highest-frequency slice (meeting follow-ups, status updates, prototype
scaffolding, first-pass research scans) — deliberately sequenced first so
trust in the pattern forms before any agent gets near a client or a
governance committee. It has now been used across a stretch of real work in
this session. This spec ships Phase 2: the "prototype accelerators" tier —
still nothing governance-facing, but closer to the moment a prototype
becomes something shown to someone else.

## Goals

- Add three agents to `agents/role_operations/`: `demo_narrative_packager`,
  `tough_question_rehearsal`, `experiment_ledger` — on the same four-file
  contract and configuration mechanism (`role_context.yml`) as Phase 1.
- Connect `demo_narrative_packager` explicitly to the data-provenance
  guardrail (spec `0025`): any synthetic/illustrative data in a demo
  visual is disclosed, never blended in silently.
- Connect `tough_question_rehearsal` to `role_context.yml`'s stakeholder
  personas, so its default three personas (risk reviewer, technical
  partner, client sponsor) are overridable by real configured ones.
- Connect `experiment_ledger` to `rapid_scaffolder`'s iteration loop —
  every variant tried during prototyping gets logged, not just the winner.
- Update `agents/role_operations/README.md`'s Phase tracking now that
  Phase 2 is shipped.

## Non-Goals

- No Phase 3 agents in this slice (`model_card_drafter`, `audit_trail_keeper`,
  `governance_readiness_checklist`, `second_look_backtest_reviewer`,
  `build_handoff_writer`, `alert_triage`) — still deliberately sequenced
  last, since they touch a governance-facing decision trail.
- No runtime code; agent contracts only, matching `0024`'s own pattern.
- No change to `role_context.yml`'s schema in this slice; Phase 2's agents
  use the same `stakeholders.personas`/`communication` fields Phase 1
  already declared. Whether the schema needs to grow for Phase 3's
  governance-evidence shape is an open question carried from `0024`.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide three Phase 2 role-operations agents (`demo_narrative_packager`, `tough_question_rehearsal`, `experiment_ledger`) on the four-file contract, each usable with no configuration and sharpened by optional local configuration. | must |
| REQ-002 | `demo_narrative_packager` shall ground every claim in supplied prototype results and explicitly disclose any synthetic/illustrative data in a visual, per `instructions/data_provenance.md`. | must |
| REQ-003 | `tough_question_rehearsal` shall draft persona-grouped questions with suggested answers, flagging a question the material cannot yet answer rather than inventing a plausible answer. | must |
| REQ-004 | `experiment_ledger` shall log every variant reported, including rejected ones, without survivorship-biased curation, and state rejection reasons plainly. | must |
| REQ-005 | `agents/role_operations/README.md`, `agents/README.md`, and `specs/README.md` shall reflect Phase 2 as shipped. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Agent contract consistency | Every new public agent has `README.md`, `prompt.md`, `instructions.md`, `tasks.md`, each with a `Spec-Driven Role` section. |
| NFR-002 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates all pass. |
| NFR-003 | No fabrication | Every agent's `instructions.md` states explicitly that a claim, answer, or result absent from the input is flagged, never invented. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given each of the three agents' `instructions.md`, when inspected, then each explicitly states it must work without configuration and never persists real specifics into a tracked file. | REQ-001, NFR-001 |
| AC-002 | Given `demo_narrative_packager/instructions.md`, when inspected, then it requires disclosing synthetic/illustrative data per `instructions/data_provenance.md`, not blending it in silently. | REQ-002 |
| AC-003 | Given `tough_question_rehearsal/instructions.md`, when inspected, then it requires flagging an unanswerable question rather than inventing an answer, and reading personas from `role_context.yml` when configured. | REQ-003 |
| AC-004 | Given `experiment_ledger/instructions.md`, when inspected, then it requires logging every reported variant (including rejected ones) with no survivorship curation, and stating rejection reasons plainly. | REQ-004 |
| AC-005 | Given `agents/role_operations/README.md`, `agents/README.md`, and `specs/README.md`, when inspected, then each lists all three Phase 2 agents and reflects Phase 2 as shipped. | REQ-005 |
| AC-006 | Given the full gate suite, when run, then `spec`, `agent-catalog`, `docs-link`, `spec-index` all pass. | NFR-002 |

## Data & Dependencies

No data dependencies. No runtime code, consistent with `0024`.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | `demo_narrative_packager` under time pressure before a real demo skips the synthetic-data disclosure step. | An undisclosed synthetic figure reaches a stakeholder as if it were real. | The disclosure requirement is a named operating rule and check, not an optional nicety; `instructions/data_provenance.md`'s existing gate/template infrastructure (spec `0025`) is already in place to catch a committed disclosure gap. |
| RISK-002 | `tough_question_rehearsal` produces generic, low-value questions that don't reflect real scrutiny. | The prep sheet gives false confidence instead of genuine rehearsal value. | Documented explicitly in the agent's prompt as an operating rule ("genuinely skeptical... not generic filler"); the check requires persona-appropriateness, not just question count. |
| RISK-003 | `experiment_ledger` becomes a chore abandoned mid-prototype, leaving a partial, misleading record. | A reviewer sees an incomplete search and mistakes it for the whole one. | Out of scope for this slice to enforce mechanically (no runtime); the agent's Purpose and Required Review Themes state completeness as the whole point, and a partial ledger is a known, named limitation rather than a silent one. |

## Assumptions & Open Questions

- Assumption: Phase 2 is safe to ship now that Phase 1 has been used across
  real work in this session, matching the original roadmap's trust-building
  sequencing.
- Assumption: `demo_narrative_packager` and `tough_question_rehearsal` are
  used together (narrative first, then rehearsal against it), so no
  additional "orchestrator" agent is needed to sequence them.
- Open question (carried from `0024`): does `role_context.yml`'s schema
  need to grow once Phase 3's governance-evidence shape is designed?

## Exceptions

None.
