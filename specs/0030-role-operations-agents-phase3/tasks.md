# Tasks: Role Operations Agents (Phase 3)

- **Spec:** 0030-role-operations-agents-phase3 (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Agent contracts follow the four-file convention with a `Spec-Driven Role`
  section in each `instructions.md`.
- Each agent works with no configuration and states so explicitly.
- No real firm, platform, client, team-member, or PII-shaped value anywhere
  in this slice's files.
- No fabricated capability claims.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add `templates/docs/decision_log.md` and six Phase 3 agents. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, NFR-001, NFR-003, NFR-004 | done | `model_card_drafter/`, `audit_trail_keeper/`, `governance_readiness_checklist/`, `second_look_backtest_reviewer/`, `build_handoff_writer/`, `alert_triage/`. |
| T-002 | Update Phase tracking and catalogs. | REQ-009 | done | `agents/role_operations/README.md`, `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`. |
| T-003 | Run validation gates. | NFR-002 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | Direct inspection of each of the six agents' `instructions.md` | done |
| AC-002 | Direct inspection of `templates/docs/decision_log.md` | done |
| AC-003 | Direct inspection of `model_card_drafter/instructions.md` | done |
| AC-004 | Direct inspection of `audit_trail_keeper/instructions.md` | done |
| AC-005 | Direct inspection of `governance_readiness_checklist/instructions.md` | done |
| AC-006 | Direct inspection of `second_look_backtest_reviewer/README.md`, `instructions.md` | done |
| AC-007 | Direct inspection of `build_handoff_writer/instructions.md` | done |
| AC-008 | Direct inspection of `alert_triage/README.md`, `instructions.md` | done |
| AC-009 | Direct inspection of `agents/role_operations/README.md`, `agents/README.md`, `specs/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md` | done |
| AC-010 | `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index` | done |

## Follow-ups

- The fourteen-agent role-operations roster (Phases 1–3) is now complete.
  A future retrospective on which agents see real use is an open question
  carried into `docs/handoffs/future_features.md`, not a task here.
