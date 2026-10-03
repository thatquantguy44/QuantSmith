# Tasks: Venture Predictive-Model Reference Baselines

- **Spec:** 0095-venture-predictive-model-baselines (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-03

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Tests pass deterministically; standard library only; synthetic data only, stated as such.
- Expected values come from hand or exact rational arithmetic, or a generating process with known truth.
- Gates pass and no existing test regresses.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Point-in-time tools | REQ-001 | done | |
| T-002 | Kaplan-Meier and Aalen-Johansen | REQ-002 | done | |
| T-003 | Cause-specific hazard model and horizon handling | REQ-003 | done | |
| T-004 | Out-of-time calibration, concordance, bootstrap | REQ-004 | done | |
| T-005 | Emergence indicator and retrospective replay | REQ-005 | done | |
| T-006 | Organization-level link prediction | REQ-006 | done | |
| T-007 | Anomaly indicator with incomplete-period handling | REQ-007 | done | |
| T-008 | Chain-ladder nowcast, vintages, backtest | REQ-008 | done | |
| T-009 | Deployability gate, catalog fields, validator rule | REQ-009, NFR-002 | done | |
| T-010 | Synthetic generators and determinism | REQ-010, NFR-001 | done | |
| T-011 | Gap, roadmap, indexes, run card | REQ-011 | done | |
| T-012 | Gates and full suite | NFR-003 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | tests/test_venture_models.py::test_ac001_* | done |
| AC-002 | tests/test_venture_models.py::test_ac002_* | done |
| AC-003 | tests/test_venture_models.py::test_ac003_* | done |
| AC-004 | tests/test_venture_models.py::test_ac004_* | done |
| AC-005 | tests/test_venture_models.py::test_ac005_* | done |
| AC-006 | tests/test_venture_models.py::test_ac006_* | done |
| AC-007 | tests/test_venture_models.py::test_ac007_* | done |
| AC-008 | tests/test_venture_models.py::test_ac008_* | done |
| AC-009 | tests/test_venture_models.py::test_ac009_* | done |
| AC-010 | tests/test_venture_models.py::test_ac010_* | done |
| AC-011 | tests/test_venture_models.py::test_ac011_* | done |
| AC-012 | run-stage.sh gates + full pytest | done |
