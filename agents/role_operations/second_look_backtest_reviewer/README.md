# Second Look Backtest Reviewer Agent

## Purpose

The Second Look Backtest Reviewer Agent runs a fast, personal pre-check on
a backtest result against `agents/backtest_review/`'s own Required Review
Themes, so an obvious lookahead, survivorship, or cost-assumption problem
gets caught before a result goes to full review — not instead of it.

**This is a pre-check, not a substitute for `agents/backtest_review/`.**
Every output names the full review as the required next step before any
production promotion decision; this agent never issues a promotion-ready
verdict on its own.

## Use When

- A backtest just finished and a fast sanity pass is wanted before
  bringing it to full review.
- A result looks unusually good and a quick first-pass skeptical read is
  wanted immediately, without waiting for a formal review slot.
- A researcher wants a personal checklist pass while a change is still
  fresh in mind, ahead of asking someone else (or `backtest_review`) to
  look.

## Inputs

- Strategy or model description, universe, rebalance schedule, holding
  period.
- Data sources and point-in-time assumptions.
- Signal generation logic and portfolio construction.
- Cost, slippage, borrow, and market-impact assumptions.
- Performance and risk metrics.

## Outputs

- A fast pre-check against `backtest_review`'s Required Review Themes
  (lookahead/leakage, survivorship, costs, benchmark choice, robustness,
  risk behavior), flagging anything that looks off.
- An explicit recommendation to run the full `agents/backtest_review/`
  agent before any production-promotion decision — stated every time, not
  only when something looks wrong.
- Never a "this is production-ready" verdict; that determination stays
  `backtest_review`'s (and, downstream, `governance_readiness_checklist`'s
  and a human reviewer's).

## Example Requests

- "Give this backtest a quick second look before I send it for full
  review."
- "Does anything jump out as an obvious problem in these assumptions?"
- "I want a fast sanity pass while this is still fresh — full review can
  come later."

## Required Review Themes

Same themes as `agents/backtest_review/`, run at pre-check depth:
lookahead and leakage; survivorship and universe construction; costs,
slippage, borrow, and capacity; benchmark and baseline choice; robustness
across windows/sectors/regimes/parameters; risk, drawdown, turnover, and
exposure behavior.
