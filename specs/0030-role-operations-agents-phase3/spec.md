# Spec: Role Operations Agents (Phase 3)

- **ID:** 0030-role-operations-agents-phase3
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

Specs `0024` (Phase 1) and `0029` (Phase 2) shipped the role-operations
roster's lower-stakes tiers — ambient toil, then prototype accelerators —
deliberately sequenced first so the pattern (configurable, no company data,
drafts not finals, no fabrication) earned trust before any agent got near a
governance-facing decision trail. That trust-building period has run its
course. This spec ships Phase 3, the last tier: model-card drafting,
audit-trail keeping, governance-readiness checking, a fast pre-check ahead
of full backtest review, build-handoff writing, and personal alert triage.
These six close out the original fourteen-agent roster.

Phase 3 differs from Phase 1/2 in one important way: three of its outputs
(model card, governance checklist, decision log) are drafts of artifacts a
governance process actually consumes, and two of its agents
(`second_look_backtest_reviewer`, `alert_triage`) sit next to existing
agents (`backtest_review`, `alerts/alert_router` +
`alerts/incident_notification`) that already own the real review/lifecycle
authority. Both risks get the same treatment as everything else in this
group: explicit "draft, not final" labeling, and explicit "defers to, does
not replace" framing for the two agents with an existing counterpart.

## Goals

- Add six agents to `agents/role_operations/`: `model_card_drafter`,
  `audit_trail_keeper`, `governance_readiness_checklist`,
  `second_look_backtest_reviewer`, `build_handoff_writer`, `alert_triage` —
  on the same four-file contract and `role_context.yml` configuration
  mechanism as Phase 1/2.
- Add `templates/docs/decision_log.md`, the template backing
  `audit_trail_keeper` — `agentic_dictionary.md` already defines "Decision
  Log" as a term but no template file existed for it.
- `model_card_drafter` populates `templates/docs/model_card.md` from
  supplied model information, marking any section the input doesn't cover
  as a gap rather than inventing a plausible-sounding fill.
- `audit_trail_keeper` appends `templates/docs/decision_log.md` entries
  (decision, rationale, alternatives considered, consequences, owner, date)
  as an append-only record, never rewriting or deleting a prior entry.
- `governance_readiness_checklist` walks
  `templates/docs/production_readiness_checklist.md` item by item, marking
  each evidenced (with a citation), a gap, or not applicable — never
  checked off without something to point to.
- `second_look_backtest_reviewer` runs a fast personal pre-check against
  `backtest_review`'s Required Review Themes, explicitly recommending the
  full `backtest_review` agent before any production promotion decision —
  framed throughout as a pre-check, never a substitute for it.
- `build_handoff_writer` populates `templates/docs/handoff_memo.md` from
  actual project state, flagging an unresolved item rather than omitting
  it to look more finished.
- `alert_triage` adds a personal priority/context pass over alerts already
  routed by `agents/alerts/alert_router/`, explicitly deferring all
  suppression, escalation, and lifecycle actions to `alert_router` and
  `agents/alerts/incident_notification/` — it annotates for the human, it
  does not re-route or resolve.
- Update `agents/role_operations/README.md`'s Phase tracking to Phase 1 +
  2 + 3 (roster complete), and update `agents/README.md`, `specs/README.md`,
  root `README.md`, `docs/handoff.md`, and
  `docs/handoffs/future_features.md` to match.

## Non-Goals

- No runtime code; agent contracts only, matching `0024`/`0029`'s own
  pattern.
- No change to `second_look_backtest_reviewer`'s or `alert_triage`'s
  counterpart agents (`backtest_review`, `alert_router`,
  `incident_notification`) — Phase 3 adds a layer in front of them, it does
  not modify their contracts.
- No change to `role_context.yml`'s schema in this slice. Phase 3's agents
  read the same fields Phase 1/2 already declared (stakeholders, domain,
  communication tone); none of the six needs a new field to produce a
  sensible generic result. The open question carried from `0024`/`0029`
  (whether the schema needs to grow for governance-evidence shape) is
  answered here: no growth needed, because these agents draft from
  whatever evidence the user supplies at the point of use, not from
  configuration.
- No automated authority to file, submit, or approve a governance artifact;
  every output in this slice is explicitly a draft for human review, per
  `instructions/role_operations.md`'s existing "agents draft, the human
  decides" standard.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide six Phase 3 role-operations agents (`model_card_drafter`, `audit_trail_keeper`, `governance_readiness_checklist`, `second_look_backtest_reviewer`, `build_handoff_writer`, `alert_triage`) on the four-file contract, each usable with no configuration and sharpened by optional local configuration. | must |
| REQ-002 | The system shall provide `templates/docs/decision_log.md`: decision, rationale, alternatives considered, consequences, owner, date — matching `agentic_dictionary.md`'s Decision Log definition. | must |
| REQ-003 | `model_card_drafter` shall populate `templates/docs/model_card.md` from supplied information and mark any uncovered section as a gap, never inventing a value. | must |
| REQ-004 | `audit_trail_keeper` shall append `templates/docs/decision_log.md` entries without rewriting or deleting a prior entry. | must |
| REQ-005 | `governance_readiness_checklist` shall mark every `templates/docs/production_readiness_checklist.md` item evidenced (with a citation), a gap, or not applicable — never checked off without a citation. | must |
| REQ-006 | `second_look_backtest_reviewer` shall run a fast pre-check against `backtest_review`'s Required Review Themes and explicitly recommend the full `backtest_review` agent before production promotion, framed as a pre-check, not a substitute. | must |
| REQ-007 | `build_handoff_writer` shall populate `templates/docs/handoff_memo.md` from actual project state and flag an unresolved item rather than omit it. | must |
| REQ-008 | `alert_triage` shall add a priority/context annotation pass over alerts already routed by `alert_router`, and shall not itself suppress, escalate, resolve, or re-route — those remain `alert_router`'s and `incident_notification`'s authority. | must |
| REQ-009 | `agents/role_operations/README.md`, `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, and `docs/handoffs/future_features.md` shall reflect Phase 3 as shipped and the fourteen-agent roster as complete. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Agent contract consistency | Every new public agent has `README.md`, `prompt.md`, `instructions.md`, `tasks.md`, each with a `Spec-Driven Role` section. |
| NFR-002 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates all pass. |
| NFR-003 | No fabrication | Every agent's `instructions.md` states explicitly that a value, decision, or citation absent from the input is flagged as a gap, never invented. |
| NFR-004 | Handoff clarity | `second_look_backtest_reviewer/README.md` and `alert_triage/README.md` each state explicitly, in their Purpose section, how they differ from and defer to their existing counterpart agent. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given each of the six agents' `instructions.md`, when inspected, then each explicitly states it must work without configuration and never persists real specifics into a tracked file. | REQ-001, NFR-001 |
| AC-002 | Given `templates/docs/decision_log.md`, when inspected, then it defines decision, rationale, alternatives considered, consequences, owner, and date fields. | REQ-002 |
| AC-003 | Given `model_card_drafter/instructions.md`, when inspected, then it requires marking any section `templates/docs/model_card.md` calls for but the input doesn't cover as a gap, not a fabricated value. | REQ-003, NFR-003 |
| AC-004 | Given `audit_trail_keeper/instructions.md`, when inspected, then it requires appending, never rewriting or deleting, a prior decision-log entry. | REQ-004 |
| AC-005 | Given `governance_readiness_checklist/instructions.md`, when inspected, then it requires every checklist item marked evidenced (with a citation), a gap, or not applicable — never checked off without one. | REQ-005 |
| AC-006 | Given `second_look_backtest_reviewer/README.md` and `instructions.md`, when inspected, then both state it is a fast pre-check that recommends the full `backtest_review` agent before production promotion, not a substitute for it. | REQ-006, NFR-004 |
| AC-007 | Given `build_handoff_writer/instructions.md`, when inspected, then it requires flagging an unresolved item in `templates/docs/handoff_memo.md` rather than omitting it. | REQ-007 |
| AC-008 | Given `alert_triage/README.md` and `instructions.md`, when inspected, then both state it never suppresses, escalates, resolves, or re-routes an alert, and that those actions remain `alert_router`'s and `incident_notification`'s authority. | REQ-008, NFR-004 |
| AC-009 | Given `agents/role_operations/README.md`, `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, and `docs/handoffs/future_features.md`, when inspected, then each lists all six Phase 3 agents and reflects the fourteen-agent roster as complete. | REQ-009 |
| AC-010 | Given the full gate suite, when run, then `spec`, `agent-catalog`, `docs-link`, `spec-index` all pass. | NFR-002 |

## Data & Dependencies

No data dependencies. No runtime code, consistent with `0024`/`0029`.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A Phase 3 draft (model card, governance checklist, decision log) gets filed as the final governance artifact without human review, given how close it sits to the real thing. | An unreviewed draft enters a governance process as if it were the approved artifact. | Every one of the six agents' `prompt.md` and `README.md` states its output is a draft for review, per `instructions/role_operations.md`'s existing "agents draft, the human decides" standard; nothing in this slice grants filing or approval authority. |
| RISK-002 | `second_look_backtest_reviewer`'s fast pre-check gives false confidence and a strategy skips the full `backtest_review` before promotion. | A production decision relies on a lighter check than the one the constitution's robustness standard actually requires. | `instructions.md`'s Operating Rules hardcode recommending full `backtest_review` before promotion as part of every output, not an optional closing line; the README's Purpose states the pre-check/full-review distinction up front. |
| RISK-003 | `alert_triage` suppresses, re-routes, or resolves an alert on its own authority, breaking `alert_router`'s dedup/lifecycle tracking. | An alert's real lifecycle state (acknowledged, escalated, resolved) diverges from what `alert_router`/`incident_notification` believe it to be. | `instructions.md` states plainly that `alert_triage` only annotates priority/context for the human; it never calls, mimics, or overrides `alert_router`'s or `incident_notification`'s lifecycle actions. |
| RISK-004 | `governance_readiness_checklist` marks an item "evidenced" without real evidence, just to present as more complete. | A reviewer trusts a checkmark that doesn't correspond to anything actually reviewed. | REQ-005/AC-005 require a citation for every evidenced item, not just a checkmark; the check in `instructions.md` asks explicitly whether each evidenced item cites something real. |

## Assumptions & Open Questions

- Assumption: Phase 3 is safe to ship now that Phase 1 and Phase 2 have
  both been used across real work in this session, completing the
  trust-building sequence the original roadmap called for.
- Assumption: `second_look_backtest_reviewer` and `alert_triage` add enough
  value as a fast personal layer in front of `backtest_review` and
  `alert_router`/`incident_notification` to justify existing alongside
  them, given the explicit non-substitute framing required by REQ-006/008.
- Open question: once all fourteen role-operations agents have real usage
  history, is a lightweight "which of these fourteen do I actually reach
  for" retrospective worth capturing back into
  `docs/handoffs/future_features.md`?

## Exceptions

None.
