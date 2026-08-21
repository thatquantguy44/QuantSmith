# Tasks: Remaining Backing Instructions (Risk, Data Ingestion, Reproducibility)

- **Spec:** 0031-remaining-backing-instructions (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Each new instruction file follows the existing backing-standard shape.
- No existing agent's operating rules, gate logic, or template contract
  changes — cross-references only.
- No fabricated capability claims (e.g. no implying the `repro` gate
  checks more than it does).

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `instructions/risk_management.md`. | REQ-001, NFR-001 | done | Exposure, concentration, drawdown/tail, stress testing, monitorable limits. |
| T-002 | Write `instructions/data_ingestion.md`. | REQ-002, NFR-001 | done | Point-in-time capture, snapshotting, credential handling via the source catalog, schema validation. |
| T-003 | Write `instructions/reproducibility.md`. | REQ-003, NFR-001 | done | States what P4 requires; documents the `repro` gate's actual mechanism and `run_card.md`. |
| T-004 | Cross-reference each standard from the agents it backs. | REQ-004, NFR-003 | done | `agents/risk/instructions.md`, `agents/data_ingestion/README.md` + 3 sub-agents, `agents/implementation/instructions.md`, `agents/testing_validation/instructions.md`. |
| T-005 | Update catalogs and handoff docs. | REQ-005 | done | Root `README.md` instructions table, `docs/handoff.md` item 9, `docs/handoffs/future_features.md` Instructions table, `specs/README.md`. |
| T-006 | Run validation gates. | NFR-002 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | Direct inspection of `instructions/risk_management.md` | done |
| AC-002 | Direct inspection of `instructions/data_ingestion.md` | done |
| AC-003 | Direct inspection of `instructions/reproducibility.md` | done |
| AC-004 | Direct inspection of the four cross-referenced agents' `instructions.md` | done |
| AC-005 | Direct inspection of root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md` | done |
| AC-006 | `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index` | done |

## Follow-ups

- None identified; this closes the "remaining backing instructions" line
  item in `docs/handoff.md`'s What's Next.
