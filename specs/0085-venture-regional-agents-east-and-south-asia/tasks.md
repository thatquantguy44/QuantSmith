# Tasks: Venture Regional Agents — Greater China & East Asia, South Asia

- **Spec:** 0085-venture-regional-agents-east-and-south-asia (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Four contract files per agent; never-boundary stated; no data or credentials.
- Tests pass deterministically; gates pass.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Greater China and East Asia regional lead | REQ-001 | done | |
| T-002 | Greater China entity-structure analyst | REQ-002 | done | |
| T-003 | South Asia regional lead | REQ-003 | done | |
| T-004 | Convention extensions with citations or unverified | REQ-004, NFR-002 | done | |
| T-005 | Parser, era function, golden cases | REQ-005, NFR-001 | done | |
| T-006 | Update catalog, standard, dictionary, coverage, roster | REQ-006 | done | |
| T-007 | Run tests and gates | NFR-003 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_regions.py::test_ac001_* | done |
| AC-002 | tests/test_venture_regions.py::test_ac002_* | done |
| AC-003 | tests/test_venture_regions.py::test_ac003_* | done |
| AC-004 | tests/test_venture_regions.py::test_ac004_* | done |
| AC-005 | tests/test_venture_regions.py::test_ac005_* | done |
| AC-006 | tests/test_venture_regions.py::test_ac006_* | done |
| AC-007 | run-stage.sh spec + agent-catalog + handoff-sync | done |
| AC-008 | tests/test_venture_regions.py::test_ac008_* | done |
