# Tasks: Venture Sources, Point-in-Time Ingestion & Entity Resolution

- **Spec:** 0088-venture-sources-pit-ingestion (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-02

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Tests exist and pass deterministically; synthetic data only.
- No credentials; unverified claims labelled.
- Gates pass.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add eleven source entries and index rows | REQ-001, NFR-002 | done | |
| T-002 | known_at policies and `derive_known_at` with late-retrieval flag | REQ-002, REQ-003 | done | |
| T-003 | As-of views and outcome-independent cohorts | REQ-004, REQ-005 | done | |
| T-004 | Name normalization and entity-resolution decisions | REQ-006, REQ-007 | done | |
| T-005 | Entity-resolution agent contract | REQ-008 | done | |
| T-006 | Index in agents, standard, dictionary, coverage | REQ-009 | done | |
| T-007 | Tests and gate runs | NFR-001, NFR-003 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_ingestion.py::test_ac001_*, source-catalog gate | done |
| AC-002 | tests/test_venture_ingestion.py::test_ac002_* | done |
| AC-003 | tests/test_venture_ingestion.py::test_ac003_* | done |
| AC-004 | tests/test_venture_ingestion.py::test_ac004_* | done |
| AC-005 | tests/test_venture_ingestion.py::test_ac005_* | done |
| AC-006 | tests/test_venture_ingestion.py::test_ac006_* | done |
| AC-007 | tests/test_venture_ingestion.py::test_ac007_* | done |
| AC-008 | tests/test_venture_ingestion.py::test_ac008_*, agent-catalog gate | done |
| AC-009 | tests/test_venture_ingestion.py::test_ac009_* | done |
| AC-010 | tests/test_venture_ingestion.py::test_ac010_* | done |
| AC-011 | tests/test_venture_ingestion.py::test_ac011_* | done |
