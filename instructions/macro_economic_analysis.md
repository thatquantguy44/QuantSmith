# Macro Economic Analysis Instructions

## Purpose

Use this instruction set when a workflow needs a macro or economic read —
tracking a release, interpreting policy, classifying the current regime,
translating that regime to cross-asset behavior, stress-testing it forward,
or writing it up as a brief or report. It is the shared standard behind the
`agents/economists/` group. The goal is that a quant or portfolio-management
workflow can start from a grounded, point-in-time-correct macro backdrop
instead of each agent re-deriving (or silently assuming) one.

This group is deliberately **analysis and synthesis, not action**. It does
not design or size a trading strategy (see
`agents/trading_strategies/macro_multi_asset/`) and it does not monitor a
live model's behavior for regime change (see
`agents/monitoring/model_signal_monitoring/`) — a different job from
classifying what the current economic regime actually *is*. It hands both,
and `agents/portfolio_management/`, `risk`, and `research_analyst`, a
grounded macro read to build on.

## Required Inputs

- The indicator, release, policy statement, or question in scope, and the
  as-of date being analyzed.
- Where available, the registered source (`sources/{fred,bls,bea,census,
  eia}.yml`) the data traces to — see `instructions/data_source_catalog.md`.
- For a regime or scenario read: the indicators and policy context already
  established (from `macro_indicator_analyst`/`monetary_policy_analyst`),
  not re-derived from scratch.
- For a report: the cadence (recurring brief vs. periodic outlook) and the
  audience/workflow it feeds.

## Expected Output

- A grounded read (indicator interpretation, policy stance, regime label,
  cross-asset implication, or scenario) that traces to a stated source or
  input — never an invented number, quote, or forecast.
- Vintage/point-in-time treatment for any indicator that revises (first
  print vs. later revision), stated explicitly.
- Any gap — a value not yet released, a policy stance not yet stated, a
  question the available data can't answer — flagged plainly, not filled
  with a plausible-sounding guess.
- An explicit handoff to the downstream agent the read is for
  (`macro_multi_asset`, `portfolio_management/*`, `risk`, `backtest_review`,
  or `research_analyst`).

## Standards

- **Grounded, not invented.** Every indicator value, policy statement, or
  quoted figure traces to something actually supplied or to a registered
  `sources/` entry. An unavailable value is a stated gap, per
  `instructions/data_provenance.md`'s real-data-first standard — never
  filled with a plausible number.
- **Point-in-time and vintage-aware.** An indicator's first-print value and
  its later revisions are different facts; state which one is being used
  and why. Never present a revised figure as what was knowable on the
  original release date. See `instructions/point_in_time.md`.
- **Analysis, not action.** State the read; defer the trading, sizing, or
  allocation decision to the agent that owns it. This group's job ends at
  a clear handoff, not a position.
- **Distinguish regime classification from regime-change monitoring.**
  `macro_regime_classifier` answers "what is the current economic regime,"
  a periodic analytical judgment. `agents/monitoring/
  model_signal_monitoring` answers "has a live model's behavior diverged
  from its training regime," a continuous operational check. They inform
  each other; neither replaces the other.
- **State the as-of date on every read.** A macro read is only as current
  as its stated as-of date; an undated read invites being treated as
  live when it may not be.
- **Scenario paths are quantified, not just narrated.** A forward stress
  scenario names the specific indicators and the direction/magnitude of
  their assumed move, not only a prose description of "a downturn."

## Checks

- Does every indicator value, policy statement, or forecast trace to a
  supplied input or a registered `sources/` entry?
- Is vintage explicit wherever an indicator revises (first print vs.
  revision)?
- Is a gap (unreleased data, unstated policy, an unanswerable question)
  flagged plainly rather than filled in?
- Does the output name a downstream handoff rather than making the
  trading/allocation call itself?
- If a regime is classified, is it clearly distinguished from a live
  model's regime-change monitoring?
- Is an as-of date stated on every brief or report?
- Are scenario paths quantified (specific indicators, direction,
  magnitude), not just narrated?

## Common Failure Modes

- Stating a plausible-sounding CPI/GDP/NFP figure that wasn't actually
  supplied or sourced, because it "sounds about right."
- Treating a revised indicator value as if it were knowable on the
  original release date (a point-in-time leakage risk for anything
  downstream that backtests on it).
- A regime classification presented with the confidence of a live
  monitoring signal, blurring into `model_signal_monitoring`'s job.
- A macro brief with no as-of date, later read as current weeks after it
  was written.
- A "stress scenario" that's a paragraph of prose with no quantified
  indicator path a downstream risk or backtest process could actually
  apply.
- Recommending a specific trade or allocation size instead of handing the
  read to `macro_multi_asset`/`portfolio_management/*`.

## Spec-Driven Alignment

This standard backs the `agents/economists/` group (spec
`0033-economists-agents`) across Planning and Testing. "Traces to a
supplied input or `sources/` entry" and "vintage stated explicitly" become
testable `AC-*`/`NFR-*`; a fabricated figure or an undated brief is a
`RISK-*`. Point-in-time handling is enforced by
`instructions/point_in_time.md`; grounding is enforced by
`instructions/data_provenance.md`. The group feeds
`agents/trading_strategies/macro_multi_asset`,
`agents/portfolio_management/*`, `risk`, `backtest_review`, and
`research_analyst` — it does not replace them.
