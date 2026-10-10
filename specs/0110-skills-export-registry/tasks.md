# Tasks: Skills export and registry

- **Spec:** 0110-skills-export-registry (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-10

> Every task cites a requirement; every acceptance criterion is named by a test.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests pass; `quantsmith-skills check` reports no findings on this repository.
- No hand-written content under `.claude/skills/` generated names.
- Docs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Agent | Notes |
| --- | --- | --- | --- | --- | --- |
| T-001 | Implement rendering, naming, descriptions, validation, and config overrides/excludes. | REQ-001, REQ-002, NFR-001 | done | `implementation` | Gitignored (local-only) agents are never exported. |
| T-002 | Implement the registry build: add, revise, retire, reactivate; idempotent writes. | REQ-003, REQ-004, NFR-002 | done | `implementation` | Generation 1 = 204 skills. |
| T-003 | Implement `check`; add the `skills-export` gate, pre-commit block, CI step, tests. | REQ-005 | done | `testing_validation` | Blocking in pre-commit and CI. |
| T-004 | Implement `pending`, `mark-published`, plugin and zip packaging; CLI `quantsmith-skills`. | REQ-006, REQ-007, NFR-003 | done | `implementation` | No network. |
| T-006 | Add project selection: only chosen categories/agents materialize in `.claude/skills/`; all stay registered and packaged. | REQ-008, RISK-003 | done | `implementation` | 53 of 204 selected. |
| T-005 | Decide the Claude.ai target: publish with `--pending-for claude_ai` + `mark-published`, or not. | REQ-006 | done | owner | Owner decision 2026-10-10: Claude.ai is not a target (the agents are not used in Claude.ai chat). Nothing is published there; the 99 older hand-exported copies on the account are to be deleted by the owner. The `claude_ai` target stays unmarked; the tooling remains available if that changes. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `tests/test_skills_export.py::test_repository_export_is_fresh_AC_001` | done |
| AC-002 | `tests/test_skills_export.py::test_rendered_skill_format_AC_002`, `::test_gitignored_agents_are_never_exported_AC_002` | done |
| AC-003 | `tests/test_skills_export.py::test_registry_lifecycle_AC_003` | done |
| AC-004 | `tests/test_skills_export.py::test_check_detects_drift_and_build_repairs_AC_004` | done |
| AC-005 | `tests/test_skills_export.py::test_name_validation_and_overrides_AC_005` | done |
| AC-006 | `tests/test_skills_export.py::test_pending_and_publication_marks_AC_006` | done |
| AC-007 | `tests/test_skills_export.py::test_packaging_plugin_and_zips_AC_007` | done |
| AC-008 | `tests/test_skills_export.py::test_cli_and_gate_AC_008` | done |
| AC-009 | `tests/test_skills_export.py::test_project_selection_AC_009` | done |
