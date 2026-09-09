# Spec: Securities-Lending Model Correction & Expansion

- **ID:** 0066-securities-lending-model-correction
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-09-09

## Problem & Context

`knowledge/short_term_markets/gap_register.md` (spec `0063`) names six
concrete, evidenced discrepancies between the current securities-financing
runtime and the canonical `0063` domain pack. Five are owned, fully or
partly, by `0066`:

- **D-0063-002 (high):** `sec_lending.py`'s GC/WARM/HTB classification
  thresholds (`_GC_THRESHOLD = 50`, `_WARM_THRESHOLD = 200`) are hardcoded
  module constants presented without qualification, looking like universal
  market rules rather than a stated model assumption.
- **D-0063-003 (high):** `sec_lending.py` computes fee/rebate accrual on a
  `/252` (trading-days) basis while `financing_cost_analysis.py` and `0063`'s
  registered conventions (`convention.seclend.borrow_fee_act360_simple`,
  `convention.seclend.rebate_act360_simple`) use ACT/360 — an unstated,
  incompatible day-count mismatch between two modules in the same chain.
- **D-0063-004 (medium):** `InventoryOptimizationAgent`'s docstring claims a
  per-counterparty exposure constraint; `_optimize()` never implements one,
  and `OptimizedAllocation.counterparty` was a placeholder string
  (`"BEST_AVAILABLE"`), not a real assignment.
- **D-0063-005 (high):** `financing_cost_analysis.py`'s
  `check_point_in_time` only flags a rate known after `period_end`, missing
  a rate first known mid-period and applied retroactively to the whole
  period (including days before it was knowable).
- **D-0063-006 (medium):** `financing_cost_analysis.py` applies one hardcoded
  `_DAY_COUNT_BASIS` to every leg regardless of product.

D-0063-001 (repo-special vs. stock-loan-special sign/viewpoint ambiguity)
was already corrected at the `0063` contract layer
(`concept.repo_special`/`concept.stock_loan_special`); its remaining
`0066` slice is documentation only.

Every fix is grounded in `0063`'s own already-reviewed golden cases —
`golden.seclend.fee_rebate_signs` (exact ACT/360 fee/rebate numbers) and
`golden.temporal.asof_excludes_later_known_rate` ("knowledge_as_of must be
on or before the query as_of date") — not invented correctness.

## Goals

- Correct `sec_lending.py`'s classification thresholds, day-count basis, and
  counterparty-concentration claim (D-0063-002, 003, 004).
- Correct `financing_cost_analysis.py`'s point-in-time boundary and make its
  day-count basis explicit per leg (D-0063-005, 006).
- Update `agents/securities_financing/securities_lending/instructions.md` to
  cite the `concept.repo_special`/`concept.stock_loan_special` distinction
  explicitly (D-0063-001's remaining slice).
- Update `gap_register.md`'s disposition for each corrected row, and move
  `0066` from reserved to written/implemented in the catalogs.

## Non-Goals

- No LP reformulation to a real per-counterparty allocation. The SQL data
  model (`sql_data.py`) has no per-security × per-counterparty demand to
  allocate against; inventing one would fabricate data, which `0063`'s own
  real-data-first standard rules out. `InventoryOptimizationAgent`'s
  docstring is corrected to state this plainly; `SecLendingRiskAgent`
  remains the actual counterparty-concentration enforcement point (already
  correct, already tested).
- No sub-period rate segmentation in `check_point_in_time` — a mid-period
  rate is flagged as a whole, not partially admitted for its own later
  sub-period. Matches the gap register's own disposition for D-0063-005.
- No variable-notional or cashflow-scheduling engine. `day_count_basis`
  becomes an explicit, overridable per-leg field; nothing about notional or
  scheduling changes.
- No change to `0023`'s or `0028`'s public API shape beyond additive,
  default-preserving parameters (`gc_threshold_bps`, `warm_threshold_bps` on
  `SecLendingUniverseAgent`; `day_count_basis` on `FinancingLeg`) — every
  existing caller using defaults is unaffected except by the two
  deliberate corrections (day-count, PIT boundary), both of which change
  output value, not API shape.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `SecLendingUniverseAgent` shall accept configurable GC/WARM classification thresholds, defaulting to the prior values, rather than hardcoded module constants. | must |
| REQ-002 | `sec_lending.py`'s fee/rebate accrual shall use an ACT/360 day-count basis, matching `financing_cost_analysis.py` and `0063`'s registered `convention.seclend.*` conventions. | must |
| REQ-003 | `InventoryOptimizationAgent`'s docstring and `OptimizedAllocation.counterparty` shall state plainly that this LP has no counterparty dimension and does not enforce `max_cp_concentration`; `SecLendingRiskAgent` shall remain the stated enforcement point. | must |
| REQ-004 | `financing_cost_analysis.py`'s `check_point_in_time` shall flag a financing leg whose rate was not known by its position's `period_start`, not only after `period_end`. | must |
| REQ-005 | `FinancingLeg` shall carry an explicit, overridable `day_count_basis` field, defaulting to the prior global constant's value. | must |
| REQ-006 | `agents/securities_financing/securities_lending/instructions.md` shall cite `concept.repo_special`/`concept.stock_loan_special` by ID. | must |
| REQ-007 | `gap_register.md`'s disposition for D-0063-002 through D-0063-006 shall be updated to reference the corrected runtime and its test. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Backward compatibility | Every existing test in `test_sec_lending_workflow.py`/`test_financing_cost_analysis.py` continues to pass unmodified, except the two spots whose values were hardcoded to the pre-correction day-count/PIT behavior (updated to match the correction, not relaxed). |
| NFR-002 | Correctness grounding | Every new/updated test's expected value traces to a specific `0063` `golden.*` record by ID, not an ad hoc number. |
| NFR-003 | Repository hygiene | `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `agent-catalog`, `source-catalog`, `secret-scan` gates and the full pytest suite pass. |
| NFR-004 | Honest scope | No code or doc claims a counterparty-level allocation constraint that isn't actually enforced. |

## Acceptance Criteria

| ID | Given / When | Then | Covers |
| --- | --- | --- | --- |
| AC-001 | Given `SecLendingUniverseAgent` with custom `gc_threshold_bps`/`warm_threshold_bps`, when a security's rate is classified | the custom thresholds apply, and default construction reproduces the prior GC≤50/WARM≤200/HTB>200 boundaries exactly. | REQ-001 |
| AC-002 | Given a $1,000,000 balance, 250bps borrow fee, 50bps rebate, 30 days, when `sec_lending.py`'s fee formula is evaluated | the 30-day totals equal `golden.seclend.fee_rebate_signs`'s exact expected outputs ($2,083.33 / $416.67 / $1,666.67). | REQ-002, NFR-002 |
| AC-003 | Given `InventoryOptimizationAgent` run with two different `max_cp_concentration` values on the same universe | the allocations are identical (proving the parameter has no effect), and every `OptimizedAllocation.counterparty` is `None`. | REQ-003, NFR-004 |
| AC-004 | Given a financing leg whose `rate_asof` is after `period_start` but before `period_end` | `check_point_in_time` flags it; a rate known at or before `period_start` remains clean. | REQ-004, NFR-002 |
| AC-005 | Given a `FinancingLeg` with an explicit `day_count_basis` other than 360 | the computed leg cost changes accordingly; the default (360) reproduces prior results unchanged. | REQ-005 |
| AC-006 | Given `agents/securities_financing/securities_lending/instructions.md`, when inspected | it cites `concept.repo_special`/`concept.stock_loan_special` by ID. | REQ-006 |
| AC-007 | Given `gap_register.md`, when inspected | D-0063-002 through D-0063-006's Disposition references the corrected file and test. | REQ-007 |
| AC-008 | Given the full gate suite and full pytest suite, when run | both pass clean. | NFR-003 |

## Data & Dependencies

No new data sources. Depends on `0063` (taxonomy/convention/golden-case IDs
cited by every fix and test) and the existing `0023`/`0028` runtimes being
corrected in place — both already implemented.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The day-count correction (`/252` → `/360`) changes a live consumer's expected fee output silently. | A downstream report or backtest's financing numbers shift without explanation. | The change is disclosed in this spec, `gap_register.md`'s updated disposition, and the module docstring/comment at the constant's definition; both affected tests assert the new, golden-case-grounded value explicitly rather than the old one being silently dropped. |
| RISK-002 | Tightening the PIT boundary (`period_end` → `period_start`) flags financing legs a caller previously considered clean. | A caller's existing data trips a new finding where it didn't before. | This is the intended correction (closing a real look-ahead gap, per `golden.temporal.asof_excludes_later_known_rate`); the finding message states plainly why, and `check_point_in_time`'s docstring explains the boundary change. |
| RISK-003 | Removing the counterparty-constraint claim reads as a regression rather than a correction. | A reader assumes counterparty risk is no longer covered. | Docstring and gap-register update both state explicitly that `SecLendingRiskAgent` (unchanged, already tested) remains the actual enforcement point — nothing about counterparty risk coverage regresses, only a false claim in a different agent is removed. |

## Assumptions & Open Questions

- Assumption: `period_start` is the correct point-in-time anchor for a
  financing leg's rate (the golden case's "as_of" equivalent), since the
  rate is applied to the whole period starting there — confirmed by
  `golden.temporal.asof_excludes_later_known_rate`'s own invariant.
- Assumption: the "honest fix" for D-0063-004 (state the boundary rather
  than fabricate per-counterparty demand data) is correct given the current
  SQL data model; if a future spec adds real per-security×counterparty
  demand ingestion, a genuine LP reformulation becomes possible and this
  decision should be revisited.
- Open question: none carried forward from this slice; `0063`'s five
  original Draft Decisions were resolved separately (see
  `knowledge/short_term_markets/README.md`).

## Exceptions

None.
