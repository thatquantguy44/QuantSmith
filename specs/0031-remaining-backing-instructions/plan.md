# Plan: Remaining Backing Instructions (Risk, Data Ingestion, Reproducibility)

- **Spec:** 0031-remaining-backing-instructions (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Write three standalone instruction files, one per domain, following the
existing backing-standard shape used by `instructions/alerting.md` (Why /
Rules / Checklist / Runtime & Spec) and `instructions/point_in_time.md`
(checklist-first, for a domain that's mostly a review list). Each gets a
short cross-reference added to the agents it backs — not a rewrite of
those agents' own operating rules, matching how `alerting.md` was wired
into `agents/alerts/*` without duplicating each agent's contract.

## Architecture & Components

```text
instructions/risk_management.md
  backs: agents/risk/
  cross-referenced from: agents/risk/instructions.md (Spec-Driven Role)

instructions/data_ingestion.md
  backs: agents/data_ingestion/{database_connectivity,file_ingestion,api_ingestion}/
  cross-referenced from: agents/data_ingestion/README.md,
    each sub-agent's instructions.md (Spec-Driven Role)

instructions/reproducibility.md
  backs: hooks/stages/repro-check.sh, templates/docs/run_card.md
  cross-referenced from: agents/implementation/instructions.md,
    agents/testing_validation/instructions.md (Spec-Driven Role)
```

## Interfaces & Data Contracts

No new schema. All three standards are qualitative (no companion template
or gate), matching `instructions/backtesting.md` and
`instructions/data_quality.md`'s existing shape.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | `reproducibility.md` is the direct operationalization of P4; `data_ingestion.md`'s point-in-time capture rules extend the same principle to the ingestion boundary. |
| P8 No silent trade-offs | yes | `risk_management.md` requires tying every named risk to a monitorable metric and a stated breach action, not a narrative-only risk section. |
| P10 Honest reporting | yes | `reproducibility.md` states the `repro` gate's actual (narrow, heuristic) mechanism rather than implying a stronger guarantee than it provides. |
| P5 Reversibility | yes | Documentation and cross-reference edits only, isolated on a branch; no gate or agent behavior changes. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `instructions/risk_management.md` | T-001 |
| REQ-002 | `instructions/data_ingestion.md` | T-002 |
| REQ-003 | `instructions/reproducibility.md` | T-003 |
| REQ-004 | `agents/risk/instructions.md`, `agents/data_ingestion/*/instructions.md`, `agents/implementation/instructions.md`, `agents/testing_validation/instructions.md` | T-004 |
| REQ-005 | Root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md` | T-005 |
| NFR-001 | Shape matches `alerting.md`/`point_in_time.md` | T-001, T-002, T-003 |
| NFR-002 | Validation gates | T-006 |
| NFR-003 | No agent/gate/template edits beyond cross-references | T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Scope | All three standards in one slice | Three separate specs | The backlog already groups them as one line item ("remaining backing instructions"); they're independent in content but identical in kind (fill a documentation gap behind existing behavior), so one spec avoids three near-identical spec/plan/tasks sets for work that isn't actually interdependent but is uniformly small. |
| `data_ingestion.md` scope | One shared standard for all three ingestion agents | A separate standard per agent (`api_ingestion.md`, `file_ingestion.md`, `database_connectivity.md`) | The three agents already state near-identical point-in-time/secret/reproducibility rules independently (visible in each `instructions.md` today); one shared standard is the actual fix for that duplication, not three more copies. |
| `reproducibility.md` depth | Document the `repro` gate's real (heuristic) mechanism explicitly | Write an idealized reproducibility standard disconnected from what the gate actually checks | Matches this repo's own honest-reporting principle (P10) and the precedent set by `point_in_time.md`/`data_provenance.md`, both of which state their gate's real, narrow mechanism rather than implying more rigor than exists. |

## Validation Strategy

Run `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index`,
then the full `pytest tests/ -q` (expected unaffected — no runtime code in
this slice) and `git diff --check`. AC-001 through AC-005 are covered by
direct inspection of the three new instruction files and the cross-
referenced/updated catalog files. AC-006 is covered by the gate run itself.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; no existing gate, agent contract, or template changes
behavior.

## Open Questions

- If `agents/risk/` or `agents/data_ingestion/*` grow a concrete schema
  later (risk-limits config, snapshot manifest), does it belong in
  `templates/data/` as its own artifact? Deferred until a concrete
  workflow needs one.
