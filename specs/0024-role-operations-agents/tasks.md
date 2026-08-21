# Tasks: Role Operations Agents (Phase 1)

- **Spec:** 0024-role-operations-agents (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-09

## Definition of Done (applies to every task)

- Agent contracts follow the four-file convention with a `Spec-Driven Role`
  section in each `instructions.md`.
- No real firm, platform, client, team-member, or PII-shaped value anywhere
  in this slice's files.
- Every agent works with no configuration and states so explicitly.
- No secrets, credentials, or fabricated capability claims are introduced.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add `agents/role_operations/` group and four Phase-1 agents. | REQ-001, NFR-001 | done | `meeting_to_action/`, `status_rollup/`, `rapid_scaffolder/`, `prior_art_scanner/`, plus group `README.md`. |
| T-002 | Add the configuration template and document the resolution order. | REQ-002, NFR-003 | done | `templates/role_operations/role_context.yml`; `instructions/role_operations.md`. |
| T-003 | Add the `role-context` gate. | REQ-003, NFR-003 | done | `hooks/stages/role-context-check.sh`; tested in all three states (unconfigured, local-untracked, force-added). |
| T-004 | Wire catalogs, `.gitignore`, and `run-stage.sh`. | REQ-004, NFR-003 | done | `agents/README.md`, `specs/README.md`, root `README.md`, `.gitignore`, `hooks/stages/run-stage.sh`, `hooks/README.md`, `.github/workflows/ci.yml`. |
| T-005 | Run validation gates. | NFR-002 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `secret-scan`, `role-context`; full `pytest tests/ -q` (unaffected, docs/contracts-only); `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | Direct inspection of `templates/role_operations/role_context.yml`; `hooks/stages/role-context-check.sh` hygiene check | done |
| AC-002 | `hooks/stages/role-context-check.sh` run against a force-added `role_context.yml`, both advisory and `QF_STAGE_ENFORCE=1` | done |
| AC-003 | `hooks/stages/role-context-check.sh` run with no `role_context.yml` present | done |
| AC-004 | Direct inspection of each agent's `instructions.md` Operating Rules and Checks | done |
| AC-005 | `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index secret-scan role-context` | done |

## Follow-ups

- **Phase 2** (prototype accelerators): `demo_narrative_packager`,
  `tough_question_rehearsal`, `experiment_ledger`. Extends
  `agents/role_operations/` once Phase 1 has been used in practice.
- **Phase 3** (governance-adjacent, higher stakes — build trust first):
  `model_card_drafter`, `audit_trail_keeper`, `governance_readiness_checklist`,
  `second_look_backtest_reviewer`, `build_handoff_writer`, `alert_triage`.
- Consider whether `role_context.yml`'s schema needs to grow once Phase 2/3
  agents need richer configuration (e.g., a governance evidence checklist
  shape) than this slice's fields provide.
