#!/usr/bin/env python3
"""The real run -- wires 0045's leak-free FRED panel into 0046's walk-forward
harness (which composes 0044's engine and 0006's purged, embargoed folds).

Closes the follow-up left in `docs/handoff.md` and `specs/0045-fred-point-in-time/
tasks.md`: with `fred_local.db` produced by
`joshualutkemuller/fred-bronze-to-gold-pipeline`, building a point-in-time macro
panel and backtesting it is a wiring exercise on `fred_point_in_time.py` plus
`backtesting.py` / `walk_forward.py` -- no new signal logic belongs here (0045's
own Non-Goals: producing weights from the panel is 0001/0006/0041/0007's job).

The demonstration signal below is intentionally minimal: a cross-sectional
z-score of each series' trailing mean return over the fold's training window
only, long the strongest movers and short the weakest. It exists to prove the
panel -> returns -> walk-forward wiring end to end, not as a claimed edge --
see the rendered report's Findings section.

Usage:
    PYTHONPATH=src python3 scripts/fred_real_run.py \\
        --db-path "/path/to/fred_local.db" \\
        --out specs/0045-fred-point-in-time/backtest_report.md
"""

from __future__ import annotations

import argparse
import datetime
import statistics
import sys
from pathlib import Path
from typing import List, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quantsmith.pipelines.backtesting import BacktestConfig
from quantsmith.pipelines.fred_point_in_time import (
    build_panel,
    load_observations,
    panel_to_returns,
)
from quantsmith.pipelines.walk_forward import (
    render_walk_forward_report,
    walk_forward_backtest,
)

DEFAULT_SERIES = [
    "CPIAUCSL",  # CPI, all urban consumers
    "UNRATE",  # unemployment rate
    "PAYEMS",  # nonfarm payrolls
    "INDPRO",  # industrial production
    "FEDFUNDS",  # effective federal funds rate
    "DGS10",  # 10-year Treasury yield
    "T10Y2Y",  # 10y-2y term spread
    "GDP",  # nominal GDP (quarterly; sparser than the rest by design)
]


def month_starts(start: datetime.date, end: datetime.date) -> List[datetime.date]:
    dates = []
    d = start.replace(day=1)
    while d <= end:
        dates.append(d)
        year, month = d.year, d.month + 1
        if month > 12:
            year, month = year + 1, 1
        d = datetime.date(year, month, 1)
    return dates


def zscore_momentum_fit_predict(returns: Sequence[Sequence[float]], n_series: int):
    """Cross-sectional z-score of each series' trailing mean return, fit on
    the training window only and held static across the fold's test periods --
    demonstration-only, per 0045's Non-Goals (no signal logic belongs in the
    adapter itself)."""

    def fit_predict(train_periods, test_periods):
        train_rows = [returns[t] for t in train_periods]
        means = []
        for s in range(n_series):
            vals = [row[s] for row in train_rows]
            means.append(statistics.fmean(vals) if vals else 0.0)
        mu = statistics.fmean(means)
        sd = statistics.pstdev(means) if len(means) > 1 else 0.0
        if sd == 0:
            z = [0.0] * n_series
        else:
            z = [max(-2.0, min(2.0, (m - mu) / sd)) for m in means]
        gross = sum(abs(v) for v in z)
        weights = [v / gross for v in z] if gross > 0 else [0.0] * n_series
        return [weights for _ in test_periods]

    return fit_predict


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True, help="path to fred_local.db")
    parser.add_argument("--series", default=",".join(DEFAULT_SERIES))
    parser.add_argument("--start-date", default="2000-01-01")
    parser.add_argument("--end-date", default=datetime.date.today().isoformat())
    parser.add_argument("--n-folds", type=int, default=5)
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--embargo", type=int, default=1)
    parser.add_argument(
        "--out", default="specs/0045-fred-point-in-time/backtest_report.md"
    )
    args = parser.parse_args()

    series_ids = [s.strip() for s in args.series.split(",") if s.strip()]
    start = datetime.date.fromisoformat(args.start_date)
    end = datetime.date.fromisoformat(args.end_date)
    as_of_dates = month_starts(start, end)

    print(f"Loading {series_ids} from {args.db_path} ...")
    observations = load_observations(args.db_path, series_ids=series_ids)
    print(f"Loaded {len(observations)} point-in-time observation rows.")

    panel = build_panel(observations, as_of_dates, series_ids)
    returns = panel_to_returns(panel)
    print(f"Panel: {len(panel.as_of_dates)} as-of dates -> {len(returns)} return periods.")

    config = BacktestConfig(
        transaction_cost_bps=5.0,
        borrow_cost_bps_annual=50.0,
        periods_per_year=12,
        rebalance_lag=1,
    )
    fit_predict = zscore_momentum_fit_predict(returns, len(series_ids))

    result = walk_forward_backtest(
        returns,
        fit_predict,
        n_folds=args.n_folds,
        horizon=args.horizon,
        embargo=args.embargo,
        config=config,
    )

    print(
        f"Folds: {len(result.folds)} | mean fold Sharpe {result.mean_fold_sharpe:.2f} "
        f"| pooled Sharpe {result.pooled_sharpe:.2f} "
        f"| pooled probabilistic Sharpe {result.pooled_probabilistic_sharpe:.3f} "
        f"| positive folds {result.positive_fold_fraction:.0%}"
    )

    data_notes = (
        f"- Source: `gold_fred_point_in_time` in `{Path(args.db_path).name}` "
        f"(`joshualutkemuller/fred-bronze-to-gold-pipeline`, local mode, "
        f"no `FRED_API_KEY` in this repository).\n"
        f"- Universe: {', '.join(series_ids)} (`GDP` is quarterly and reported "
        f"stale between releases in this monthly panel by construction -- "
        f"staleness is visible, not hidden, per `build_panel`'s contract).\n"
        f"- As-of dates: {as_of_dates[0].isoformat()} to {as_of_dates[-1].isoformat()}, "
        f"month-start, `as_of_snapshot` per date -- a value is used only if its "
        f"vintage's `realtime_start` was on or before that as-of date.\n"
        f"- Weights come from a demonstration-only cross-sectional z-score of "
        f"trailing mean returns, fit on each fold's training window and held "
        f"static across its test window -- **not** a claimed signal; see "
        f"`specs/0045-fred-point-in-time/spec.md` Non-Goals (weight logic is "
        f"0001/0006/0041/0007's job, not this adapter's)."
    )

    report = render_walk_forward_report(
        result,
        strategy="FRED macro z-score momentum (demonstration wiring)",
        owner="quant-research",
        universe=f"{len(series_ids)}-series macro panel: {', '.join(series_ids)}",
        period=f"{as_of_dates[0].isoformat()} to {as_of_dates[-1].isoformat()}, monthly",
        data_notes=data_notes,
        spec_id="0045-fred-point-in-time (panel) + 0046-walk-forward (harness) + 0044-backtesting (engine)",
        last_updated=datetime.date.today().isoformat(),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
