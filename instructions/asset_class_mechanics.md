# Asset Class Mechanics Instructions

## Purpose

Use this instruction set when a workflow touches the market structure, conventions,
or data quirks of a specific asset class — equities, fixed income & credit, FX,
commodities, or digital assets. It is the shared standard behind the
`agents/asset_classes/` group. The goal is that instrument- and market-specific
mechanics (settlement, conventions, corporate actions, roll, sessions, curve
construction) are handled correctly and point-in-time, so the strategy, financing,
and risk agents that build on top inherit accurate inputs instead of silent bugs.

This group is deliberately **mechanics-only**. It does not design or review trading
strategies (see `agents/trading_strategies/`) or price financing (see
`agents/securities_financing/`); it hands both clean, well-understood market
structure and data to build on.

For U.S. short-term rates, Treasury bills, repo/reverse repo, collateral, and
securities-lending mechanics, use the canonical 0063 foundation at
`knowledge/short_term_markets/` and the operating rules in
`instructions/short_term_markets.md` before restating local conventions.

## Required Inputs

- The asset class and instrument type (equity, bond/note, CDS, FX spot/forward,
  futures, perpetual/spot crypto, …).
- The venue(s) and session/settlement conventions in play.
- Any corporate action, curve, roll, or fixing calendar relevant to the instrument.
- The point-in-time snapshot date for any convention, membership, or curve data.

## Expected Output

- A market-structure/mechanics brief for the instrument (venue, session, settlement,
  conventions).
- Point-in-time treatment of anything that revises or is reconstituted (index
  membership, curve nodes, ratings, corporate actions).
- Named data quirks and the adjustment or handling required (e.g. split/dividend
  adjustment, day-count convention, roll date, funding-rate mark).
- Explicit handoff to the strategy, financing, or risk agent that needs the output.

## Standards

- **Mechanics, not strategy.** State market structure and data handling; defer edge,
  sizing, and signal design to `agents/trading_strategies/`.
- **Point-in-time conventions.** Index membership, curve nodes, ratings, and
  corporate-action adjustments are snapshotted as of the decision date — no
  retroactively adjusted data. See `instructions/point_in_time.md`.
- **Name the settlement and session reality.** Settlement lag (T+1/T+2), session
  structure (continuous, auction, 24/7), and fixing windows change what is tradable
  and knowable at decision time.
- **Corporate actions and roll are leakage surfaces.** Splits, dividends, spin-offs,
  and futures/perpetual rolls change price series discontinuously; state the
  adjustment method and its look-ahead risk.
- **Curve and rate construction is explicit.** Where a curve, yield, or funding rate
  is built (bootstrapping, interpolation, funding-rate mark), state the method and
  its point-in-time inputs.
- **Custody, counterparty, and delivery risk are named.** Especially for commodities
  (physical delivery) and digital assets (custody, exchange counterparty risk),
  state where the instrument's risk is not just market risk.

## Checks

- Is the venue, session, and settlement convention stated?
- Is any index membership, curve, rating, or corporate-action data point-in-time?
- Is the adjustment method for corporate actions or rolls named, with its
  look-ahead risk?
- Are fixing windows, funding-rate marks, or curve-construction methods explicit?
- Is custody, counterparty, or delivery risk named where it applies?
- Does the output identify which downstream agent (strategy, financing, risk) it
  hands off to, rather than making strategy or sizing calls itself?

## Common Failure Modes

- Backtesting on split/dividend-unadjusted (or wrongly adjusted) price series.
- Using today's index membership for a historical universe (survivorship leakage).
- Ignoring settlement lag so a signal trades on data not yet settled/knowable.
- Treating futures roll or perpetual funding as a data artifact instead of a real
  cost/leakage surface.
- Assuming continuous, single-venue liquidity for markets that are fragmented,
  24/7, or auction-based.
- Skipping custody/counterparty risk in crypto or physical-delivery risk in
  commodities.

## Spec-Driven Alignment

This standard backs the `agents/asset_classes/` group across Planning and Testing.
Convention and point-in-time treatment become testable `AC-*`/`NFR-*` ("prices are
split/dividend-adjusted with method X", "index membership is point-in-time");
custody, counterparty, delivery, and roll risk become `RISK-*`. Point-in-time
handling is enforced by `instructions/point_in_time.md`. The group feeds
`agents/trading_strategies/`, `agents/securities_financing/`, `data_quality`, and
`risk` — it does not replace them.
