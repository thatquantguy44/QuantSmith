# Spec: Remaining Backing Instructions (Risk, Data Ingestion, Reproducibility)

- **ID:** 0031-remaining-backing-instructions
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`docs/handoff.md`'s "What's Next" has long carried a standing line item:
three domains already have an agent or a gate acting on their behalf, but
no written standard backing that behavior — `agents/risk/` reviews
exposure, tail, and limits from prompt instructions alone;
`agents/data_ingestion/*` (three agents) each restate point-in-time
capture, snapshotting, and schema-validation rules independently in their
own `instructions.md` rather than deferring to one shared standard; and
the `repro` gate (`hooks/stages/repro-check.sh`) and
`templates/docs/run_card.md` operationalize constitution P4
(reproducibility) with no single document stating what P4 actually
requires end to end. Every other cross-cutting domain in the SDK
(alerting, monitoring, point-in-time, data provenance) already has this
kind of standard; these three are the last gap.

## Goals

- Add `instructions/risk_management.md`: exposure (intended vs.
  unintended), concentration, drawdown/tail behavior, stress and scenario
  testing, and monitorable risk limits — the standard behind `agents/risk/`.
- Add `instructions/data_ingestion.md`: point-in-time capture, reproducible
  snapshotting, credential handling via the source catalog, and schema
  validation on load — the shared standard behind
  `agents/data_ingestion/{database_connectivity,file_ingestion,api_ingestion}/`,
  replacing each agent's independently-restated version of the same rules
  with one deferred-to source.
- Add `instructions/reproducibility.md`: what constitution P4 requires in
  practice (pinned inputs, seeded randomness, no hidden state, a run card)
  — operationalizing the `repro` gate and `templates/docs/run_card.md`,
  and the standard behind the `implementation` and `testing_validation`
  lifecycle agents.
- Cross-reference each new standard from the agents it backs (a
  `Related`/`Spec-Driven Role` link, not a rewrite of each agent's own
  operating rules) and from the root `README.md`'s instructions table.

## Non-Goals

- No new gate. `repro` already exists and already checks for a run
  manifest, a dependency lockfile, and seeded randomness in changed code;
  `reproducibility.md` documents what that gate is checking and why, it
  does not change the gate's behavior.
- No rewrite of `agents/risk/instructions.md` or the three
  `data_ingestion/*/instructions.md` files' existing operating rules —
  each already states sound rules; this spec gives them a shared standard
  to defer to and cross-reference, consistent with how `alerting.md`
  backs `agents/alerts/*` without restating each agent's own rules.
- No new risk-limit schema or dataset-snapshot schema; `risk_management.md`
  and `data_ingestion.md` describe the standard qualitatively, matching how
  `instructions/backtesting.md` and `instructions/data_quality.md` already
  operate without a companion schema of their own.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide `instructions/risk_management.md`, covering exposure, concentration, drawdown/tail behavior, stress testing, and monitorable risk limits. | must |
| REQ-002 | The system shall provide `instructions/data_ingestion.md`, covering point-in-time capture, reproducible snapshotting, credential handling (deferring to the source catalog), and load-time schema validation. | must |
| REQ-003 | The system shall provide `instructions/reproducibility.md`, stating what constitution P4 requires and how the `repro` gate and `templates/docs/run_card.md` check and capture it. | must |
| REQ-004 | `agents/risk/`, `agents/data_ingestion/*`, `agents/implementation/`, and `agents/testing_validation/` shall each cross-reference the standard that backs them. | must |
| REQ-005 | Root `README.md`'s instructions table, `docs/handoff.md`, and `docs/handoffs/future_features.md` shall reflect all three standards as shipped. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Standard consistency | Each new instruction file follows the existing backing-standard shape (Why/Rules or Checklist/Runtime & Spec or equivalent), matching `instructions/alerting.md`/`instructions/point_in_time.md`. |
| NFR-002 | Repository hygiene | `spec`, `docs-link`, `agent-catalog`, `spec-index` gates and the full pytest suite pass. |
| NFR-003 | No behavior change | No existing agent's operating rules, gate logic, or template contract changes — this slice is additive documentation and cross-references only. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `instructions/risk_management.md`, when inspected, then it covers exposure, concentration, drawdown/tail behavior, stress testing, and monitorable risk limits, and states it backs `agents/risk/`. | REQ-001 |
| AC-002 | Given `instructions/data_ingestion.md`, when inspected, then it covers point-in-time capture, reproducible snapshotting, credential handling via the source catalog, and schema validation, and states it backs the three `data_ingestion/*` agents. | REQ-002 |
| AC-003 | Given `instructions/reproducibility.md`, when inspected, then it states what P4 requires and names the `repro` gate and `templates/docs/run_card.md` as its operational checks. | REQ-003 |
| AC-004 | Given `agents/risk/instructions.md`, each `agents/data_ingestion/*/instructions.md`, `agents/implementation/instructions.md`, and `agents/testing_validation/instructions.md`, when inspected, then each references its backing standard. | REQ-004 |
| AC-005 | Given root `README.md`, `docs/handoff.md`, and `docs/handoffs/future_features.md`, when inspected, then all three standards are listed as shipped, not proposed. | REQ-005 |
| AC-006 | Given the full gate suite, when run, then `spec`, `docs-link`, `agent-catalog`, `spec-index` all pass. | NFR-002 |

## Data & Dependencies

No data dependencies, no runtime code — documentation and cross-reference
edits only, consistent with how `instructions/monitoring.md` and
`instructions/alerting.md` were added.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A new standard duplicates rather than complements an existing agent's own `instructions.md`, creating two slightly different sources of truth for the same rule. | A future edit updates one copy and not the other, and the two drift apart. | Each standard is written to be the single source for the *shared* rule (e.g. "point-in-time capture" once, not per agent); each backed agent's `instructions.md` gets a cross-reference, not a restated copy — the same pattern already proven by `alerting.md` backing three `alerts/*` agents without duplication. |
| RISK-002 | `reproducibility.md` implies the `repro` gate checks more than it actually does (the gate is a heuristic — run-manifest/lockfile presence and a naive seeded-randomness grep), giving false confidence. | A reader assumes reproducibility is mechanically verified when it is only advisorially checked. | The standard states the gate's actual, narrow mechanism explicitly (what it greps for, that it is advisory unless `QF_STAGE_ENFORCE=1`), the same honestly-scoped-limitation pattern `point_in_time.md` and `data_provenance.md` already use for their own heuristic gates. |

## Assumptions & Open Questions

- Assumption: qualitative standards (no new schema, no new gate) are the
  right shape for these three, matching `backtesting.md`/`data_quality.md`
  rather than the schema-plus-gate shape used where a new checkable
  artifact was actually being introduced (`data_provenance.md`,
  `data_source_catalog.md`).
- Open question: if `agents/risk/` or `agents/data_ingestion/*` grow a
  concrete schema of their own later (a risk-limits config, a snapshot
  manifest), does it belong in `templates/data/` as its own artifact, or
  stay described qualitatively in the standard? Deferred until a concrete
  workflow needs one.

## Exceptions

None.
