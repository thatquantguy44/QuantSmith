"""Reference pipeline for spec 0046 -- walk-forward backtest harness.

Spec ``0044`` simulates a single path, and its own rendered report says so:
"results here are in-sample unless that was applied upstream". That is the
first thing a reviewer discounts. The pieces to fix it were already built and
tested but had never been composed -- ``0006``'s ``make_folds`` produces
purged, embargoed walk-forward splits, and ``0044``'s ``run_backtest`` measures
a path net of costs.

This harness composes them. For each fold it calls a caller-supplied
``fit_predict(train_periods, test_periods)`` **once**, then evaluates the
returned weights on that fold's held-out test periods only. The headline is the
*distribution across folds* -- per-fold Sharpe, its dispersion, the best and
worst fold, and how many folds were positive -- because a single pooled number
hides whether the result came from one lucky stretch.

Neither ``return_forecasting`` nor ``backtesting`` is modified. Fold splitting
in particular is delegated, not reimplemented: a second implementation could
disagree with ``0006`` about what is purged, which is the one thing a
walk-forward harness must not get wrong.

**The limit of the guarantee.** The harness controls fold construction,
refit-per-fold, and held-out evaluation. It hands ``fit_predict`` index
sequences only -- but it cannot stop that callable from closing over global
data and peeking at test periods. A leaky strategy will still show clean
out-of-sample numbers here. That remains ``instructions/point_in_time.md``'s
concern and the ``leakage`` gate's, exactly as in ``0044`` and ``0045``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from .backtesting import (
    BacktestConfig,
    BacktestResult,
    probabilistic_sharpe_ratio,
    run_backtest,
)
from .return_forecasting import Fold, make_folds

Matrix = Sequence[Sequence[float]]
FitPredict = Callable[[Sequence[int], Sequence[int]], Matrix]


@dataclass(frozen=True)
class FoldBacktest:
    fold_index: int
    train_periods: Tuple[int, ...]
    test_periods: Tuple[int, ...]
    result: BacktestResult


@dataclass(frozen=True)
class WalkForwardResult:
    config: BacktestConfig
    folds: List[FoldBacktest] = field(default_factory=list)

    # -- per-fold distribution (the headline) -------------------------------

    @property
    def fold_sharpes(self) -> List[float]:
        return [f.result.sharpe for f in self.folds]

    @property
    def fold_net_returns(self) -> List[float]:
        return [f.result.total_return for f in self.folds]

    @property
    def mean_fold_sharpe(self) -> float:
        return _mean(self.fold_sharpes)

    @property
    def sharpe_dispersion(self) -> float:
        """Standard deviation of Sharpe across folds -- consistency, not level."""
        return _stdev(self.fold_sharpes)

    @property
    def best_fold(self) -> Optional[FoldBacktest]:
        return max(self.folds, key=lambda f: f.result.sharpe) if self.folds else None

    @property
    def worst_fold(self) -> Optional[FoldBacktest]:
        return min(self.folds, key=lambda f: f.result.sharpe) if self.folds else None

    @property
    def positive_fold_fraction(self) -> float:
        if not self.folds:
            return 0.0
        return sum(1 for r in self.fold_net_returns if r > 0) / len(self.folds)

    # -- pooled out-of-sample ----------------------------------------------

    @property
    def pooled_net_returns(self) -> List[float]:
        """Held-out periods only, concatenated in fold order."""
        pooled: List[float] = []
        for f in self.folds:
            pooled.extend(f.result.net_returns)
        return pooled

    @property
    def evaluated_periods(self) -> int:
        return len(self.pooled_net_returns)

    @property
    def pooled_sharpe(self) -> float:
        pooled = self.pooled_net_returns
        sd = _stdev(pooled)
        if sd == 0:
            return 0.0
        return _mean(pooled) / sd * math.sqrt(self.config.periods_per_year)

    @property
    def pooled_probabilistic_sharpe(self) -> float:
        return probabilistic_sharpe_ratio(self.pooled_net_returns)

    @property
    def pooled_total_costs(self) -> float:
        return sum(f.result.total_costs for f in self.folds)

    @property
    def has_shorts(self) -> bool:
        return any(f.result.has_shorts for f in self.folds)

    @property
    def average_turnover(self) -> float:
        return _mean([f.result.average_turnover for f in self.folds])


def walk_forward_backtest(
    returns: Matrix,
    fit_predict: FitPredict,
    n_folds: int = 3,
    horizon: int = 1,
    embargo: int = 1,
    config: Optional[BacktestConfig] = None,
    benchmark: Optional[Sequence[float]] = None,
) -> WalkForwardResult:
    """Refit per fold and evaluate on held-out periods only.

    ``fit_predict(train_periods, test_periods)`` is called once per fold and
    must return one weight row per test period. ``horizon`` is passed to
    ``make_folds`` and should be at least the strategy's holding period, so a
    training label window cannot overlap a test period.
    """
    cfg = config or BacktestConfig()
    n = len(returns)
    folds: List[Fold] = make_folds(
        list(range(n)), n_folds=n_folds, horizon=horizon, embargo=embargo
    )
    if not folds:
        raise ValueError(
            f"cannot form {n_folds} walk-forward fold(s) from {n} period(s) with "
            f"horizon={horizon}, embargo={embargo}: too few periods"
        )

    evaluated: List[FoldBacktest] = []
    for k, fold in enumerate(folds):
        weights = list(fit_predict(fold.train_days, fold.test_days))
        if len(weights) != len(fold.test_days):
            raise ValueError(
                f"fold {k}: fit_predict returned {len(weights)} weight row(s) for "
                f"{len(fold.test_days)} test period(s)"
            )

        # Slice so the engine's own lag still applies inside the fold: local
        # index i is global test period t0 + i, whose return sits at local
        # i + rebalance_lag.
        t0 = fold.test_days[0]
        span = len(fold.test_days)
        stop = min(t0 + span + cfg.rebalance_lag, n)
        fold_returns = list(returns[t0:stop])
        fold_benchmark = list(benchmark[t0:stop]) if benchmark is not None else None

        result = run_backtest(weights, fold_returns, cfg, benchmark=fold_benchmark)
        evaluated.append(
            FoldBacktest(
                fold_index=k,
                train_periods=tuple(fold.train_days),
                test_periods=tuple(fold.test_days),
                result=result,
            )
        )

    return WalkForwardResult(config=cfg, folds=evaluated)


# ---------------------------------------------------------------------------
# Report rendering -- REQ-007
# ---------------------------------------------------------------------------


def render_walk_forward_report(
    result: WalkForwardResult,
    strategy: str,
    owner: str,
    universe: str,
    period: str,
    data_notes: str = "",
    benchmark_name: str = "",
    spec_id: str = "",
    last_updated: str = "",
) -> str:
    """Render an out-of-sample backtest report built around the fold distribution."""
    cfg = result.config
    o: List[str] = []

    o.append(f"# Backtest Report: {strategy} (walk-forward)")
    o.append("")
    o.append("> Generated by `render_walk_forward_report` (spec `0046-walk-forward`).")
    o.append("> Every figure is computed from held-out periods; the model is refit once")
    o.append("> per fold and never evaluated on data it was fit on.")
    if spec_id:
        o.append(">")
        o.append(f"> **Spec:** {spec_id}")
    if last_updated:
        o.append(f"> **Last updated:** {last_updated}")
    o.append("")

    o.append("## Strategy Or Signal")
    o.append("")
    o.append(f"{strategy} — walk-forward over {universe}, {period}.")
    o.append("")

    o.append("## Owner")
    o.append("")
    o.append(f"- **Owner:** {owner}")
    o.append("")

    o.append("## Summary")
    o.append("")
    o.append(
        f"Across {len(result.folds)} out-of-sample fold(s) covering "
        f"{result.evaluated_periods} held-out period(s): mean fold Sharpe "
        f"{result.mean_fold_sharpe:.2f} (dispersion {result.sharpe_dispersion:.2f}), "
        f"{_pct(result.positive_fold_fraction)} of folds positive. Pooled "
        f"out-of-sample Sharpe {result.pooled_sharpe:.2f}, probabilistic Sharpe "
        f"{result.pooled_probabilistic_sharpe:.3f}."
    )
    o.append("")

    o.append("## Simulation Contract")
    o.append("")
    o.append(
        f"- **Out-of-sample construction:** folds come from `make_folds` (spec `0006`) "
        f"— purged and embargoed, each test block contiguous and later in time than "
        f"its training set. `fit_predict` is called once per fold on training periods "
        f"only, and the resulting weights are evaluated on that fold's held-out test "
        f"periods."
    )
    o.append(f"- **Rebalance lag:** {cfg.rebalance_lag} period(s), preserved within each fold.")
    o.append(f"- **Periods per year:** {cfg.periods_per_year}")
    o.append(
        "- **Limit of the guarantee:** the harness controls fold construction, "
        "refit-per-fold, and held-out evaluation. It cannot establish that "
        "`fit_predict` did not close over global data and peek at test periods — "
        "that stays `instructions/point_in_time.md`'s concern and the `leakage` "
        "gate's."
    )
    o.append("")

    o.append("## Data And Point-In-Time Assumptions")
    o.append("")
    o.append(data_notes or "- Returns were supplied already aligned by period.")
    o.append("")

    o.append("## Costs And Execution")
    o.append("")
    o.append(f"- **Transaction cost:** {cfg.transaction_cost_bps:.1f} bps per unit turnover.")
    o.append(
        f"- **Financing / borrow cost:** {cfg.borrow_cost_bps_annual:.1f} bps annual on "
        f"short exposure"
        + ("; this book holds shorts, so borrow is charged." if result.has_shorts else "; long-only, nothing charged.")
    )
    o.append(f"- **Average turnover per period:** {result.average_turnover:.4f}")
    o.append(
        "- **Not modelled:** market impact, partial fills, intraday execution — see "
        "`execution_optimization.py` (spec `0012`)."
    )
    o.append("")

    o.append("## Benchmarks And Baselines")
    o.append("")
    o.append(
        f"- **Benchmark:** {benchmark_name}"
        if benchmark_name
        else "- **Benchmark:** none supplied; a level without a baseline is not an edge."
    )
    o.append("")

    o.append("## Results")
    o.append("")
    o.append("| Fold | Test periods | Sharpe | Net return | Max drawdown |")
    o.append("| --- | --- | --- | --- | --- |")
    for f in result.folds:
        o.append(
            f"| {f.fold_index} | {len(f.test_periods)} | {f.result.sharpe:.2f} | "
            f"{_pct(f.result.total_return)} | {_pct(f.result.max_drawdown)} |"
        )
    o.append("")
    o.append("| Aggregate | Value |")
    o.append("| --- | --- |")
    o.append(f"| Mean fold Sharpe | {result.mean_fold_sharpe:.2f} |")
    o.append(f"| Sharpe dispersion across folds | {result.sharpe_dispersion:.2f} |")
    o.append(f"| Folds positive | {_pct(result.positive_fold_fraction)} |")
    o.append(f"| Pooled out-of-sample Sharpe | {result.pooled_sharpe:.2f} |")
    o.append(f"| Pooled probabilistic Sharpe | {result.pooled_probabilistic_sharpe:.3f} |")
    o.append(f"| Held-out periods evaluated | {result.evaluated_periods} |")
    o.append("")
    o.append(
        "The dispersion and the positive-fold fraction matter as much as the level: a "
        "strong mean carried by one fold is not a strategy. The pooled probabilistic "
        "Sharpe corrects the pooled figure for sample length, skew, and kurtosis."
    )
    o.append("")

    o.append("## Robustness Tests")
    o.append("")
    o.append(
        f"- **Out-of-sample:** {len(result.folds)} purged, embargoed walk-forward folds; "
        f"every figure above is from held-out periods."
    )
    o.append(
        "- **Multiple testing:** these fold results must **not** be used to select "
        "among strategy variants and then reported as out-of-sample — that reintroduces "
        "p-hacking through the back door. Selecting across variants requires a deflated "
        "Sharpe correction, which this harness deliberately does not provide."
    )
    o.append("- **Capacity:** see turnover above; no capacity ceiling was modelled.")
    o.append("")

    o.append("## Findings")
    o.append("")
    o.append(
        f"- Mean out-of-sample fold Sharpe {result.mean_fold_sharpe:.2f} with dispersion "
        f"{result.sharpe_dispersion:.2f} across {len(result.folds)} fold(s)."
    )
    o.append(f"- Costs paid across folds: {_pct(result.pooled_total_costs)}.")
    o.append("")

    o.append("## Production Blockers")
    o.append("")
    o.append("- Capacity analysis and a benchmark comparison; see `agents/backtest_review/`.")
    o.append("")

    o.append("## Decision Recommendation")
    o.append("")
    o.append("- Research only. This records out-of-sample behaviour, not a promotion decision.")
    o.append("")

    o.append("## Reproducibility")
    o.append("")
    o.append(
        f"- Deterministic given the same returns, `fit_predict`, and config "
        f"(`n_folds`={len(result.folds)}, `rebalance_lag`={cfg.rebalance_lag}, "
        f"`transaction_cost_bps`={cfg.transaction_cost_bps})."
    )
    o.append("")

    o.append("## Open Questions")
    o.append("")
    o.append("- Is the fold count sufficient for the sample length?")
    o.append("")

    return "\n".join(o)


def _mean(values: Sequence[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _stdev(values: Sequence[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"
