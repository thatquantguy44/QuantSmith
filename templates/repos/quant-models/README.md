# Shape: quant-models

**For:** model development that will size real positions. The backtest is the
governed artifact.

**Not for:** exploration. Iterate in a `quant-research` repo and graduate here.

## Structure

```text
models/       one dir per model, each with a model_card.md
backtests/    one dir per run, each with a backtest_report.md
src/models/   the implementations
config/       declared constraints, limits, universes
sources/      per-source registry
specs/        every model traces to one
```

## Why these gates

`backtest`, `leakage`, and `repro` **block**, alongside the spec chain.

A look-ahead bug in a research repo is a bad report. Here it is a bad trade.
`repro` blocks for the same reason: a result nobody can reproduce is not a
result, and "it worked on my machine last quarter" is not a defence to a risk
committee.

`monitoring-coverage` is advisory only because monitoring usually lives in the
deployment repo, not this one. If you deploy from here, promote it.
