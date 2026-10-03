# Tasks: Venture Fund and Portfolio Analytics

- **Spec:** 0091-venture-fund-and-portfolio-analytics (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-03

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Tests pass deterministically; standard library only; synthetic data only.
- Expected values come from hand or exact rational arithmetic, not from the module.
- Gates pass and no existing test regresses.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Multiples as of a date with known-at filtering | REQ-001 | done | |
| T-002 | XIRR with all roots and warnings | REQ-002 | done | |
| T-003 | J-curve cash profile and report-date series | REQ-003 | done | |
| T-004 | KS-PME and index lookup | REQ-004 | done | |
| T-005 | Peer percentile rank | REQ-005 | done | |
| T-006 | Mark-consistency review | REQ-006 | done | |
| T-007 | Seeded fund-outcome simulation and tail sensitivity | REQ-007, NFR-001, NFR-002 | done | |
| T-008 | Cohort bootstrap and equal-outcome null | REQ-008 | done | |
| T-009 | Reserve-policy simulation and table | REQ-009, NFR-002 | done | |
| T-010 | Conventions, flag registry, validator inclusion | REQ-010 | done | |
| T-011 | Three agents, coverage, workflow, indexes, registry, dictionary | REQ-011 | done | |
| T-012 | Roadmap split, gap register, next spec number | REQ-012 | done | |
| T-013 | Determinism checks, gates, full suite | NFR-001, NFR-003 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_fund_analytics.py::test_ac001_* | done |
| AC-002 | tests/test_venture_fund_analytics.py::test_ac002_* | done |
| AC-003 | tests/test_venture_fund_analytics.py::test_ac003_* | done |
| AC-004 | tests/test_venture_fund_analytics.py::test_ac004_* | done |
| AC-005 | tests/test_venture_fund_analytics.py::test_ac005_* | done |
| AC-006 | tests/test_venture_fund_analytics.py::test_ac006_* | done |
| AC-007 | tests/test_venture_fund_analytics.py::test_ac007_* | done |
| AC-008 | tests/test_venture_fund_analytics.py::test_ac008_* | done |
| AC-009 | tests/test_venture_fund_analytics.py::test_ac009_* | done |
| AC-010 | tests/test_venture_fund_analytics.py::test_ac010_* | done |
| AC-011 | tests/test_venture_fund_analytics.py::test_ac011_* | done |
| AC-012 | tests/test_venture_fund_analytics.py::test_ac012_* | done |
| AC-013 | run-stage.sh gates + full pytest | done |
