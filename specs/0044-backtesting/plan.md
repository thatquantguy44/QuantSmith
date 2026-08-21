# Plan: Backtest Engine

- **Spec:** 0044-backtesting (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-12

## Approach

One new module, `src/quantsmith/pipelines/backtesting.py`, standard
library only. It consumes a weight path and a return path and produces
per-period and summary results plus a rendered report. No existing module
is modified; `0007`/`0041` produce the weights, `0012` owns execution
realism, `0028` owns richer financing.

## Architecture & Components

```text
backtesting.py
  BacktestConfig   -- transaction_cost_bps, borrow_cost_bps_annual,
                      periods_per_year, rebalance_lag (>=1, enforced)

  PeriodResult     -- period, gross_return, transaction_cost,
                      financing_cost, net_return, turnover,
                      long_exposure, short_exposure, gross_exposure,
                      net_exposure, benchmark_return, active_return

  BacktestResult   -- config, periods, equity_curve
                      .net_returns / .total_return / .annualized_return
                      .annualized_volatility / .sharpe / .max_drawdown
                      .average_turnover / .hit_rate
                      .probabilistic_sharpe / .active_return

  run_backtest(weights, returns, config, benchmark=None) -> BacktestResult
      if config.rebalance_lag < 1: raise ValueError   # AC-002
      prev = zeros
      for i, w in enumerate(weights):
          j = i + config.rebalance_lag
          if j >= len(returns): break
          # w can only ever meet returns[j], j > i -- look-ahead is an
          # indexing impossibility, not a check (REQ-001)
          gross     = dot(w, returns[j])
          turnover  = sum(|w_k - prev_k|)
          tc        = turnover * transaction_cost_bps / 10_000
          short_exp = sum(-w_k for w_k < 0)
          fin       = short_exp * borrow_bps_annual / 10_000 / periods_per_year
          net       = gross - tc - fin                # exact (REQ-002)
          prev = w
      equity curve compounds (1 + net)

  probabilistic_sharpe_ratio(returns, benchmark_sharpe=0.0) -> float
      # Bailey & Lopez de Prado: probability the true Sharpe exceeds
      # benchmark_sharpe, given sample length, skew and kurtosis.
      #   PSR = Phi( (SR - SR*) * sqrt(n - 1)
      #              / sqrt(1 - skew*SR + ((kurt - 1)/4) * SR^2) )
      # SR here is per-period (not annualized); Phi via math.erf.

  render_backtest_report(result, strategy, owner, universe, period,
                         data_notes, spec_id, last_updated) -> str
      # templates/docs/backtest_report.md's sections, populated from real
      # results; states the cost model, the no-look-ahead guarantee AND
      # its limit (RISK-003), PSR alongside Sharpe, and turnover/capacity.
```

## Interfaces & Data Contracts

Weights are `Sequence[Sequence[float]]` (period-major) and returns the
same shape, matching the `Vector`/`Matrix` convention used across
`pipelines/`. No new persisted schema. The rendered report's shape is
`templates/docs/backtest_report.md`, which `backtest-check.sh` validates.

Shaped for the follow-on FRED slice: a weight path derived from
`gold_fred_point_in_time` (whose `realtime_start` / `realtime_end` give
true vintages) drops straight in, because the engine asks only for
aligned weights and returns.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | No look-ahead is an indexing property of the loop (`j = i + lag`, `lag >= 1`), not an assertion that could be removed. Net return is computed as gross minus costs, so it cannot disagree with its parts. |
| P10 Honest reporting | yes | Net-of-cost is the default and gross is never reported alone; PSR ships with every Sharpe; RISK-003's limit — that the engine cannot vouch for the provenance of the weights it is handed — is stated in the docstring and the report. |
| P5 Reversibility | yes | Additive: one module, one example artifact, doc wiring. |
| P8 No silent trade-offs | yes | RISK-001–RISK-004 name the linear-cost simplification, the overfitting failure mode, the provenance limit, and the deferred numpy decision. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `j = i + rebalance_lag`; lag validation | T-001 |
| REQ-002 | `net = gross - tc - fin` | T-001 |
| REQ-003 | Turnover-scaled cost; short-only financing | T-001 |
| REQ-004 | `BacktestResult` metric properties | T-001 |
| REQ-005 | `probabilistic_sharpe_ratio` | T-001 |
| REQ-006 | Optional benchmark, active return | T-001 |
| REQ-007 | `render_backtest_report` | T-001 |
| REQ-008 | Generated example report | T-003 |
| REQ-009 | Three catalogs | T-004 |
| NFR-001 – NFR-002 | Pure functions; `math` only | T-001 |
| NFR-003 | Gate-theme test | T-002 |
| NFR-004 | Validation gates | T-005 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Look-ahead protection | Structural via `j = i + lag`, `lag >= 1` | A post-hoc assertion that weights precede returns | An assertion can be disabled or drift; an index offset cannot be satisfied any other way. This is the single property a backtest engine most needs to get right. |
| Cost model | Linear in turnover plus short financing | A market-impact model (square-root law) | Impact belongs to `0012`, which already owns execution scheduling; duplicating a worse copy here would let two modules disagree. The simplification is disclosed (RISK-001), not hidden. |
| Sharpe reporting | PSR computed on every run | Sharpe alone, PSR optional | A Sharpe without a sample-length and higher-moment correction is the standard way backtests mislead. Making it non-optional is the point of the engine. |
| Dependency | Standard library | Adopt numpy now | The workload this is built for (dozens of FRED series) is well inside stdlib range. Adopting a dependency ahead of a workload that needs it would decide the architectural fork by accident rather than deliberately (RISK-004). |
| Financing rate | Flat annual bps | Compose `0028`'s `financing_cost_analysis` | `0028` needs a per-name borrow classification this slice has no source for; a flat floor is honest and composable later (carried as an open question). |

## Validation Strategy

`tests/test_backtesting.py`, one test per acceptance criterion
(AC-001 – AC-010), per the convention since `0007`. AC-001 pins the
no-look-ahead offset by constructing returns where using `returns[i]`
instead of `returns[i+1]` would give a detectably different answer.
AC-009 checks the rendered text against `backtest-check.sh`'s own theme
regexes rather than assuming compatibility, as `0039` and `0042` did.
AC-011 runs the gate itself against the committed example. Then the
documentation gate set plus `backtest`, the full `pytest tests/ -q`, and
`git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit and push. Rollback is reverting the commit;
removing the example report returns the `backtest` gate to dormant. No
existing module changes behaviour.

## Open Questions

- Should the engine consume `0028`'s `financing_cost_analysis` for borrow
  rates once a real short book is simulated? (Carried from `spec.md`.)
