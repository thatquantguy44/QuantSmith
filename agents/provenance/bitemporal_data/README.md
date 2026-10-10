# Bitemporal Data Agent

## Purpose

The Bitemporal Data Agent keeps facts on two timelines — when they are true in the
world (valid time) and when the firm learned them (knowledge time) — so any
question can be answered as of what was known at a given moment. It handles
economic-data vintages, earnings restatements, corrected vendor prints,
retractions, and index reconstitutions, and it detects look-ahead in backtests.

## Use When

- A series is revised after first release (GDP, payrolls, CPI, fundamentals).
- A vendor corrects or withdraws historical values.
- A backtest must use only what was known at each decision date.
- An audit asks what a report would have shown on a past date.

## Inputs

- Facts: key, value, validity interval, knowledge time, and source (version ref or source id).
- Queries: key, valid time, knowledge time; or a set of used facts and a decision time.

## Outputs

- A `BitemporalStore` populated append-only.
- As-of values and snapshots; revision trails per key and date.
- Look-ahead violations for backtest review.
- Handoffs to `backtest_review`, `lineage_capture`, and `data_quality`.

## Example Requests

- "What did we believe Q3 GDP was on 2026-08-01?"
- "Rebuild the fundamentals panel as known at each month-end."
- "Did this backtest read any restated EPS before it was published?"
- "Show every revision of this price and where each came from."

## Required Review Themes

- Every fact has a source and a knowledge time; nothing is backdated.
- Corrections and retractions append; history is never overwritten.
- Backtests read with `as_of(…, known_at=decision_time)`.
- `lookahead_violations` is empty for every decision.
