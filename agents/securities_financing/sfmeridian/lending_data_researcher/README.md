# Lending Data Researcher Agent

## Purpose

The Lending Data Researcher establishes what a securities-lending dataset is,
what can be trusted, what remains uncertain, and which executable check to
run next. It researches one dataset — loan book, lendable inventory, borrow
rates, collateral, recalls, or program revenue — in the adopter's database or
a delivered file, and hands back a reproducible bundle of evidence-linked
findings and recommendations. It incorporates the Dataset Intake Investigator
proof of concept and its adaptive EDA design (spec `0121`).

## Use When

- A new lending feed or table is onboarded and needs to be trusted before use.
- A desk, monitor, or backtest is about to depend on borrow rates, utilization,
  collateral, or revenue data.
- A daily feed looks wrong and needs a scoped, cited diagnosis.

## Inputs

- A dataset declared in the SFMeridian configuration (`datasets[]`).
- A research context: objective, dataset kind, viewpoint, as-of, timezone,
  grain, time column, calendar, segments, column permissions, thresholds,
  optional target, availability columns, reference profile, and budgets.

## Outputs

- A coverage ledger: every analysis family completed, blocked, skipped, or
  stopped at a budget, with the reason.
- Findings with severity, scope, counts, denominators, and evidence IDs.
- Ranked recommendations, each with a rendered read-only diagnostic or a
  question for the data owner, and a verification criterion.
- A run bundle: reports, charts (Vega-Lite), the analysis code and rendered
  SQL used, a rerun command, a dataset-contract proposal, and a manifest.

## Example Requests

- "Research the loan book for revenue attribution as of 2026-10-22."
- "Are these borrow rates point-in-time usable for a short-side backtest?"
- "Check the collateral table against a 102% margin."

## Required Review Themes

- Every number cites evidence and states its denominator and scope.
- Extract results are never stated as population facts.
- Missing context is reported, not invented; budget stops are not coverage.
- Nothing is repaired, deduplicated, imputed, or written.

## Runtime

A tested loop agent (spec `0121`): `python -m sfmeridian research run --config C
--dataset D --context X`, or `sfmeridian.research.policy.run_research`. Manifest:
`plugins/sfmeridian/src/sfmeridian/data/agents/lending_data_researcher.json`.
