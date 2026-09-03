# Quant Factory Agent

## Purpose

The Quant Factory Agent orchestrates **parallel model-development lanes**,
evaluates them at a shared convergence gate, and proposes a decision —
which lane(s) to approve, which to reject, and why. It applies the same
discipline to model selection that `0044-backtesting` applies to
individual backtests and `0009-experimentation` applies to A/B test
design: the gate decides, not recency bias.

## Use When

- More than one model hypothesis is under active development and must be
  compared on equal footing.
- A selection decision must be reproducible from an audit ledger alone.
- An ensemble (all lanes approved) or a race (first lane to pass wins) is
  preferred over manual cherry-picking.
- A new feature set, model architecture, or backtest config must be
  validated against a baseline lane before replacing it.

## Inputs

- A completed `templates/prompts/factory_run_card.md` naming each lane's
  hypothesis, feature set, model tag, and backtest config.
- Gate thresholds: `min_sharpe`, `max_drawdown`, `min_annual_return`, and
  `pass_threshold`.
- Convergence mode: `best_of_n`, `all_required`, or `first_to_pass`.
- `seed` and optional `deadline_seconds`.
- A `LaneResult` for each lane (produced by whatever executor ran the
  lanes — the agent does not run the training itself).

## Outputs

- A `FactoryDecision` struct with `approved_lanes`, per-lane scores and
  statuses, and the overall run decision.
- One JSONL entry appended to the factory ledger.
- A human-readable run summary citing the gate values and the reason for
  each lane's outcome.

## What this agent does NOT do

- It does not train models, load data, or run backtests; those are the
  lane executor's job.
- It does not promote an approved lane to production; that requires a
  separate deployment step.
- It does not pick gate thresholds; those are the analyst's responsibility
  and are recorded verbatim in the ledger.

## Spec

`specs/0061-quant-model-factory/` — `spec.md`, `plan.md`, `tasks.md`.

## Runtime

`src/quantsmith/pipelines/quant_factory.py` — `FactoryRunner`, `score_lane`,
`FactorySpec`, `LaneSpec`, `LaneResult`, `ConvergenceGate`.
