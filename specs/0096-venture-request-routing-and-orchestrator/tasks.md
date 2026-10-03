# Tasks: Venture Request Routing and Orchestrator

- **Spec:** 0096-venture-request-routing-and-orchestrator (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-03

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Tests pass deterministically; standard library only; synthetic requests only.
- Every routing reference is validated; no path to a decision or release exists.
- Gates pass and no existing test regresses.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Routing rules as reviewable data | REQ-001 | done | |
| T-002 | Validator routing block and reachability | REQ-002, REQ-003 | done | |
| T-003 | Refusals in every word order | REQ-004 | done | |
| T-004 | Task classification with clarification | REQ-005 | done | |
| T-005 | Region detection and placeholder expansion | REQ-006 | done | |
| T-006 | Non-English script step | REQ-007 | done | |
| T-007 | Strictest class and clearance denial | REQ-008 | done | |
| T-008 | Plan shape, determinism, no mutation | REQ-009, NFR-001 | done | |
| T-009 | Agent contract, coverage, indexes, registry, glossary | REQ-010, NFR-002 | done | |
| T-010 | Gates and full suite | NFR-003 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_routing.py::test_ac001_* | done |
| AC-002 | tests/test_venture_routing.py::test_ac002_* | done |
| AC-003 | tests/test_venture_routing.py::test_ac003_* | done |
| AC-004 | tests/test_venture_routing.py::test_ac004_* | done |
| AC-005 | tests/test_venture_routing.py::test_ac005_* | done |
| AC-006 | tests/test_venture_routing.py::test_ac006_* | done |
| AC-007 | tests/test_venture_routing.py::test_ac007_* | done |
| AC-008 | tests/test_venture_routing.py::test_ac008_* | done |
| AC-009 | run-stage.sh gates + full pytest | done |
