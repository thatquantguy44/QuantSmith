# Risk Management Standard

How QuantSmith reviews and monitors the risk of a signal, model, portfolio, or
strategy — exposure, concentration, drawdown and tail behavior, stress
response, and the limits that keep those risks visible after launch. This is
the standard behind `agents/risk/`.

## Why This Standard

A strong backtest or a strong return tells only half the story. The other half
is the risk that produced it: what exposures are intended versus incidental,
how concentrated the book is, how it behaves in its worst periods, and
whether anyone would actually notice a limit breach before it mattered.
Without a stated standard, a risk review becomes whatever the reviewer
happens to think of that day; this standard makes the review the same shape
every time.

## Coverage — what a risk review must produce

| Area | What to establish |
| --- | --- |
| Exposure | Every material exposure (factor, sector, name, geography, currency), and whether each is intended or incidental. |
| Concentration | Position/name/sector/factor/liquidity concentration, not just aggregate diversification statistics. |
| Drawdown & tail | Drawdown depth, duration, and recovery; explicit left-tail behavior, not just volatility. |
| Stress & scenario | Behavior under historical stress episodes and plausible forward scenarios, including ones the strategy has never lived through. |
| Capacity & liquidity | Turnover, capacity, and how liquidity changes under stress, not just in normal markets. |
| Limits & monitoring | A monitorable metric, a threshold, an owner, and a stated action for every named risk. |

## Rules

1. **Name intended exposures separately from unintended ones.** A factor tilt
   the strategy is designed to take and one that crept in from correlated
   names are different findings, even if they look identical in an exposure
   report.
2. **Averages hide the risk that matters.** Report the left tail explicitly —
   worst-case drawdown, worst-decile outcomes — never just volatility or a
   Sharpe ratio.
3. **Stress against real and plausible scenarios, not just the sample period.**
   A backtest's own history is not a stress test; test against historical
   crises and forward scenarios the sample may not contain.
4. **Concentration is multi-dimensional.** A book can look diversified by name
   and still be concentrated by factor, sector, or liquidity bucket — check
   all four, not just position count.
5. **Liquidity changes under stress.** Capacity and turnover assumptions
   validated in calm markets do not automatically hold in stressed ones;
   state the stressed-liquidity assumption explicitly, not just the calm one.
6. **Every risk gets a monitorable limit, not just a narrative.** A risk
   described in prose with no metric, threshold, owner, and breach action is
   not yet a managed risk — it is an observation waiting to become one
   (constitution P8, no silent trade-offs).
7. **Don't accept a return story without its risk story.** A strategy
   proposed for capital without a risk review is an incomplete proposal, not
   a conservative one.

## Checklist

- [ ] Every material exposure is named and labeled intended or unintended.
- [ ] Concentration is assessed by name, sector, factor, and liquidity.
- [ ] Drawdown depth, duration, and recovery are reported; left-tail behavior
      is explicit, not inferred from volatility.
- [ ] The strategy has been stressed against historical and forward scenarios
      beyond its own backtest sample.
- [ ] Capacity, turnover, and liquidity are assessed under stress, not only
      in calm conditions.
- [ ] Every named risk has a metric, a threshold, an owner, and a breach
      action.

## Runtime & Spec

- Agent: `agents/risk/` — a review role; it interrogates a strategy's risk,
  it does not build the strategy.
- Hands off to: `instructions/monitoring.md` (turning a stated risk limit
  into a live-checked metric) and `instructions/alerting.md` (routing a
  breach once monitored).
- Feeds: `agents/role_operations/governance_readiness_checklist` (a risk
  review is evidence a governance-readiness pass can cite) and
  `agents/deployment_release/` (production-readiness sign-off).
