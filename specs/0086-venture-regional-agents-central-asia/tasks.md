# Tasks: Venture Regional Agent — Central Asia

- **Spec:** 0086-venture-regional-agents-central-asia (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Four contract files; never-boundary stated; no data or credentials.
- Tests pass deterministically; gates pass; no regression in existing tests.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Central Asia regional lead | REQ-001 | done | |
| T-002 | Cyrillic script and legal-form handling | REQ-002, NFR-001 | done | |
| T-003 | Russian-locale number parsing | REQ-003, NFR-001 | done | |
| T-004 | Golden cases, glossary term, script-variant rule | REQ-004, NFR-002 | done | |
| T-005 | Coverage matrix, roadmap, regional roster | REQ-005 | done | |
| T-006 | Catalog, standard, dictionary | REQ-006 | done | |
| T-007 | Run tests and gates | NFR-003 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_central_asia.py::test_ac001_* | done |
| AC-002 | tests/test_venture_central_asia.py::test_ac002_* | done |
| AC-003 | tests/test_venture_central_asia.py::test_ac003_* | done |
| AC-004 | tests/test_venture_central_asia.py::test_ac004_* | done |
| AC-005 | tests/test_venture_central_asia.py::test_ac005_* | done |
| AC-006 | tests/test_venture_central_asia.py::test_ac006_* | done |
| AC-007 | run-stage.sh gates + full pytest | done |
| AC-008 | tests/test_venture_central_asia.py::test_ac008_* | done |
