# Spec: Funding Ladder Min-Cost Flow

- **ID:** 0035-funding-ladder
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`specs/0013-optimization-solvers/` shipped `min_cost_flow`, a general
min-cost network-flow solver, but nothing has been built on it yet.
`specs/0034-cardinality-constrained-portfolio/` closed the SDK's standing
`P0` gap for the MILP solver by composing it with `0007`'s QP; this spec
does the equivalent for the flow solver: a **funding ladder** — matching a
set of future cash obligations to a set of available funding tenors
(overnight, 1-week, 1-month, 3-month, …), each with its own capacity and
cost, at minimum total funding cost. This is a textbook min-cost-flow
application (a bipartite tenor-to-obligation network) and a genuinely
common treasury/cash-management need distinct from what `0007`/`0034`
already cover (portfolio construction, not funding).

This is deliberately a **general treasury/cash-funding** tool, not a
securities-financing one. Per the explicit direction already recorded in
`docs/handoff.md`, this SDK does not build securities-financing
optimization logic (repo/securities-lending economics) — that domain
routes to an adopter's own models via `agents/optimization/
model_plugin_registration/` (spec `0026`). A funding ladder over
obligation dates and tenor capacities/rates applies broadly (any entity
managing a cash-outflow schedule against available funding lines) and
does not model repo, collateral, or securities-lending mechanics.

## Goals

- Add `src/quantsmith/pipelines/funding_ladder.py`: `FundingTenor`
  (name, tenor length, capacity, rate), `FundingObligation` (name, horizon,
  notional), and `solve_funding_ladder` — builds a `SOURCE → tenor nodes →
  obligation nodes → SINK` network and calls `0013`'s `min_cost_flow`
  directly (no reimplementation).
- A tenor may only fund an obligation it can actually cover: the tenor's
  length must be at least the obligation's horizon (the funding must still
  be outstanding when the obligation is due). This eligibility rule is
  expressed as edge existence in the network, not a separate filter step.
- Every obligation is either fully funded or the result reports
  infeasibility explicitly — never a partially-funded result presented as
  success.
- Report both the per-(tenor, obligation) allocation breakdown and each
  tenor's total utilization, so the result is directly usable, not just a
  total cost number.

## Non-Goals

- No securities-financing modeling (repo, securities lending, collateral/
  haircut mechanics) — that stays agent-contract-only and routes to
  `agents/optimization/model_plugin_registration/` per the standing
  direction; this spec's "funding" is general treasury cash management.
- No rate curve modeling or term-structure interpolation; each tenor's
  rate is supplied directly as an input, not derived.
- No dynamic/rolling multi-period control (deciding *when* to re-observe
  and re-solve the ladder as time passes and rates change) — this is a
  single, static allocation decision given a snapshot of tenors and
  obligations, matching `0034`'s own single-decision scope.
- No cross-tenor concentration or counterparty-aggregation limits beyond
  each tenor's own stated capacity — a tenor here already represents one
  funding line/counterparty's aggregate capacity.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `solve_funding_ladder` shall build a bipartite `SOURCE → tenor → obligation → SINK` network and solve it via `min_cost_flow`, with a tenor-to-obligation edge existing only when the tenor's length covers the obligation's horizon. | must |
| REQ-002 | Every obligation shall be fully funded (total inbound allocation equals its notional) when a feasible solution exists. | must |
| REQ-003 | The solution shall minimize total funding cost (rate × horizon carry cost, summed across all allocations). | must |
| REQ-004 | The result shall report the per-(tenor, obligation) allocation breakdown and each tenor's total utilization. | must |
| REQ-005 | The system shall report infeasibility explicitly (a stated status) rather than a partial or silently wrong result when total eligible capacity cannot fund all obligations. | must |
| REQ-006 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same tenors and obligations always return the same allocation and cost. |
| NFR-002 | Composition, not reimplementation | No new flow-solving logic; the module only builds the network and calls `min_cost_flow`. |
| NFR-003 | Dependency isolation | Standard-library only, consistent with `0007`/`0013`/`0034`. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a feasible ladder, when solved, then every obligation's total inbound allocation equals its notional exactly. | REQ-002 |
| AC-002 | Given a tenor shorter than an obligation's horizon, when solved, then no allocation is made from that tenor to that obligation. | REQ-001 |
| AC-003 | Given a tenor's capacity, when solved, then that tenor's total utilization across all obligations never exceeds its capacity. | REQ-001 |
| AC-004 | Given two eligible tenors for the same obligation with different rates, when solved, then the cheaper eligible tenor is preferred (used to capacity) before the more expensive one is drawn. | REQ-003 |
| AC-005 | Given a per-(tenor, obligation) result, when inspected, then it reports both the allocation breakdown and each tenor's total utilization. | REQ-004 |
| AC-006 | Given a ladder where total eligible capacity cannot cover all obligations, when solved, then the status is `"infeasible"` — no partial allocation presented as a full solution. | REQ-005 |
| AC-007 | Given the same tenors and obligations, when solved twice, then the allocation and total cost are identical both times. | NFR-001 |
| AC-008 | Given `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md`, when inspected, then each lists spec `0035` and `funding_ladder.py`. | REQ-006 |

## Data & Dependencies

No data dependencies. Standard-library only; imports `min_cost_flow` from
`optimization_solvers.py` (`0013`) directly — no new dependency, no
modification to that module.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A caller mistakes this for a securities-financing tool (repo/collateral economics) given the domain adjacency. | Scope creep expectation; a user asks it to model something it was deliberately never built to model. | Stated explicitly and repeatedly (Problem & Context, Non-Goals) as general treasury/cash funding, not securities financing; the module docstring restates the boundary. |
| RISK-002 | The static, single-snapshot scope (no rolling re-solve as time/rates change) is mistaken for a full treasury management system. | A user expects the tool to handle rate changes or re-optimization over time on its own. | Stated as a Non-Goal; the function signature itself only accepts one snapshot of tenors/obligations, making the scope structurally visible, not just documented. |
| RISK-003 | An infeasible ladder (insufficient eligible capacity) is misread as "no funding available at all" rather than "not enough eligible capacity for this specific obligation mix." | A user doesn't know which obligation or tenor to address to restore feasibility. | AC-006's infeasibility report is a stated status on the whole solve; a follow-up (not in this slice) could add per-obligation infeasibility diagnostics if a concrete workflow needs finer-grained feedback — noted as an open question rather than silently assumed unnecessary. |

## Assumptions & Open Questions

- Assumption: a static, single-snapshot ladder (not a rolling, time-
  stepped simulation) is the right first scope, matching `0034`'s own
  single-decision precedent on the same toolkit.
- Assumption: cost as `rate × horizon` (a linear carry cost) is a
  sufficient first model of funding cost; day-count conventions and
  compounding are deliberately left as caller-supplied inputs (bake them
  into the rate/horizon units before calling) rather than modeled
  internally.
- Open question: would per-obligation infeasibility diagnostics (which
  specific obligation(s) can't be funded, not just an aggregate
  infeasible status) be worth adding once a concrete workflow needs
  finer-grained feedback than AC-006 provides?

## Exceptions

None.
