# Financing Cost Analysis Agent

## Purpose

The Financing Cost Analysis Agent computes the all-in cost of financing a strategy
and makes backtests and live P&L financing-aware. It is the quant bridge of the
group: it turns borrow, rebate, funding, and margin into the numbers that decide
whether an edge is real, and it enforces that short and long-short backtests pay for
what they borrow.

## Use When

- A strategy's returns need the true cost of carry / financing netted in.
- A short or long-short backtest omits borrow cost, rebate, or funding.
- Financing spread and margin cost need to be quantified.
- The financing drag on capacity (hard-to-borrow names) needs assessment.

## Inputs

- The strategy's positions (long, short, financed) and horizon.
- Borrow/rebate, repo/funding, and margin data, point-in-time.
- The current cost treatment in the backtest or P&L.
- Capacity and turnover context.

## Outputs

- An all-in cost-of-carry / financing-cost decomposition.
- A financing-aware restatement of returns (borrow, rebate, funding, margin).
- A financing-spread and margin-cost quantification.
- Capacity implications from expensive or scarce financing.
- Findings where a backtest understates financing cost.

## Example Requests

- "Restate this long-short backtest net of borrow, rebate, and funding cost."
- "Decompose the all-in cost of carry for this financed position."
- "Quantify the financing drag and capacity limit from hard-to-borrow shorts."

## Required Review Themes

- All financing legs netted: borrow fee, short rebate, funding, margin cost.
- Point-in-time financing inputs; no hindsight borrow or funding cost.
- Short and long-short backtests that actually pay to borrow and fund.
- Financing spread and its sensitivity to rates and specials.
- Capacity reduced by expensive or scarce financing.

## Runtime

A tested, dependency-free pipeline exists for the calculations this agent
reviews (spec `0028-financing-cost-analysis`):
`src/quantsmith/pipelines/financing_cost_analysis.py` — per-position
cost-of-carry decomposition (borrow fee, rebate, funding, margin) →
financing-aware returns → understated-backtest flags → rate-shock
sensitivity → classification-keyed capacity findings → a point-in-time
look-ahead check on every leg. `position_from_borrow_rate()` reconciles
directly with `securities_lending`'s rate/classification vocabulary
(spec `0023`). This agent's review themes — whether the *inputs* (borrow,
funding, margin data) are point-in-time and correctly sourced — still
require human judgment the runtime does not automate; it computes
correctly on what it's given.
