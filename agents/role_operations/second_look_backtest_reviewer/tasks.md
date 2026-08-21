# Second Look Backtest Reviewer Tasks

## Run A Pre-Check

Input: strategy/model description, data sources, signal logic, portfolio
construction, cost assumptions, performance and risk metrics.

Output: a pass/flag note per Required Review Theme, specific concerns if
any, and a closing recommendation to run `agents/backtest_review/` before
any production-promotion decision.

## Flag A Specific Concern

Input: one aspect of a backtest (e.g. an unusually clean out-of-sample
result, a cost assumption).

Output: a focused note on why it's worth a closer look at full review,
with the same closing recommendation.

## Hand Off To Full Review

Input: a completed pre-check.

Output: a short summary suitable for handing to `agents/backtest_review/`
— what the pre-check found, and what it explicitly did not assess.
