# Spec: Venture Fund and Portfolio Analytics

- **ID:** 0091-venture-fund-and-portfolio-analytics
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-03

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`. The predictive models originally grouped with this spec are split out to reserved `0095` so each can be validated on its own.

## Problem & Context

The portfolio-consulting mission needs fund performance reported honestly and
venture outcome uncertainty shown honestly. Both are easy to get wrong in ways
that look authoritative: an IRR on flows that change sign twice has several
answers; an early-life multiple is not comparable with a mature fund's; a peer
quartile from a thin or mismatched vintage set is noise; marks drift from the
last round without anyone noticing; and a "power-law" simulation gives one
confident number whose value rests entirely on assumed hit rates and tails.
`0083` defined the fund-metric conventions (DPI, RVPI, TVPI, IRR, PME, J-curve)
but nothing computes or checks them, and the model catalog lists fund-outcome
simulation as design only.

## Goals

- Compute multiples, XIRR, the J-curve, and PME exactly and reproducibly, using only information known at the report date.
- Review valuation marks for internal consistency without ever setting or approving one.
- Simulate fund outcomes and reserve policy with seeded, explicit-assumption scenarios that report intervals and compare with a null.
- Give each analysis an agent contract with a hard decision boundary.

## Non-Goals

- No valuation, mark, commitment, follow-on, or reserve decision, and no forecast of a fund's return.
- No predictive company models (survival, emergence, link, anomaly, nowcast): reserved `0095`.
- No real fund, LP, or portfolio data; all flows, indices, marks, and cohorts are synthetic.
- No net-of-fee waterfall, carry, or clawback modelling; flows are supplied on a stated basis.
- No live data adapters.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall compute DPI, RVPI, and TVPI as of a date using only flows (and NAVs) known on that date, using the latest NAV on or before it, refusing a fund with no paid-in capital and warning when the NAV is absent or older than a caller-supplied limit. | must |
| REQ-002 | The SDK shall compute XIRR on Actual/365 with the latest NAV as a terminal inflow, find every root on a rate grid, report all of them, headline the root nearest a guess, and warn when the IRR may not be unique; it shall raise when there is no inflow, no outflow, or no root. | must |
| REQ-003 | The SDK shall produce the J-curve cash profile (running net of distributions less contributions, trough, breakeven date or none) and a report-date series in which each row uses only information known at that date. | must |
| REQ-004 | The SDK shall compute Kaplan-Schoar PME from caller-supplied index levels, using the last index level on or before each flow date, and shall refuse an index that starts after the first flow or has a non-positive level. | must |
| REQ-005 | The SDK shall compute a peer percentile rank and quartile among peers of the same vintage supplied by the caller and shall refuse fewer than ten vintage-matched peers. | must |
| REQ-006 | The SDK shall review valuation marks and return flags with their numbers for a missing basis, a stale mark, a mark-up without a new round, a mark predating the latest round, a down round not reflected, and a price deviating from the last round, using thresholds supplied by the caller, and shall never set, approve, or propose a mark. | must |
| REQ-007 | The SDK shall simulate the gross fund multiple with equal checks and heavy-tailed company outcomes, seeded and deterministic, reporting the mean with its Monte Carlo standard error, the 5th/25th/50th/75th/95th percentiles, the probability below 1x, the top company's share of proceeds, and an assumption ledger, plus tail-parameter sensitivity. | must |
| REQ-008 | The SDK shall bootstrap fund multiples from a supplied company cohort, report the share of trials below the equal-outcome null, and warn when the cohort has fewer than 30 companies. | must |
| REQ-009 | The SDK shall simulate follow-on reserve policy under explicit selection assumptions (hit rate, false-positive rate, breakout multiple, dilution), compare reserve fractions on identical simulated outcomes, and state that the result depends on those assumptions. | must |
| REQ-010 | The SDK shall record the XIRR, peer-percentile, and mark-flag conventions in `conventions.json`, include the flag registry in the pack validator's review sign-off, and keep the module's flag codes identical to the registry. | must |
| REQ-011 | The SDK shall add the agents `fund_performance_analyst`, `valuation_marks_reviewer`, and `portfolio_reserve_analyst` with four contract files each and a stated boundary, mark them built in the coverage matrix, and update the portfolio-and-fund-review workflow, standard, catalog, group README, dictionary, and agent registry. | must |
| REQ-012 | The SDK shall reserve `0095` for the predictive models, record the split in the roadmap and gap register, and move the next free spec number to `0096`. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Standard library only; the same inputs and seed give identical outputs on every run, and global `random` state is never touched. |
| NFR-002 | Honesty | Simulations are labelled illustrative, gross, and assumption-dependent; no real fund or person appears; results validated on synthetic flows only are stated as such. |
| NFR-003 | Gates | All gates with enforcement on pass and no existing test regresses. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a four-flow synthetic fund, when multiples are computed as of the NAV date, then DPI 0.3, RVPI 1.0, TVPI 1.3; and given earlier dates, later-known flows, no paid-in capital, or a stale NAV, then only known flows count, the fund is refused, or the warning is raised. | REQ-001 |
| AC-002 | Given a 730-day single-flow pair, when XIRR runs, then it equals 10%; given the fund, then NPV at the result is zero; given a leap-year pair, then Actual/365 is honoured; given no inflow, then it raises; and given flows with roots at 10% and 20%, then both are reported with a warning and the headline follows the guess. | REQ-002 |
| AC-003 | Given the fund, when the cash profile is built, then the running net is -40, -100, -70 with the trough at 2022-01-01 and no breakeven, and a later distribution gives a breakeven date; and the report-date series uses only information known at each date. | REQ-003 |
| AC-004 | Given the fund and an index, when KS-PME runs, then it equals the exact rational computation, equals one when the fund tracks the index, and raises when the index starts late or is non-positive. | REQ-004 |
| AC-005 | Given twenty same-vintage peers, when the percentile is computed, then it is 0.525 for the median-tied value with quartile 2, other-vintage peers are ignored, and fewer than ten peers raises. | REQ-005 |
| AC-006 | Given synthetic holdings, when marks are reviewed, then a clean holding has no flags, each flag fires only on its condition, flags carry their numbers and the decision owner, and no flag proposes a value. | REQ-006 |
| AC-007 | Given fixed parameters and a seed, when the fund is simulated twice, then the results are identical and global random state is unchanged; degenerate cases (all losses, all equal wins) have exact answers; quantiles are ordered; a heavier tail raises the upper quantile; and invalid parameters raise. | REQ-007, NFR-001 |
| AC-008 | Given a cohort, when bootstrapped, then the equal-outcome null equals the cohort mean, a skewed cohort puts most trials below it, a cohort under 30 warns, and an empty or negative cohort raises. | REQ-008 |
| AC-009 | Given reserve parameters, when reserve fractions are compared, then outcomes are common across fractions, no identified companies means no follow-ons, assumptions are returned with the note that they are assumed, and invalid inputs raise. | REQ-009 |
| AC-010 | Given the conventions, when validated, then XIRR, peer-percentile, and six mark flags exist as draft records and the module's codes equal the registry. | REQ-010 |
| AC-011 | Given the coverage matrix, agents, workflow, roadmap, and indexes, when read, then three agents are built with four files and their boundaries, the workflow has no planned agents, `0095` is reserved with no closes, and both indexes name `0096` as next. | REQ-011, REQ-012 |
| AC-012 | Given the source and a repeated run, when inspected, then there is no global seeding, third-party import, or network use and the serialized output is identical. | NFR-001, NFR-002 |
| AC-013 | Given the repository, when gates and the full suite run, then no gate has findings and no previously passing test fails. | NFR-003 |

## Data & Dependencies

Depends on `0083` (fund-metric conventions, bias contracts), `0088` (`known_at`
semantics), `0090` (assumption and tradecraft conventions), `0025` (synthetic data).
Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A stale or optimistic NAV drives a confident multiple. | Overstated performance. | NAV age warning; RVPI described as the manager's mark. |
| RISK-002 | A non-unique IRR is reported as one number. | Misleading return. | All roots reported with a warning. |
| RISK-003 | Early-life metrics compared with mature funds. | Wrong ranking. | J-curve profile; vintage-matched peers only. |
| RISK-004 | A thin or survivorship-biased peer set gives false quartiles. | Spurious benchmark. | Ten-peer minimum, vintage match, stated caveat. |
| RISK-005 | Mark flags read as findings or as approval. | Wrong valuation decision. | Flags carry numbers and the decision owner; no value proposed. |
| RISK-006 | Simulated reserve benefit taken as a forecast. | Misallocated reserves. | Assumption ledger, assumed-not-estimated note, null comparison, intervals. |
| RISK-007 | Tail-dominated results overfit small cohorts. | False precision. | Small-sample warning; sensitivity across alpha; MCSE reported. |

## Assumptions & Open Questions

- Assumption: scenario tools are useful before real data exists because they fix the arithmetic and the guardrails; they are validated on synthetic flows only.
- Open question: which NAV basis (gross or net) and index the adopter's funds will use.
- Open question: how the valuation policy defines stale-mark age and price tolerance (the caller supplies them).

## Exceptions

None.
