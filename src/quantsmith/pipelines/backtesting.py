"""Reference pipeline for spec 0044 -- backtest engine.

The artifact quant research exists to produce, and the one this SDK had
governed without ever running: ``instructions/backtesting.md`` is the standard,
``agents/backtest_review/`` reviews it, ``templates/docs/backtest_report.md`` is
its shape, and ``hooks/stages/backtest-check.sh`` is enforced in CI -- but
nothing here had ever produced a backtest for any of them to act on.

Three properties are deliberate:

* **No look-ahead is structural.** Weights decided at period ``i`` are applied
  to ``returns[i + rebalance_lag]`` with ``rebalance_lag >= 1`` enforced, so a
  weight vector cannot meet a return at or before its own decision index. That
  is an indexing impossibility, not an assertion that could be removed.

* **Net of costs is the default.** Every period's net return is its gross
  return less a turnover-scaled transaction cost and a financing charge on
  short exposure. Gross is recorded but never reported alone -- a long/short
  result cannot quietly omit borrow.

* **A probabilistic Sharpe accompanies every Sharpe.** A Sharpe ratio without a
  correction for sample length, skew, and kurtosis is the standard way a
  backtest misleads; ``probabilistic_sharpe_ratio`` is computed on every run
  rather than offered as an extra.

**The limit of the guarantee.** This engine controls its own simulation loop.
It cannot tell whether the *weights it was handed* were themselves built with
look-ahead -- a leaky signal will produce a clean-looking backtest here. That
remains ``instructions/point_in_time.md``'s concern and the ``leakage`` gate's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

Vector = Sequence[float]
Matrix = Sequence[Sequence[float]]

BPS = 10_000.0


@dataclass(frozen=True)
class BacktestConfig:
    """Cost and timing assumptions for a simulation."""

    transaction_cost_bps: float = 5.0
    borrow_cost_bps_annual: float = 0.0
    periods_per_year: int = 252
    rebalance_lag: int = 1


@dataclass(frozen=True)
class PeriodResult:
    period: int
    gross_return: float
    transaction_cost: float
    financing_cost: float
    net_return: float
    turnover: float
    long_exposure: float
    short_exposure: float
    gross_exposure: float
    net_exposure: float
    benchmark_return: Optional[float] = None
    active_return: Optional[float] = None


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    periods: List[PeriodResult] = field(default_factory=list)

    # -- paths -------------------------------------------------------------

    @property
    def net_returns(self) -> List[float]:
        return [p.net_return for p in self.periods]

    @property
    def equity_curve(self) -> List[float]:
        curve: List[float] = []
        level = 1.0
        for r in self.net_returns:
            level *= 1.0 + r
            curve.append(level)
        return curve

    # -- summary metrics ---------------------------------------------------

    @property
    def total_return(self) -> float:
        curve = self.equity_curve
        return curve[-1] - 1.0 if curve else 0.0

    @property
    def annualized_return(self) -> float:
        n = len(self.periods)
        if n == 0:
            return 0.0
        growth = 1.0 + self.total_return
        if growth <= 0:
            return -1.0
        return growth ** (self.config.periods_per_year / n) - 1.0

    @property
    def annualized_volatility(self) -> float:
        return _stdev(self.net_returns) * math.sqrt(self.config.periods_per_year)

    @property
    def sharpe(self) -> float:
        """Annualized Sharpe of the *net* path (excess over zero)."""
        sd = _stdev(self.net_returns)
        if sd == 0:
            return 0.0
        return _mean(self.net_returns) / sd * math.sqrt(self.config.periods_per_year)

    @property
    def max_drawdown(self) -> float:
        """Largest peak-to-trough decline of the equity curve, as a positive fraction."""
        peak = 1.0
        worst = 0.0
        for level in self.equity_curve:
            peak = max(peak, level)
            worst = max(worst, (peak - level) / peak)
        return worst

    @property
    def average_turnover(self) -> float:
        return _mean([p.turnover for p in self.periods])

    @property
    def hit_rate(self) -> float:
        if not self.periods:
            return 0.0
        return sum(1 for p in self.periods if p.net_return > 0) / len(self.periods)

    @property
    def total_costs(self) -> float:
        return sum(p.transaction_cost + p.financing_cost for p in self.periods)

    @property
    def probabilistic_sharpe(self) -> float:
        return probabilistic_sharpe_ratio(self.net_returns)

    @property
    def has_shorts(self) -> bool:
        return any(p.short_exposure > 0 for p in self.periods)

    @property
    def active_return(self) -> Optional[float]:
        """Mean per-period net return less benchmark, when a benchmark was given."""
        actives = [p.active_return for p in self.periods if p.active_return is not None]
        return _mean(actives) if actives else None


def run_backtest(
    weights: Matrix,
    returns: Matrix,
    config: Optional[BacktestConfig] = None,
    benchmark: Optional[Vector] = None,
) -> BacktestResult:
    """Simulate a weight path against realized returns, net of costs.

    ``weights[i]`` is the target portfolio decided using information through
    period ``i``; it is applied to ``returns[i + config.rebalance_lag]``. The
    offset is the no-look-ahead guarantee (REQ-001) -- see the module docstring
    for what it does and does not cover.
    """
    cfg = config or BacktestConfig()
    if cfg.rebalance_lag < 1:
        raise ValueError(
            "rebalance_lag must be at least 1: a lag of 0 would apply weights to "
            "the same period's return, which is look-ahead"
        )
    if cfg.periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")

    periods: List[PeriodResult] = []
    prev: List[float] = []

    for i, w in enumerate(weights):
        j = i + cfg.rebalance_lag
        if j >= len(returns):
            break
        row = list(returns[j])
        w = list(w)
        if len(w) != len(row):
            raise ValueError(
                f"period {i}: {len(w)} weight(s) but {len(row)} return(s) at period {j}"
            )
        if not prev:
            prev = [0.0] * len(w)

        gross = sum(wk * rk for wk, rk in zip(w, row))
        turnover = sum(abs(wk - pk) for wk, pk in zip(w, prev))
        tc = turnover * cfg.transaction_cost_bps / BPS

        short_exposure = sum(-wk for wk in w if wk < 0)
        long_exposure = sum(wk for wk in w if wk > 0)
        financing = short_exposure * cfg.borrow_cost_bps_annual / BPS / cfg.periods_per_year

        net = gross - tc - financing

        bench = None
        active = None
        if benchmark is not None and j < len(benchmark):
            bench = float(benchmark[j])
            active = net - bench

        periods.append(
            PeriodResult(
                period=i,
                gross_return=gross,
                transaction_cost=tc,
                financing_cost=financing,
                net_return=net,
                turnover=turnover,
                long_exposure=long_exposure,
                short_exposure=short_exposure,
                gross_exposure=long_exposure + short_exposure,
                net_exposure=long_exposure - short_exposure,
                benchmark_return=bench,
                active_return=active,
            )
        )
        prev = w

    return BacktestResult(config=cfg, periods=periods)


def probabilistic_sharpe_ratio(returns: Sequence[float], benchmark_sharpe: float = 0.0) -> float:
    """Probability the true Sharpe exceeds ``benchmark_sharpe`` (Bailey & López de Prado).

    Corrects an observed Sharpe for sample length, skew, and excess kurtosis --
    the honest answer to "is this distinguishable from luck". Returns a
    probability in ``[0, 1]``; ``0.0`` when the sample is too short or flat to
    say anything.
    """
    n = len(returns)
    if n < 3:
        return 0.0
    sd = _stdev(returns)
    if sd == 0:
        return 0.0

    sr = _mean(returns) / sd  # per-period, not annualized
    skew = _skew(returns, sd)
    kurt = _kurtosis(returns, sd)

    denom_sq = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if denom_sq <= 0:
        return 0.0
    z = (sr - benchmark_sharpe) * math.sqrt(n - 1) / math.sqrt(denom_sq)
    return _normal_cdf(z)


# ---------------------------------------------------------------------------
# Report rendering -- REQ-007
# ---------------------------------------------------------------------------


def render_backtest_report(
    result: BacktestResult,
    strategy: str,
    owner: str,
    universe: str,
    period: str,
    data_notes: str = "",
    benchmark_name: str = "",
    spec_id: str = "",
    last_updated: str = "",
) -> str:
    """Render a ``templates/docs/backtest_report.md``-shaped report.

    Populated from real computed results. States the cost model, the
    no-look-ahead guarantee *and its limit*, and the probabilistic Sharpe
    alongside the Sharpe -- never a headline number on its own.
    """
    cfg = result.config
    o: List[str] = []

    o.append(f"# Backtest Report: {strategy}")
    o.append("")
    o.append("> Generated by `render_backtest_report` (spec `0044-backtesting`) from a")
    o.append("> completed simulation. Every figure below is computed from the realized")
    o.append("> net path, never entered by hand.")
    if spec_id:
        o.append(f">")
        o.append(f"> **Spec:** {spec_id}")
    if last_updated:
        o.append(f"> **Last updated:** {last_updated}")
    o.append("")

    o.append("## Strategy Or Signal")
    o.append("")
    o.append(f"{strategy} — simulated over {universe}, {period}.")
    o.append("")

    o.append("## Owner")
    o.append("")
    o.append(f"- **Owner:** {owner}")
    o.append("")

    o.append("## Summary")
    o.append("")
    o.append(
        f"Net annualized return {_pct(result.annualized_return)} at "
        f"{_pct(result.annualized_volatility)} volatility "
        f"(Sharpe {result.sharpe:.2f}, probabilistic Sharpe "
        f"{result.probabilistic_sharpe:.3f}). Maximum drawdown "
        f"{_pct(result.max_drawdown)} over {len(result.periods)} periods."
    )
    o.append("")

    o.append("## Simulation Contract")
    o.append("")
    o.append(f"- **Periods simulated:** {len(result.periods)}")
    o.append(f"- **Periods per year:** {cfg.periods_per_year}")
    o.append(
        f"- **Rebalance lag:** {cfg.rebalance_lag} period(s) — weights decided at "
        f"period `i` are applied to returns at `i + {cfg.rebalance_lag}`, so a weight "
        f"vector can never meet a return at or before its own decision index."
    )
    o.append(
        "- **Limit of that guarantee:** it covers this simulation loop only. It does "
        "not establish that the weights supplied were themselves built without "
        "look-ahead; that is `instructions/point_in_time.md`'s concern and the "
        "`leakage` gate's."
    )
    o.append("")

    o.append("## Data And Point-In-Time Assumptions")
    o.append("")
    o.append(data_notes or "- Returns and weights were supplied already aligned by period.")
    o.append("")

    o.append("## Costs And Execution")
    o.append("")
    o.append(
        f"- **Transaction cost:** {cfg.transaction_cost_bps:.1f} bps per unit turnover, "
        f"linear in realized turnover."
    )
    o.append(
        f"- **Financing / borrow cost:** {cfg.borrow_cost_bps_annual:.1f} bps annual on "
        f"short exposure"
        + (
            "; this book holds shorts, so borrow is charged."
            if result.has_shorts
            else "; this book is long-only, so nothing was charged."
        )
    )
    o.append(f"- **Total costs paid:** {_pct(result.total_costs)} of starting capital.")
    o.append(
        "- **Not modelled:** market impact, partial fills, and intraday execution. The "
        "cost model is linear in turnover and will understate impact for a large book; "
        "impact-aware scheduling is `execution_optimization.py` (spec `0012`)."
    )
    o.append("")

    o.append("## Benchmarks And Baselines")
    o.append("")
    if result.active_return is not None:
        o.append(
            f"- **Benchmark:** {benchmark_name or 'supplied benchmark series'} — mean "
            f"per-period active return {_pct(result.active_return)}."
        )
    else:
        o.append(
            "- **Benchmark:** none supplied. A backtest without a baseline states a "
            "level, not an edge; supply one before drawing a conclusion."
        )
    o.append("")

    o.append("## Results")
    o.append("")
    o.append("| Metric | Value |")
    o.append("| --- | --- |")
    o.append(f"| Net total return | {_pct(result.total_return)} |")
    o.append(f"| Net annualized return | {_pct(result.annualized_return)} |")
    o.append(f"| Annualized volatility | {_pct(result.annualized_volatility)} |")
    o.append(f"| Sharpe (net) | {result.sharpe:.2f} |")
    o.append(f"| Probabilistic Sharpe (vs. 0) | {result.probabilistic_sharpe:.3f} |")
    o.append(f"| Maximum drawdown | {_pct(result.max_drawdown)} |")
    o.append(f"| Average turnover per period | {result.average_turnover:.4f} |")
    o.append(f"| Hit rate | {_pct(result.hit_rate)} |")
    o.append("")
    o.append(
        "The probabilistic Sharpe is the probability the true Sharpe exceeds zero given "
        "this sample's length, skew, and kurtosis. A high Sharpe with a low "
        "probabilistic Sharpe is a short or fat-tailed sample, not an edge — this is "
        "the multiple-testing and p-hacking guard, and it is computed on every run."
    )
    o.append("")

    o.append("## Robustness Tests")
    o.append("")
    o.append(
        "- **Out-of-sample:** this report covers a single simulated path. Walk-forward "
        "or holdout evaluation over purged, embargoed folds is `return_forecasting.py`'s "
        "`make_folds` (spec `0006`); results here are in-sample unless that was applied "
        "upstream."
    )
    o.append("- **Capacity:** see turnover above; no capacity ceiling was modelled.")
    o.append("")

    o.append("## Findings")
    o.append("")
    o.append(
        f"- Net of costs, the strategy returned {_pct(result.annualized_return)} "
        f"annualized against {_pct(result.annualized_volatility)} volatility."
    )
    o.append(
        f"- Costs consumed {_pct(result.total_costs)} of starting capital at an average "
        f"turnover of {result.average_turnover:.4f} per period."
    )
    o.append("")

    o.append("## Production Blockers")
    o.append("")
    o.append(
        "- Out-of-sample evidence, capacity analysis, and a benchmark comparison are "
        "required before any promotion decision; see `agents/backtest_review/`."
    )
    o.append("")

    o.append("## Decision Recommendation")
    o.append("")
    o.append(
        "- Research only. This report records what a supplied weight path would have "
        "produced under the stated assumptions; it is not a promotion recommendation."
    )
    o.append("")

    o.append("## Reproducibility")
    o.append("")
    o.append(
        f"- Deterministic: the same weights, returns, and config "
        f"(`transaction_cost_bps={cfg.transaction_cost_bps}`, "
        f"`borrow_cost_bps_annual={cfg.borrow_cost_bps_annual}`, "
        f"`periods_per_year={cfg.periods_per_year}`, "
        f"`rebalance_lag={cfg.rebalance_lag}`) reproduce this report exactly."
    )
    o.append("")

    o.append("## Open Questions")
    o.append("")
    o.append("- Is the cost model adequate for the intended book size?")
    o.append("")

    return "\n".join(o)


# ---------------------------------------------------------------------------
# Small numeric helpers (stdlib only)
# ---------------------------------------------------------------------------


def _mean(values: Sequence[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _stdev(values: Sequence[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _skew(values: Sequence[float], sd: float) -> float:
    values = list(values)
    n = len(values)
    if n < 3 or sd == 0:
        return 0.0
    m = _mean(values)
    return sum(((v - m) / sd) ** 3 for v in values) / n


def _kurtosis(values: Sequence[float], sd: float) -> float:
    """Non-excess kurtosis (3.0 for a normal sample)."""
    values = list(values)
    n = len(values)
    if n < 4 or sd == 0:
        return 3.0
    m = _mean(values)
    return sum(((v - m) / sd) ** 4 for v in values) / n


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"
