# Tasks: Funding Ladder Min-Cost Flow

- **Spec:** 0035-funding-ladder (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-10

## Definition of Done (applies to every task)

- Standard-library only; no dependency added.
- No modification to `optimization_solvers.py` (`0013`) — composition only.
- Deterministic: the same tenors and obligations always return the same
  allocation and cost.
- Infeasibility is a stated status, never a partial result presented as
  full funding.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `solve_funding_ladder`, `FundingTenor`, `FundingObligation`, `FundingLadderResult`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001, NFR-002, NFR-003 | done | Bipartite network via `min_cost_flow`; eligibility by edge existence; per-obligation sink capacity forces full funding. |
| T-002 | Write `tests/test_funding_ladder.py`. | REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, NFR-001 | done | One test per acceptance criterion (AC-001 – AC-007). |
| T-003 | Wire catalogs and handoff docs. | REQ-006 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-004 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_every_obligation_fully_funded_AC_001` | done |
| AC-002 | `test_ineligible_tenor_never_used_AC_002` | done |
| AC-003 | `test_tenor_capacity_respected_AC_003` | done |
| AC-004 | `test_cheaper_tenor_preferred_AC_004` | done |
| AC-005 | `test_allocation_and_utilization_reported_AC_005` | done |
| AC-006 | `test_infeasible_reported_explicitly_AC_006` | done |
| AC-007 | `test_deterministic_AC_007` | done |
| AC-008 | Direct inspection of `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | done |

## Follow-ups

- Per-obligation infeasibility diagnostics, if a concrete workflow needs
  finer-grained feedback than the aggregate status (carried as an open
  question in `spec.md`).
- A rolling, time-stepped funding-ladder simulation, if a concrete
  workflow needs re-solving as time/rates change (explicitly out of scope
  for this static-snapshot slice).
