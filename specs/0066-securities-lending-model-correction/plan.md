# Plan: Securities-Lending Model Correction & Expansion

- **Spec:** 0066-securities-lending-model-correction (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-09-09

## Approach

Correct five gap-register discrepancies in place, in the same two runtime
modules the gap register already names (`sec_lending.py`,
`financing_cost_analysis.py`), with additive/default-preserving parameters
so every existing caller using defaults is unaffected except by the two
deliberate value corrections (day-count, PIT boundary). Ground every fix
and its test in an existing `0063` `golden.*` record rather than asserting
a new, unreviewed number.

## Architecture & Components

```text
knowledge/short_term_markets/gap_register.md (0063, already written)
  D-0063-002 --> sec_lending.py: _classify() thresholds now configurable
  D-0063-003 --> sec_lending.py: /252 -> /360, grounded in
                 golden.seclend.fee_rebate_signs
  D-0063-004 --> sec_lending.py: InventoryOptimizationAgent docstring +
                 OptimizedAllocation.counterparty corrected to state no
                 counterparty dimension exists; SecLendingRiskAgent
                 (unchanged) remains the real enforcement point
  D-0063-005 --> financing_cost_analysis.py: check_point_in_time boundary
                 period_end -> period_start, grounded in
                 golden.temporal.asof_excludes_later_known_rate
  D-0063-006 --> financing_cost_analysis.py: FinancingLeg.day_count_basis
                 explicit field, defaulting to the prior global constant
  D-0063-001 (doc slice) --> agents/securities_financing/securities_lending/
                 instructions.md cites concept.repo_special /
                 concept.stock_loan_special
```

No new module, no new agent. Every change is a targeted correction inside
an already-implemented, already-tested runtime.

## Interfaces & Data Contracts

Two additive, default-preserving API changes:

- `SecLendingUniverseAgent.__init__(..., gc_threshold_bps: float = 50.0,
  warm_threshold_bps: float = 200.0)`.
- `FinancingLeg(..., day_count_basis: float = 360.0)`.

`OptimizedAllocation.counterparty` changes type from `str` (always a
placeholder) to `Optional[str] = None` (always `None`, honestly) — a
narrowing correction, not a widening one; no caller was relying on the
placeholder string's content since it was never anything but
`"BEST_AVAILABLE"`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Every fixed value traces to a `0063` `golden.*` record's exact expected output, verified by a new test before the fix was considered complete. |
| P10 Honest reporting | yes | D-0063-004's fix removes a false claim rather than fabricating data to satisfy it; `gap_register.md`'s disposition is updated to say exactly what changed and what didn't. |
| P5 Reversibility | yes | Two runtime files touched, both with full test coverage before and after; revert is a single commit revert. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `SecLendingUniverseAgent.__init__`, `_classify()` | T-001 |
| REQ-002 | `sec_lending.py` `_DAY_COUNT_BASIS`, fee calc sites | T-002 |
| REQ-003 | `InventoryOptimizationAgent` docstring, `OptimizedAllocation.counterparty` | T-003 |
| REQ-004 | `financing_cost_analysis.py` `check_point_in_time` | T-004 |
| REQ-005 | `FinancingLeg.day_count_basis`, `_leg_cost` | T-005 |
| REQ-006 | `securities_lending/instructions.md` | T-006 |
| REQ-007 | `gap_register.md` | T-007 |
| NFR-001, NFR-002 | New/updated tests in both test files | T-008 |
| NFR-003 | Validation gates | T-009 |
| NFR-004 | Docstring/comment corrections (T-003) | T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| D-0063-004 fix scope | "Honest fix": remove the false claim, no data model change | Full LP reformulation with a fabricated per-security×counterparty demand matrix | The SQL schema has no real per-security×counterparty demand; inventing one to feed a "real" constraint would itself be a fabrication `0063`'s own standard rules out. Reviewer's explicit decision. |
| Thresholds mechanism | Constructor params on `SecLendingUniverseAgent`, defaulting to prior values | A separate `ClassificationPolicy` dataclass | Matches the existing pattern every other agent in the file already uses (`squeeze_util_threshold`, `max_cp_concentration`, etc. are all constructor params); no new abstraction needed for two numbers. |
| Day-count fix scope | Change the two hardcoded `/252` sites to a named `_DAY_COUNT_BASIS = 360.0` constant | Thread a day-count parameter through every call site | `sec_lending.py`'s fee calc, unlike `financing_cost_analysis.py`'s per-leg model, has one fee concept per security with no per-leg-kind variation to parameterize; a single named module constant (mirroring `financing_cost_analysis.py`'s own pattern before this spec) is the right-sized fix. |
| PIT boundary | `rate_asof > period_start` | `rate_asof > period_start - grace_period` (a configurable grace window) | No grace-period concept exists anywhere else in this codebase's PIT discipline (`instructions/point_in_time.md`); adding one here would be a new, unreviewed policy knob. The strict boundary matches `golden.temporal.asof_excludes_later_known_rate`'s own "on or before" rule exactly. |

## Validation Strategy

`PYTHONPATH=src pytest -q tests/test_sec_lending_workflow.py
tests/test_financing_cost_analysis.py tests/test_short_term_markets_knowledge.py`
first (fast, targeted), then the full `PYTHONPATH=src pytest -q` suite, then
`hooks/stages/run-stage.sh spec docs-link spec-index doc-counts handoff-sync
agent-catalog source-catalog secret-scan`, then `git diff --check`. AC-001
through AC-005 are each covered by a specific new/updated test named in
`tasks.md`'s Test Coverage Map. AC-006/AC-007 are covered by direct
inspection. AC-008 is covered by the gate/suite run itself.

## Rollout, Observability & Rollback

Branch `spec0066-securities-lending-model-correction`, commit only (push/PR
only if asked). Rollback is reverting the single commit — both corrected
runtimes have full test coverage on both sides of the change, so a revert
returns to a known-passing prior state. No new gate, no new dependency.

## Open Questions

None carried forward from this slice.
