# Repo Financing Instructions

## Operating Rules

- Use `instructions/short_term_markets.md` and `knowledge/short_term_markets/`
  for U.S. repo/reverse-repo roles, rate signs, GC/specific specialness,
  day-count, settlement, haircut, lifecycle, source, and review-status records.
- Net funding cost from returns; do not treat leverage as free.
- Distinguish GC from specials in repo using the repo-rate axis: positive
  specialness is `GC repo rate - specific collateral repo rate`, with cash
  provider/taker viewpoints stated.
- Use point-in-time repo rates and curves; no hindsight funding cost.
- Assess roll risk when overnight repo funds longer-dated positions.
- State haircuts and the collateral posted against the cash.
- Name funding-counterparty exposure and the mitigation (tri-party, haircut).
- Consider funding availability under stress, not just in calm markets.

## Checks

- Is funding cost netted from strategy returns?
- Are GC and specials distinguished in the repo rate?
- Are repo rates point-in-time?
- Is roll risk assessed for the term-vs-overnight mix?
- Are haircuts and posted collateral stated?
- Is counterparty exposure named with its protection?

## Output Contract

Use clear Markdown. Include a `Funding Plan & Rate` section, a `Roll & Term` section,
and a `Counterparty & Haircut` section. State the point-in-time treatment.

## Spec-Driven Role

Funding assumptions become spec criteria: "funding cost netted", "point-in-time
repo rates" become `AC-*`/`NFR-*`; roll and counterparty exposure become `RISK-*`.
Point-in-time rates are enforced by `instructions/point_in_time.md`. See
`instructions/securities_financing.md`, `instructions/short_term_markets.md`, and
`knowledge/short_term_markets/`. Hands off to `financing_cost_analysis`,
`collateral_management`, and `risk`.
