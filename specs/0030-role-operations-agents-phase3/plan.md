# Plan: Role Operations Agents (Phase 3)

- **Spec:** 0030-role-operations-agents-phase3 (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Add six agents to the existing `agents/role_operations/` group, reusing its
established configuration mechanism (`role_context.yml`, spec `0024`) and
guardrail set (no fabrication, data-provenance disclosure, spec `0025`)
without modifying either. Four of the six populate an existing
`templates/docs/` template as a draft artifact (`model_card.md`,
`production_readiness_checklist.md`, `handoff_memo.md`, and a new
`decision_log.md`); the other two (`second_look_backtest_reviewer`,
`alert_triage`) sit in front of an existing agent that owns real
review/lifecycle authority (`backtest_review`,
`alert_router`/`incident_notification`) and hand off to it rather than
duplicating it.

## Architecture & Components

```text
templates/docs/decision_log.md   (new: decision, rationale, alternatives,
                                   consequences, owner, date)

agents/role_operations/
  model_card_drafter/              -- model info -> templates/docs/model_card.md draft
       reads: role_context.yml (domain/platform tailoring)
  audit_trail_keeper/              -- a decision as it's made -> append-only
                                       templates/docs/decision_log.md entry
  governance_readiness_checklist/  -- artifact state -> templates/docs/
                                       production_readiness_checklist.md,
                                       each item evidenced/gap/n-a
  second_look_backtest_reviewer/   -- a backtest result -> fast pre-check
                                       against backtest_review's Required
                                       Review Themes
       hands off to: agents/backtest_review/ (full review before promotion)
  build_handoff_writer/            -- project state -> templates/docs/
                                       handoff_memo.md draft
  alert_triage/                    -- routed alerts -> priority/context
                                       annotation for the human
       hands off to: agents/alerts/alert_router/,
                      agents/alerts/incident_notification/
                      (routing, suppression, escalation, lifecycle stay
                       theirs)
```

## Interfaces & Data Contracts

`templates/docs/decision_log.md` is the one new schema in this slice:
decision, rationale, alternatives considered, consequences, owner, date —
matching `agentic_dictionary.md`'s existing Decision Log definition. The
other three template-populating agents read schemas that already exist
(`model_card.md`, `production_readiness_checklist.md`, `handoff_memo.md`).
`second_look_backtest_reviewer` and `alert_triage` define no new schema;
each states its handoff explicitly in its own `instructions.md` Output
Contract.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P10 Honest reporting | yes | Every populated template marks what the input doesn't cover as a gap, never a fabricated fill; `governance_readiness_checklist` requires a citation for every item marked evidenced. |
| P3 Reproducibility & correctness (review discipline) | yes | `second_look_backtest_reviewer` explicitly cannot substitute for `backtest_review`'s full review before a production promotion decision — the pre-check adds a fast pass, it doesn't shrink the real gate. |
| P9 Security & data | yes | Same `role_context.yml`/no-tracked-real-data rules as Phase 1/2, unchanged; `alert_triage` never touches alert delivery credentials, that stays `adapters/alert_delivery/`'s and `alert_router`'s job. |
| P5 Reversibility | yes | Docs/contracts-only change, isolated on a branch; `audit_trail_keeper`'s append-only rule means a bad entry is corrected with a new entry, never a silent rewrite of history. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Six agent directories, four-file contract each | T-001 |
| REQ-002 | `templates/docs/decision_log.md` | T-001 |
| REQ-003 | `model_card_drafter/instructions.md` | T-001 |
| REQ-004 | `audit_trail_keeper/instructions.md` | T-001 |
| REQ-005 | `governance_readiness_checklist/instructions.md` | T-001 |
| REQ-006 | `second_look_backtest_reviewer/README.md`, `instructions.md` | T-001 |
| REQ-007 | `build_handoff_writer/instructions.md` | T-001 |
| REQ-008 | `alert_triage/README.md`, `instructions.md` | T-001 |
| REQ-009 | `agents/role_operations/README.md`, `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md` | T-002 |
| NFR-001 | Four-file contract + `Spec-Driven Role` per agent | T-001 |
| NFR-002 | Validation gates | T-003 |
| NFR-003 | "Never invent, flag as gap" as an explicit operating rule per agent | T-001 |
| NFR-004 | Explicit defer-to-counterpart framing in two READMEs | T-001 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope this slice | All 6 remaining agents together | Split Phase 3 further (e.g. governance-artifact agents vs. handoff agents) | All six share the same higher-stakes/governance-adjacent character the roadmap already grouped as "Phase 3"; splitting further adds spec overhead without a real risk-tier distinction between them. |
| `second_look_backtest_reviewer` relationship to `backtest_review` | A fast pre-check agent that hands off, with the non-substitute framing hardcoded into its output | Fold its behavior into `backtest_review` itself as an optional "quick mode" | A separate agent keeps `backtest_review`'s existing contract untouched (Non-Goal) and makes the pre-check/full-review distinction a matter of which agent you invoke, not a mode flag a user could silently leave on. |
| `alert_triage` relationship to `alert_router`/`incident_notification` | A read-only annotation layer with no lifecycle authority | Give `alert_triage` the ability to suppress/ack on the user's behalf | Suppression/ack/escalation are exactly the actions `alert_router`'s dedup and `incident_notification`'s lifecycle tracking depend on being singular and authoritative; a second actor with the same power breaks that invariant (RISK-003). |
| `role_context.yml` schema | Unchanged | Extend it now for a governance-evidence shape | Carried open question from `0024`/`0029`, resolved here: each Phase 3 agent drafts from evidence supplied at the point of use, not from configuration, so no schema growth is needed. |

## Validation Strategy

Run `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index`,
then the full `pytest tests/ -q` and `git diff --check`. AC-001 through
AC-009 are covered by direct inspection of each agent's `instructions.md`/
`README.md` and the six catalog/handoff files. AC-010 is covered by the
gate run itself.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; no existing agent, template, or gate changes behavior —
`backtest_review` and `alert_router`/`incident_notification` are unmodified.

## Open Questions

- Once all fourteen role-operations agents have real usage history, is a
  lightweight "which of these fourteen do I actually reach for" retrospective
  worth capturing back into `docs/handoffs/future_features.md`?
