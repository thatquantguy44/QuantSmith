# Spec: Walk-Forward Backtest Harness

- **ID:** 0046-walk-forward
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-12

## Problem & Context

Spec `0044`'s backtest engine simulates a single path, and its own
rendered report says so:

> "this report covers a single simulated path … results here are
> in-sample unless that was applied upstream."

That is the first thing a reviewer discounts, and `agents/backtest_review/`
exists to discount it. The pieces to fix it are already built and tested
but have never been composed: `0006`'s `make_folds` produces purged,
embargoed, walk-forward splits, and `0044`'s `run_backtest` measures a
path net of costs. No module references both — verified by search, the
only co-occurrence is a prose mention inside `backtesting.py`'s rendered
report.

The gap matters most for the work queued behind it. The FRED vertical
slice (`0045`) will run over monthly or quarterly macro series, so its
sample is short. One in-sample path over a couple of hundred periods
proves very little; an out-of-sample distribution across folds is the
only form in which that result carries weight.

## Goals

- Add `src/quantsmith/pipelines/walk_forward.py`, composing `0006`'s
  `make_folds` with `0044`'s `run_backtest` and modifying neither.
- Refit per fold: the harness calls a caller-supplied
  `fit_predict(train_periods, test_periods)` once per fold and evaluates
  the returned weights **only on that fold's held-out test periods**.
- Report the **distribution across folds** — per-fold Sharpe and net
  return, their mean and dispersion, the best and worst fold, and the
  fraction of folds that were positive — rather than a single number.
- Pool the held-out periods into one out-of-sample series and report its
  Sharpe and probabilistic Sharpe, so the aggregate is judged on
  out-of-sample data only.
- Render a report that satisfies `hooks/stages/backtest-check.sh` and
  states its out-of-sample construction explicitly, and ship a generated
  example.

## Non-Goals

- **No new fold logic.** Purge, embargo, and ordering are `0006`'s
  `make_folds`; this composes it rather than reimplementing, for the same
  reason `0042` borrowed `0011`'s toposort.
- **No new simulation logic.** Per-fold measurement is `0044`'s
  `run_backtest` unchanged.
- **No strategy.** `fit_predict` is supplied by the caller.
- **No hyperparameter search or model selection across folds.** Choosing
  a variant using fold results is itself a multiple-testing problem; a
  deflated Sharpe ratio is the natural follow-up and is deliberately not
  bundled here.
- **No claim that walk-forward proves generalisation.** It removes one
  specific failure (evaluating on data the model was fit on), not all of
  them.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `walk_forward_backtest` shall obtain folds from `0006`'s `make_folds` with caller-supplied `n_folds`, `horizon`, and `embargo`, and shall not implement its own splitting. | must |
| REQ-002 | For each fold, the harness shall call `fit_predict(train_periods, test_periods)` exactly once and evaluate the returned weights on that fold's test periods only, via `0044`'s `run_backtest`. | must |
| REQ-003 | Weight-to-return alignment within a fold shall preserve the engine's rebalance lag, so a fold's first weight still meets a return `rebalance_lag` periods later. | must |
| REQ-004 | The result shall expose per-fold Sharpe and net return, their mean and standard deviation, the best and worst fold, and the fraction of folds with a positive net return. | must |
| REQ-005 | The result shall expose a pooled out-of-sample return series built only from held-out periods, with its Sharpe and probabilistic Sharpe. | must |
| REQ-006 | `fit_predict` returning the wrong number of weight rows for a fold shall raise a clear error naming the fold. | must |
| REQ-007 | `render_walk_forward_report` shall emit a report satisfying `backtest-check.sh`'s themes, presenting the fold distribution rather than a single figure. | must |
| REQ-008 | A generated example report shall be committed and shall pass the `backtest` gate. | must |
| REQ-009 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same returns, `fit_predict`, and config always produce identical results and text. |
| NFR-002 | Dependency isolation | Standard library only; imports `return_forecasting` and `backtesting`. |
| NFR-003 | Gate compatibility | The rendered report satisfies `backtest-check.sh`'s themes — verified in tests. |
| NFR-004 | Repository hygiene | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`, `backtest` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a return path, when the harness runs, then its folds equal `make_folds` called with the same arguments — no independent splitting. | REQ-001 |
| AC-002 | Given a recording `fit_predict`, when the harness runs, then it is called once per fold, and every `train_periods` it receives is disjoint from that fold's `test_periods`. | REQ-002 |
| AC-003 | Given a `fit_predict` that returns a marker weight, when a fold is evaluated, then the fold's gross return uses the test-period return offset by `rebalance_lag`, not the test period's own return. | REQ-003 |
| AC-004 | Given several folds, when the run completes, then per-fold Sharpe and net return, their mean and dispersion, best and worst fold, and the positive fraction are all reported. | REQ-004 |
| AC-005 | Given the completed run, when the pooled series is inspected, then its length equals the total evaluated test periods across folds, and its Sharpe and probabilistic Sharpe are reported. | REQ-005 |
| AC-006 | Given a `fit_predict` returning too few rows, when the harness runs, then it raises `ValueError` naming the fold. | REQ-006 |
| AC-007 | Given a completed run, when the report is rendered, then it satisfies `backtest-check.sh`'s themes and shows the fold table. | REQ-007, NFR-003 |
| AC-008 | Given the same inputs, when run twice, then results and rendered text are identical. | NFR-001 |
| AC-009 | Given too few periods to form folds, when the harness runs, then it raises a clear error rather than returning an empty result. | REQ-001 |
| AC-010 | Given the committed example, when `run-stage.sh backtest` runs, then it reports no findings. | REQ-008 |
| AC-011 | Given the three catalogs, when inspected, then each lists spec `0046` and `walk_forward.py`. | REQ-009 |

## Data & Dependencies

No data dependencies. Standard library, plus `return_forecasting`
(`0006`) and `backtesting` (`0044`) from this package.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The harness hands `fit_predict` only index ranges; it cannot stop that callable from closing over global data and peeking at test periods. | A leaky strategy still shows clean out-of-sample numbers. | Stated plainly in the module docstring and the rendered report — the same honest boundary `0044` and `0045` drew. The harness guarantees fold construction, refit-per-fold, and held-out evaluation; provenance inside `fit_predict` stays the caller's responsibility, and the `leakage` gate's. |
| RISK-002 | Few folds over a short sample produce a fold-level dispersion that is itself noisy, inviting over-reading of a "consistent" result. | False confidence from a small denominator. | The fold count and per-fold period counts are reported alongside every aggregate, and the pooled probabilistic Sharpe corrects for total sample length. |
| RISK-003 | A user selects the best-performing variant using these fold results and reports its Sharpe as out-of-sample. | Multiple testing reintroduced through the back door. | Named as an explicit Non-Goal, and the report states that fold results must not be used for selection without a deflated Sharpe correction. |

## Assumptions & Open Questions

- Assumption: `make_folds`' contiguous, later-in-time test blocks are the
  right walk-forward shape; anchored and rolling variants can be added
  later without changing this interface.
- Assumption: `horizon` passed to `make_folds` should be at least the
  strategy's holding period, so a training label window cannot overlap a
  test period.
- Open question: should a deflated Sharpe ratio (correcting for the
  number of variants tried) ship as the natural sibling of this harness?

## Exceptions

None.
