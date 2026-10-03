# Tasks: Venture Tradecraft and Screening-Support Agents

- **Spec:** 0090-venture-tradecraft-and-screening-agents (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Four contract files per agent; never-boundary stated; no data or credentials.
- Helpers pure, tested, standard library only; gates pass; no regression.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Source reliability grader and grade/corroboration helpers | REQ-001, REQ-007 | done | |
| T-002 | Confidence language reviewer and wording helpers | REQ-002, REQ-007 | done | |
| T-003 | Competing hypotheses analyst, matrix, sensitivity | REQ-003, REQ-007 | done | |
| T-004 | Collection gap tracker and channel/aging/orphan helpers | REQ-004, REQ-007 | done | |
| T-005 | Ownership screen, effective ownership, threshold, lint | REQ-005, REQ-007, NFR-002 | done | |
| T-006 | Dual-use indicator | REQ-006 | done | |
| T-007 | Coverage, workflows, standard, catalog, group README, dictionary | REQ-008 | done | |
| T-008 | Tests, determinism, gates, full suite | NFR-001, NFR-003 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_tradecraft.py::test_ac001_* | done |
| AC-002 | tests/test_venture_tradecraft.py::test_ac002_* | done |
| AC-003 | tests/test_venture_tradecraft.py::test_ac003_* | done |
| AC-004 | tests/test_venture_tradecraft.py::test_ac004_* | done |
| AC-005 | tests/test_venture_tradecraft.py::test_ac005_* | done |
| AC-006 | tests/test_venture_tradecraft.py::test_ac006_* | done |
| AC-007 | tests/test_venture_tradecraft.py::test_ac007_* | done |
| AC-008 | tests/test_venture_tradecraft.py::test_ac008_* | done |
| AC-009 | tests/test_venture_tradecraft.py::test_ac009_* | done |
| AC-010 | tests/test_venture_tradecraft.py::test_ac010_* | done |
| AC-011 | tests/test_venture_tradecraft.py::test_ac011_* | done |
| AC-012 | tests/test_venture_tradecraft.py::test_ac012_* | done |
| AC-013 | run-stage.sh gates + full pytest | done |
