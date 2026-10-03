# Tasks: Venture Signal Analysts and Sourcing Agents

- **Spec:** 0089-venture-signal-and-sourcing-agents (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Four contract files per agent; never-boundary stated; no data or credentials.
- Tests pass deterministically; gates pass; no regression.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Patent and IP analyst | REQ-001, NFR-001 | done | |
| T-002 | Hiring signal analyst | REQ-002, NFR-001 | done | |
| T-003 | Narrative and news analyst | REQ-003, NFR-001 | done | |
| T-004 | Technology landscape analyst | REQ-004, NFR-001 | done | |
| T-005 | Deal sourcing | REQ-005, NFR-001 | done | |
| T-006 | Company diligence | REQ-006, NFR-001 | done | |
| T-007 | Decision-path classes in coverage and workflow-class rule | REQ-007 | done | |
| T-008 | Update coverage, workflows, catalog, standard, group README, dictionary | REQ-008 | done | |
| T-009 | Run tests and gates; review content for data | NFR-002, NFR-003 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_signals.py::test_ac001_* | done |
| AC-002 | tests/test_venture_signals.py::test_ac002_* | done |
| AC-003 | tests/test_venture_signals.py::test_ac003_* | done |
| AC-004 | tests/test_venture_signals.py::test_ac004_* | done |
| AC-005 | tests/test_venture_signals.py::test_ac005_* | done |
| AC-006 | tests/test_venture_signals.py::test_ac006_* | done |
| AC-007 | tests/test_venture_signals.py::test_ac007_* | done |
| AC-008 | tests/test_venture_signals.py::test_ac008_* | done |
| AC-009 | run-stage.sh gates + full pytest | done |
| AC-010 | tests/test_venture_signals.py::test_ac010_* | done |
