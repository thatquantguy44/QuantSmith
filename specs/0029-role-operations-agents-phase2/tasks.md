# Tasks: Role Operations Agents (Phase 2)

- **Spec:** 0029-role-operations-agents-phase2 (`spec.md`, `plan.md`)
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
| T-001 | Add three Phase 2 agents. | REQ-001, REQ-002, REQ-003, REQ-004, NFR-001, NFR-003 | done | `demo_narrative_packager/`, `tough_question_rehearsal/`, `experiment_ledger/`. |
| T-002 | Update Phase tracking and catalogs. | REQ-005 | done | `agents/role_operations/README.md`, `agents/README.md`, `specs/README.md`. |
| T-003 | Run validation gates. | NFR-002 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | Direct inspection of each agent's `instructions.md` | done |
| AC-002 | Direct inspection of `demo_narrative_packager/instructions.md` | done |
| AC-003 | Direct inspection of `tough_question_rehearsal/instructions.md` | done |
| AC-004 | Direct inspection of `experiment_ledger/instructions.md` | done |
| AC-005 | Direct inspection of `agents/role_operations/README.md`, `agents/README.md`, `specs/README.md` | done |
| AC-006 | `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index` | done |

## Follow-ups

- **Phase 3** (governance-adjacent, higher stakes — build trust first):
  `model_card_drafter`, `audit_trail_keeper`, `governance_readiness_checklist`,
  `second_look_backtest_reviewer`, `build_handoff_writer`, `alert_triage`.
- Revisit whether `role_context.yml`'s schema needs to grow for Phase 3's
  governance-evidence shape (carried from `0024`).
