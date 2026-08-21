# Plan: Walk-Forward Backtest Harness

- **Spec:** 0046-walk-forward (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-12

## Approach

One new module, `src/quantsmith/pipelines/walk_forward.py`, importing
`make_folds`/`Fold` from `return_forecasting` (`0006`) and
`BacktestConfig`/`run_backtest`/`probabilistic_sharpe_ratio` from
`backtesting` (`0044`). Both are imported and neither is modified — the
composition-not-reimplementation pattern used since `0034`.

## Architecture & Components

```text
walk_forward.py
  FoldBacktest        -- fold_index, train_periods, test_periods, result (BacktestResult)
  WalkForwardResult   -- config, folds: List[FoldBacktest]
      .fold_sharpes / .fold_net_returns
      .mean_fold_sharpe / .sharpe_dispersion      (stdev across folds)
      .best_fold / .worst_fold
      .positive_fold_fraction
      .pooled_net_returns   -- concatenated held-out periods only
      .pooled_sharpe / .pooled_probabilistic_sharpe
      .evaluated_periods

  walk_forward_backtest(returns, fit_predict, n_folds, horizon, embargo,
                        config, benchmark) -> WalkForwardResult

      periods = range(len(returns))
      folds = make_folds(periods, n_folds, horizon, embargo)   # 0006, verbatim
      if not folds: raise ValueError(...)                       # AC-009

      for k, fold in enumerate(folds):
          w = fit_predict(fold.train_days, fold.test_days)      # once per fold
          verify len(w) == len(fold.test_days) else raise       # AC-006

          # Alignment: within a fold, slice weights and returns so the
          # engine's own lag still applies. Global test period t0 + i is
          # local i; its return lives at local i + lag.
          t0   = fold.test_days[0]
          span = len(fold.test_days)
          lag  = config.rebalance_lag
          fold_returns = returns[t0 : t0 + span + lag]
          result = run_backtest(w, fold_returns, config, benchmark_slice)

      # aggregates computed from the per-fold results and the pooled
      # held-out series -- never from training periods
```

`make_folds` already guarantees the properties this harness relies on: a
test block is contiguous and later in time than its training set, and a
training day survives only if `t_train + horizon < test_start - embargo`.
Reimplementing that here could disagree with `0006`, which is the one
thing a walk-forward harness must not do.

## Interfaces & Data Contracts

`fit_predict(train_periods, test_periods) -> Matrix` is the caller's
seam: it receives index sequences only and returns one weight row per
test period. Everything else reuses `0044`'s types, so a
`WalkForwardResult`'s per-fold entries are ordinary `BacktestResult`
objects with all their existing metrics.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Fold splitting is `0006`'s, per-fold measurement is `0044`'s; evaluation indices come from `fold.test_days`, so a training period cannot enter an out-of-sample aggregate. |
| P10 Honest reporting | yes | The fold distribution is the headline, not a single number; RISK-001's boundary (the harness cannot police what `fit_predict` closes over) is stated in the docstring and the report. |
| P5 Reversibility | yes | Additive; `return_forecasting.py` and `backtesting.py` are imported, never edited. |
| P8 No silent trade-offs | yes | RISK-001–RISK-003 name the provenance limit, small-fold-count noise, and the selection trap. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `make_folds` delegation | T-001 |
| REQ-002 | Per-fold `fit_predict` + held-out evaluation | T-001 |
| REQ-003 | Fold slicing preserving `rebalance_lag` | T-001 |
| REQ-004 | Fold-distribution properties | T-001 |
| REQ-005 | Pooled out-of-sample series | T-001 |
| REQ-006 | Weight-count validation | T-001 |
| REQ-007 | `render_walk_forward_report` | T-001 |
| REQ-008 | Generated example report | T-003 |
| REQ-009 | Three catalogs | T-004 |
| NFR-001 – NFR-002 | Pure functions; stdlib + two local imports | T-001 |
| NFR-003 | Gate-theme test | T-002 |
| NFR-004 | Validation gates | T-005 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Fold construction | Delegate to `0006`'s `make_folds` | Implement walk-forward splitting here | A second implementation could disagree with `0006` about what is purged — the one thing this harness exists to get right. Same reasoning as `0042` borrowing `0011`'s toposort. |
| Strategy interface | A `fit_predict(train, test)` callable invoked per fold | Accept a pre-computed full weight path and slice it | A pre-computed path is fit once over everything, so slicing it measures out-of-sample *periods* while the model still saw them. Refit-per-fold is the property that makes the result out-of-sample at all. |
| Headline metric | The fold distribution, with pooled metrics secondary | A single pooled Sharpe | A single number hides whether the result came from one lucky fold. Dispersion and the positive-fold fraction are what a reviewer actually asks for. |
| Model selection | Explicitly out of scope | Pick the best variant across folds | Selecting on fold results reintroduces multiple testing; the honest completion is a deflated Sharpe, deliberately left as a follow-up rather than half-built here. |

## Validation Strategy

`tests/test_walk_forward.py`, one test per acceptance criterion
(AC-001 – AC-009). AC-001 asserts the harness's folds equal a direct
`make_folds` call — the delegation is pinned, not assumed. AC-002 uses a
recording `fit_predict` to prove train and test indices are disjoint per
fold. AC-003 is the alignment test: a marker weight shows the fold's
gross return uses the lagged return, not the test period's own. AC-007
checks the rendered text against `backtest-check.sh`'s theme regexes, as
`0039`, `0042`, and `0044` did. Then the documentation gate set plus
`backtest`, the full `pytest tests/ -q`, and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit and push. Rollback is reverting the commit;
removing the example report leaves `0044`'s example still satisfying the
`backtest` gate. No existing module changes behaviour.

## Open Questions

- Should a deflated Sharpe ratio ship as the natural sibling of this
  harness? (Carried from `spec.md`.)
