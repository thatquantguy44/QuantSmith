# Spec: Backtest Engine

- **ID:** 0044-backtesting
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-12

## Problem & Context

This SDK governs backtesting thoroughly and has never run one.
`instructions/backtesting.md` is the standard, `agents/backtest_review/`
is the reviewing agent, `templates/docs/backtest_report.md` is the
artifact shape, and `hooks/stages/backtest-check.sh` is **enforced in
CI** — yet running it reports "No backtest report artifact detected",
because nothing in the repository has ever produced a backtest. That is
the same dormant-gate shape closed for data contracts (`0039`) and
pipeline manifests (`0042`), but it sits on the artifact quant research
exists to produce.

The gap is also what keeps every result in this SDK synthetic. `0041`'s
own acceptance criterion had to be labelled a mechanism demonstration on
a constructed fixture rather than a market claim, precisely because there
is no engine to produce a real one.

This spec adds that engine. It is deliberately the first half of a
two-step build: the second is a real vertical slice over point-in-time
FRED data from `joshualutkemuller/fred-bronze-to-gold-pipeline`, whose
`gold.fred_point_in_time` table carries FRED's true `realtime_start` /
`realtime_end` vintage columns. The engine's inputs are shaped so that
slice is a wiring exercise rather than a rewrite.

## Goals

- Add `src/quantsmith/pipelines/backtesting.py`: `run_backtest` over a
  path of target weights and realized returns, producing per-period and
  summary results — gross and net return, transaction cost, financing
  cost, turnover, exposures, drawdown, and Sharpe.
- Make **no look-ahead structural**: weights decided at period `t` are
  applied only to returns at `t + rebalance_lag` with `rebalance_lag >= 1`
  enforced, so a weight vector cannot touch a return at or before its own
  decision index. Not a check that can be forgotten — an indexing
  property of the loop.
- Report **net of costs by default**, never gross alone: transaction cost
  scaled by realized turnover, and financing charged on short exposure,
  so a long/short result cannot quietly omit borrow.
- Compute a **probabilistic Sharpe ratio** (Bailey & López de Prado)
  accounting for sample length, skew, and kurtosis — the honest answer to
  "is this Sharpe distinguishable from zero", and the multiple-testing
  theme `backtest-check.sh` requires.
- Add `render_backtest_report`, emitting a
  `templates/docs/backtest_report.md`-shaped document populated from real
  computed results, and ship a generated example so the CI-enforced
  `backtest` gate validates real content for the first time.

## Non-Goals

- **No signal or strategy logic.** The engine consumes a weight path;
  producing it is `0001`/`0006`/`0041`/`0007`'s job.
- **No data fetching.** Returns and weights are supplied already
  computed, matching `0039`'s boundary. The FRED slice will supply them.
- **No optimiser.** Position sizing is `0007`/`0034`; this measures what
  a given path would have produced.
- **No intraday, no partial fills, no market-impact model.** Execution
  realism beyond a linear turnover cost is `0012`'s
  (`execution_optimization.py`) concern; this slice states the assumption
  rather than modelling it.
- **No numpy.** Standard library only, consistent with every other
  `pipelines/` module. The dependency question raised for real-universe
  scale is deferred, not silently decided: a macro slice over dozens of
  FRED series is well inside stdlib range, and the decision should be
  forced by a workload that needs it.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `run_backtest` shall apply weights decided at period `t` only to returns at `t + rebalance_lag`, and shall reject `rebalance_lag < 1`. | must |
| REQ-002 | Each period's net return shall equal its gross return less transaction and financing costs, exactly. | must |
| REQ-003 | Transaction cost shall scale with realized turnover (the L1 change in weights), and financing cost shall be charged on short exposure only. | must |
| REQ-004 | The result shall report annualized return, volatility, Sharpe, maximum drawdown, average turnover, hit rate, and exposures, all computed from the net path. | must |
| REQ-005 | `probabilistic_sharpe_ratio` shall compute PSR from the observed Sharpe, sample length, skew, and kurtosis of the realized return series. | must |
| REQ-006 | `run_backtest` shall accept an optional benchmark return series and report active return against it. | must |
| REQ-007 | `render_backtest_report` shall emit a `templates/docs/backtest_report.md`-shaped document populated from real results, satisfying `hooks/stages/backtest-check.sh`'s themes. | must |
| REQ-008 | A generated example report shall be committed and shall pass the CI-enforced `backtest` gate. | must |
| REQ-009 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same weights, returns, and config always produce identical results and rendered text. |
| NFR-002 | Dependency isolation | Standard library only (`math` for `erf`/`sqrt`). |
| NFR-003 | Gate compatibility | The rendered report satisfies `backtest-check.sh`'s themes — verified directly in tests. |
| NFR-004 | Repository hygiene | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`, `backtest` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a weight path and returns, when `run_backtest` runs with `rebalance_lag=1`, then period `i`'s gross return uses `returns[i+1]`, never `returns[i]` or earlier. | REQ-001 |
| AC-002 | Given `rebalance_lag=0`, when `run_backtest` runs, then it raises `ValueError` naming the look-ahead risk. | REQ-001 |
| AC-003 | Given any run, when each period is inspected, then `net_return == gross_return - transaction_cost - financing_cost` within tolerance. | REQ-002 |
| AC-004 | Given a constant weight path after the first period, when the backtest runs, then turnover and transaction cost are zero for every unchanged period. | REQ-003 |
| AC-005 | Given a short position and a non-zero borrow rate, when the backtest runs, then financing cost is positive and scales with short exposure; a long-only path is charged nothing. | REQ-003 |
| AC-006 | Given a known return path, when metrics are computed, then max drawdown and the equity curve match a hand-computed expectation. | REQ-004 |
| AC-007 | Given a return series, when `probabilistic_sharpe_ratio` runs, then the result lies in `[0, 1]` and increases with sample length for a fixed Sharpe. | REQ-005 |
| AC-008 | Given a benchmark series, when the backtest runs, then active return equals the strategy's net return less the benchmark's, per period. | REQ-006 |
| AC-009 | Given a completed result, when `render_backtest_report` runs, then the output contains the template's sections and satisfies `backtest-check.sh`'s themes. | REQ-007, NFR-003 |
| AC-010 | Given the same inputs, when run and rendered twice, then results and text are identical. | NFR-001 |
| AC-011 | Given the committed example report, when `run-stage.sh backtest` runs, then it reports the artifact with no findings. | REQ-008 |
| AC-012 | Given the three catalogs, when inspected, then each lists spec `0044` and `backtesting.py`. | REQ-009 |

## Data & Dependencies

No data dependencies in this slice. Standard library only. The follow-on
vertical slice will consume `gold_fred_point_in_time` from the local
SQLite output of `joshualutkemuller/fred-bronze-to-gold-pipeline`, which
requires a `FRED_API_KEY` held by the operator — never by this
repository (P9).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A linear turnover cost understates real-world impact, so net results read as more achievable than they are. | An over-optimistic backtest. | The rendered report states the cost model explicitly as linear-in-turnover and names market impact as unmodelled; `0012` owns impact-aware scheduling. Stated, not silently assumed. |
| RISK-002 | A user reads the Sharpe without the PSR and treats a short, lucky sample as evidence. | The classic backtest overfitting failure. | PSR is computed on every run and rendered in the report's results section, not offered as an optional extra. |
| RISK-003 | The engine cannot detect that the *weights* it was handed were themselves built with look-ahead; it only guarantees its own indexing is clean. | A leaky signal produces a clean-looking backtest. | Stated plainly in the module docstring and the report: the no-look-ahead guarantee covers the simulation loop, not the provenance of the inputs. Upstream leakage is `instructions/point_in_time.md` and the `leakage` gate's concern. |
| RISK-004 | Stdlib-only arithmetic will not scale to a large universe with long history. | The engine is unusable for an equity cross-section. | Explicit Non-Goal; the macro slice this is built for is well inside range, and the dependency decision is deferred to a workload that actually forces it rather than pre-emptively. |

## Assumptions & Open Questions

- Assumption: weights are target portfolio weights per period, and
  returns are simple period returns aligned to the same index.
- Assumption: a linear turnover cost plus a short-financing charge is the
  right cost floor for a first engine; `0028` already owns richer
  financing analysis and can be composed later.
- Open question: should the engine consume `0028`'s
  `financing_cost_analysis` directly for borrow rates rather than a flat
  annual rate, once a real short book is simulated?

## Exceptions

None.
