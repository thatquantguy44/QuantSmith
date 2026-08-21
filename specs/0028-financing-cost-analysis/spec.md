# Spec: Financing Cost Analysis

- **ID:** 0028-financing-cost-analysis
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`agents/securities_financing/financing_cost_analysis/` is the group's quant
bridge — it promises an all-in cost-of-carry decomposition, financing-aware
returns, a flag when a backtest understates financing cost, financing-spread
sensitivity, and capacity findings from scarce/expensive financing — but,
like `repo_financing/` and `collateral_management/`, it has been
agent-contract-only, with no tested runtime to back those promises. Spec
`0023` promoted `securities_lending/` to a tested runtime; this spec does
the same for `financing_cost_analysis/`, following the group's own stated
workflow (`securities_lending | repo_financing | collateral_management →
financing_cost_analysis → backtest_review + risk`) — the borrow-fee leg
this module computes reconciles directly with `0023`'s classification
(GC/WARM/HTB) and rate vocabulary.

## Goals

- Add `src/quantsmith/pipelines/financing_cost_analysis.py`: a
  dependency-free, deterministic module computing per-position cost-of-carry
  decomposition (borrow fee, rebate, funding, margin), financing-aware
  returns, understated-backtest flags, rate-shock sensitivity, and
  classification-keyed capacity findings.
- Reconcile with `0023`'s securities-lending vocabulary
  (rate_bps/classification) without importing its `numpy`-dependent
  runtime, so this module stays in the dependency-free `pipelines/`
  family.
- Enforce point-in-time discipline: a financing leg whose rate was "known"
  after its position's period ended is flagged as a look-ahead risk.
- Add `tests/test_financing_cost_analysis.py` tracing every acceptance
  criterion, and reference the runtime from the `financing_cost_analysis`
  agent contract (mirroring how `0023` referenced its runtime from
  `securities_lending`).

## Non-Goals

- No promotion of `repo_financing/` or `collateral_management/` in this
  slice; `financing_cost_analysis` accepts financing legs (borrow, funding,
  margin) as structured inputs regardless of which upstream agent or
  system produced them, so it does not require either of those agents to
  have a runtime first.
- No live rate-curve construction or repo/margin data fetching; the module
  operates on rates and dates the caller supplies, the same boundary every
  other `pipelines/` module respects.
- No portfolio-level P&L attribution beyond financing; `backtest_review`
  and `risk` remain the agents that interpret a financing-aware return in
  the context of the full strategy.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall decompose a financed position's all-in cost of carry into borrow-fee, rebate, funding, and margin legs, each computed on an explicit day-count basis. | must |
| REQ-002 | The system shall restate a gross return net of aggregate financing cost, reporting the drag explicitly. | must |
| REQ-003 | The system shall flag when a backtest's reported financing cost understates the computed all-in cost beyond a stated tolerance. | must |
| REQ-004 | The system shall quantify the financing spread's sensitivity to a uniform rate shock by re-decomposing under the shock. | must |
| REQ-005 | The system shall surface capacity findings keyed by borrow classification (GC/WARM/HTB), flagging where requested notional exceeds available. | must |
| REQ-006 | The `financing_cost_analysis` agent contract, the agent catalog, the spec index, and the runtime catalog shall reference the runtime and its reconciliation with `0023`. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Point-in-time | A financing leg whose rate was known after its position's period end is flagged as a look-ahead risk. |
| NFR-002 | Dependency-free | The module imports only the standard library; reconciliation with `0023`'s vocabulary is by plain values, not by importing its `numpy`-dependent runtime. |
| NFR-003 | Determinism | The same inputs produce identical decomposition, sensitivity, and capacity results across runs. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a position with all four leg kinds, when decomposed, then each leg's cost matches a hand-computed ACT/360 calculation and invalid side/notional/leg-kind values are rejected. | REQ-001 |
| AC-002 | Given a gross return and a cost decomposition, when restated, then `net_return = gross_return - financing_cost` and `drag` equals the financing cost. | REQ-002 |
| AC-003 | Given a backtest's reported cost below the computed cost, when checked, then it is flagged; given a reported cost at or above the computed cost, then it is not. | REQ-003 |
| AC-004 | Given a position with borrow-fee and rebate legs, when shocked across a range, then net cost is monotonically increasing in the shock and the borrow leg is clamped at zero, not negative. | REQ-004 |
| AC-005 | Given a mixed book of HTB/GC short positions and an availability cap, when capacity is checked, then the constrained classification is flagged and an uncapped classification is not; a long position never contributes to short-borrow capacity. | REQ-005 |
| AC-006 | Given a leg whose `rate_asof` is after its position's `period_end`, when point-in-time-checked, then it is flagged as look-ahead; a clean position is not. | NFR-001 |
| AC-007 | Given `agents/securities_financing/financing_cost_analysis/{README,instructions}.md`, `agents/README.md`, `specs/README.md`, and `src/quantsmith/pipelines/README.md`, when inspected, then each references the runtime and its reconciliation with `0023`. | REQ-006 |

## Data & Dependencies

No data dependencies. Standard-library only (`dataclasses`, `datetime`,
`typing`), consistent with the `pipelines/` family.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | ACT/360 is not the correct convention for every financing leg an adopter actually uses (some repo markets use ACT/365 or ACT/ACT). | A cost decomposition is systematically mis-scaled for a non-ACT/360 market. | Documented as the module's explicit, single stated convention (matching the money-market convention BLS/BEA/other day-count-sensitive specs in this repo already assume); an adopter needing a different convention adjusts the rate input or requests a parameterized day-count basis as a follow-up. |
| RISK-002 | The rate-shock sensitivity model shifts borrow_fee/funding legs uniformly, which may not reflect how specials (HTB names) actually reprice under a rate move. | Sensitivity understates or overstates real spread risk for hard-to-borrow names. | Documented as a simplification in the module's docstring; a specials-aware sensitivity model is a candidate follow-up once real HTB rate-shock data is available to validate against. |
| RISK-003 | `financing_cost_analysis` accepting financing legs as plain structured input (rather than requiring `repo_financing`/`collateral_management` runtimes) could let a caller supply ungrounded funding/margin rates. | A financing-aware return looks precise but rests on an unreviewed rate assumption. | This module computes what it's given; the `financing_cost_analysis` agent contract's existing Required Review Themes (point-in-time inputs, reconciliation with securities-lending and repo agents) remain the review layer this runtime does not replace. |

## Assumptions & Open Questions

- Assumption: ACT/360 is an acceptable default day-count convention to ship
  with, given it's the standard money-market convention for repo and
  short-term borrow economics.
- Assumption: accepting financing legs as structured input (not requiring
  `repo_financing`/`collateral_management` to have runtimes first) is the
  right way to let this module "close out" the group's quant bridge without
  blocking on the other two agents.
- Open question: does a specials-aware (non-uniform) rate-shock model
  become worth building once real HTB financing data is available to
  ground it?

## Exceptions

None.
