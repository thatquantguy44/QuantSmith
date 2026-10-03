"""ML pipeline agents for quant and securities lending workflows.

Provides a composable set of agents for:
  - Feature engineering from market / lending data
  - Model training (sklearn compatible)
  - Walk-forward backtesting / evaluation
  - Borrow-demand forecasting (sec lending specific)
  - Anomaly detection for risk monitoring

All agents follow the same Blackboard protocol as the rest of the pipeline.
scikit-learn is the primary ML dependency; numpy/scipy handle numerics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from .framework import Blackboard
from .agents import MarketData


# ---------------------------------------------------------------------------
# Shared dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FeatureSet:
    """Features and optional targets for ML training / inference."""

    feature_names: List[str]
    X: np.ndarray              # shape (n_samples, n_features)
    y: Optional[np.ndarray] = None   # shape (n_samples,) – None at inference time
    sample_dates: Optional[List[str]] = None
    tickers: Optional[List[str]] = None


@dataclass
class ModelArtifact:
    """Trained model and associated metadata."""

    model: Any                           # sklearn estimator
    model_type: str
    feature_names: List[str]
    train_score: float = 0.0
    val_score: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """Walk-forward backtest diagnostics."""

    fold_scores: List[float] = field(default_factory=list)
    predictions: np.ndarray = field(default_factory=lambda: np.array([]))
    actuals: np.ndarray = field(default_factory=lambda: np.array([]))
    mean_score: float = 0.0
    std_score: float = 0.0


# ---------------------------------------------------------------------------
# Agent 1 – Feature engineering (market data → features)
# ---------------------------------------------------------------------------

class FeatureEngineeringAgent:
    """Constructs ML features from market returns data.

    Reads ``market_data`` from the blackboard (populated by DataAgent or
    YahooFinanceDataAgent) and writes ``feature_set``.

    Features generated per asset (cross-sectionally stacked):
      - Momentum returns: 5d, 21d, 63d
      - Realised volatility: 21d, 63d
      - Volume-normalised return (if available)
      - Mean-reversion z-score: 5d vs 63d mean
    """

    def __init__(
        self,
        momentum_windows: Sequence[int] = (5, 21, 63),
        vol_windows: Sequence[int] = (21, 63),
        target_horizon: int = 5,
    ) -> None:
        self.name = "feature_engineering_agent"
        self._mom_windows = list(momentum_windows)
        self._vol_windows = list(vol_windows)
        self._target_horizon = target_horizon

    def run(self, blackboard: Blackboard) -> None:
        blackboard.require("market_data")
        md: MarketData = blackboard["market_data"]
        returns = md.returns           # shape (T, N)
        tickers = list(md.tickers)

        min_lookback = max(self._mom_windows + self._vol_windows) + self._target_horizon
        if returns.shape[0] < min_lookback:
            raise ValueError(
                f"Insufficient history: need at least {min_lookback} periods, "
                f"got {returns.shape[0]}"
            )

        T, N = returns.shape
        feature_rows: List[np.ndarray] = []
        ticker_labels: List[str] = []
        target_values: List[float] = []

        max_win = max(self._mom_windows + self._vol_windows)
        # Build cross-sectional feature matrix; one row per (time, asset)
        for t in range(max_win, T - self._target_horizon):
            for i, ticker in enumerate(tickers):
                feats: List[float] = []

                # Momentum
                for w in self._mom_windows:
                    r = float(
                        (1 + returns[t - w : t, i]).prod() - 1
                    )
                    feats.append(r)

                # Realised vol
                for w in self._vol_windows:
                    v = float(returns[t - w : t, i].std(ddof=1) * np.sqrt(252))
                    feats.append(v)

                # Mean-reversion z-score
                short_ret = float(returns[t - 5 : t, i].mean())
                long_ret = float(returns[t - 63 : t, i].mean())
                long_std = float(returns[t - 63 : t, i].std(ddof=1))
                z = (short_ret - long_ret) / long_std if long_std > 0 else 0.0
                feats.append(z)

                feature_rows.append(np.array(feats, dtype=float))
                ticker_labels.append(ticker)

                # Target: forward return over horizon
                fwd = float(returns[t : t + self._target_horizon, i].sum())
                target_values.append(fwd)

        feature_names = (
            [f"mom_{w}d" for w in self._mom_windows]
            + [f"vol_{w}d" for w in self._vol_windows]
            + ["mean_rev_z"]
        )

        X = np.array(feature_rows, dtype=float)
        y = np.array(target_values, dtype=float)

        # Replace any NaN / Inf
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        blackboard["feature_set"] = FeatureSet(
            feature_names=feature_names,
            X=X,
            y=y,
            tickers=ticker_labels,
        )


# ---------------------------------------------------------------------------
# Agent 2 – Model training
# ---------------------------------------------------------------------------

class ModelTrainingAgent:
    """Trains a scikit-learn estimator on the feature set.

    Reads ``feature_set`` from the blackboard and writes ``model_artifact``.
    Supports any sklearn-compatible estimator via the ``model_factory`` arg.

    Default: ``GradientBoostingRegressor`` for return prediction.
    """

    def __init__(
        self,
        model_factory: Optional[Callable[[], Any]] = None,
        train_pct: float = 0.80,
        model_type: str = "gradient_boost",
    ) -> None:
        self.name = "model_training_agent"
        self._factory = model_factory
        self._train_pct = train_pct
        self._model_type = model_type

    def run(self, blackboard: Blackboard) -> None:
        blackboard.require("feature_set")
        fs: FeatureSet = blackboard["feature_set"]

        if fs.y is None:
            raise ValueError("feature_set must have targets (y) for training")

        model = self._build_model()
        X, y = fs.X, fs.y

        n_train = max(1, int(len(X) * self._train_pct))
        X_train, X_val = X[:n_train], X[n_train:]
        y_train, y_val = y[:n_train], y[n_train:]

        model.fit(X_train, y_train)
        train_score = float(model.score(X_train, y_train))

        if len(X_val) > 0:
            val_score = float(model.score(X_val, y_val))
            y_pred = model.predict(X_val)
            residuals = y_val - y_pred
            metrics = {
                "val_r2": val_score,
                "val_mae": float(np.abs(residuals).mean()),
                "val_rmse": float(np.sqrt((residuals ** 2).mean())),
                "ic": float(np.corrcoef(y_pred, y_val)[0, 1]) if len(y_val) > 1 else 0.0,
            }
        else:
            val_score = 0.0
            metrics = {}

        blackboard["model_artifact"] = ModelArtifact(
            model=model,
            model_type=self._model_type,
            feature_names=fs.feature_names,
            train_score=train_score,
            val_score=val_score,
            metrics=metrics,
        )

    def _build_model(self) -> Any:
        if self._factory is not None:
            return self._factory()

        try:
            from sklearn.ensemble import GradientBoostingRegressor  # type: ignore
            return GradientBoostingRegressor(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42,
            )
        except ImportError:
            pass

        try:
            from sklearn.linear_model import Ridge  # type: ignore
            return Ridge(alpha=1.0)
        except ImportError:
            pass

        return _NaiveMeanRegressor()


# ---------------------------------------------------------------------------
# Agent 3 – Walk-forward backtest
# ---------------------------------------------------------------------------

class WalkForwardBacktestAgent:
    """Walk-forward cross-validation of the trained model.

    Reads ``feature_set`` and ``model_artifact`` (for the estimator class)
    and writes ``backtest_result`` to the blackboard.
    """

    def __init__(
        self,
        n_folds: int = 5,
        min_train_pct: float = 0.40,
        model_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        if n_folds < 2:
            raise ValueError("n_folds must be at least 2")
        self.name = "walk_forward_backtest_agent"
        self._n_folds = n_folds
        self._min_train_pct = min_train_pct
        self._factory = model_factory

    def run(self, blackboard: Blackboard) -> None:
        blackboard.require("feature_set")
        fs: FeatureSet = blackboard["feature_set"]

        if fs.y is None:
            raise ValueError("feature_set must have targets for backtesting")

        artifact: Optional[ModelArtifact] = blackboard.get("model_artifact")

        X, y = fs.X, fs.y
        n = len(X)
        fold_size = n // (self._n_folds + 1)
        min_train = max(1, int(n * self._min_train_pct))

        fold_scores: List[float] = []
        all_preds: List[np.ndarray] = []
        all_actuals: List[np.ndarray] = []

        for fold in range(self._n_folds):
            test_start = min_train + fold * fold_size
            test_end = test_start + fold_size
            if test_end > n:
                break

            X_tr, y_tr = X[:test_start], y[:test_start]
            X_te, y_te = X[test_start:test_end], y[test_start:test_end]

            model = self._get_model(artifact)
            model.fit(X_tr, y_tr)
            score = float(model.score(X_te, y_te))
            fold_scores.append(score)
            all_preds.append(model.predict(X_te))
            all_actuals.append(y_te)

        preds_arr = np.concatenate(all_preds) if all_preds else np.array([])
        actuals_arr = np.concatenate(all_actuals) if all_actuals else np.array([])

        result = BacktestResult(
            fold_scores=fold_scores,
            predictions=preds_arr,
            actuals=actuals_arr,
            mean_score=float(np.mean(fold_scores)) if fold_scores else 0.0,
            std_score=float(np.std(fold_scores, ddof=1)) if len(fold_scores) > 1 else 0.0,
        )
        blackboard["backtest_result"] = result

    def _get_model(self, artifact: Optional[ModelArtifact]) -> Any:
        if self._factory is not None:
            return self._factory()
        if artifact is not None:
            # Re-instantiate same class with default params
            try:
                return type(artifact.model).__new__(type(artifact.model))
            except Exception:
                pass
        return _NaiveMeanRegressor()


# ---------------------------------------------------------------------------
# Agent 4 – Borrow demand forecasting (sec-lending specific)
# ---------------------------------------------------------------------------

class BorrowDemandForecastAgent:
    """Predicts near-term borrow demand for securities in the lending universe.

    Uses borrow-rate history (rate trend, utilization trend, rate volatility)
    as features to forecast whether demand will increase.  Writes
    ``borrow_demand_forecast`` as a list of per-ticker dicts.

    Operates in heuristic mode when sklearn is not available.
    """

    def __init__(self, horizon_days: int = 5) -> None:
        if horizon_days < 1:
            raise ValueError("horizon_days must be at least 1")
        self.name = "borrow_demand_forecast_agent"
        self._horizon = horizon_days

    def run(self, blackboard: Blackboard) -> None:
        blackboard.require("sec_lending_universe")
        from .sec_lending import SecLendingUniverse

        universe: SecLendingUniverse = blackboard["sec_lending_universe"]
        secs = universe.securities

        forecasts = []
        for sec in secs:
            # Heuristic features: rate trend, utilization, volatility
            rate_trend = sec.rate_bps - sec.rate_30d_avg  # positive = rising
            util = sec.utilization
            rate_vol = sec.rate_30d_vol

            # Demand score: higher util + rising rates → higher forecast
            demand_score = util * 0.5 + (rate_trend / max(sec.rate_30d_avg, 1)) * 0.3
            demand_score += min(rate_vol / max(sec.rate_bps, 1), 0.5) * 0.2

            # Scale to current availability × util as base demand
            base_demand = sec.availability * sec.utilization
            predicted_demand = base_demand * (1 + demand_score * self._horizon / 252)

            confidence = (
                "HIGH" if util > 0.80 and rate_trend > 0
                else "MEDIUM" if util > 0.50
                else "LOW"
            )

            forecasts.append(
                {
                    "ticker": sec.ticker,
                    "cusip": sec.cusip,
                    "predicted_demand": max(0, predicted_demand),
                    "demand_score": round(float(demand_score), 4),
                    "confidence": confidence,
                    "classification": sec.classification,
                }
            )

        # Sort by demand score descending
        forecasts.sort(key=lambda x: x["demand_score"], reverse=True)
        blackboard["borrow_demand_forecast"] = forecasts


# ---------------------------------------------------------------------------
# Agent 5 – Anomaly detection for risk monitoring
# ---------------------------------------------------------------------------

class AnomalyDetectionAgent:
    """Detects statistical anomalies in returns or borrow-rate data.

    Uses z-score based detection on the most recent window.  Flags assets
    whose returns or borrow rates fall outside `n_sigma` standard deviations.
    Writes ``anomaly_flags`` to the blackboard.
    """

    def __init__(self, lookback: int = 21, n_sigma: float = 3.0) -> None:
        if lookback < 5:
            raise ValueError("lookback must be at least 5")
        if n_sigma <= 0:
            raise ValueError("n_sigma must be positive")
        self.name = "anomaly_detection_agent"
        self._lookback = lookback
        self._n_sigma = n_sigma

    def run(self, blackboard: Blackboard) -> None:
        flags: Dict[str, Any] = {"return_anomalies": [], "rate_anomalies": []}

        # Return anomalies
        md: Optional[MarketData] = blackboard.get("market_data")
        if md is not None and md.returns.shape[0] >= self._lookback:
            window = md.returns[-self._lookback :]
            means = window.mean(axis=0)
            stds = window.std(axis=0, ddof=1)
            latest = md.returns[-1]
            for i, ticker in enumerate(md.tickers):
                if stds[i] > 0:
                    z = (latest[i] - means[i]) / stds[i]
                    if abs(z) > self._n_sigma:
                        flags["return_anomalies"].append(
                            {
                                "ticker": ticker,
                                "z_score": round(float(z), 2),
                                "latest_return": round(float(latest[i]), 4),
                            }
                        )

        # Borrow rate anomalies (from sec lending universe)
        from .sec_lending import SecLendingUniverse

        universe: Optional[SecLendingUniverse] = blackboard.get("sec_lending_universe")
        if universe is not None:
            for sec in universe.securities:
                if sec.rate_30d_vol > 0:
                    z = (sec.rate_bps - sec.rate_30d_avg) / sec.rate_30d_vol
                    if abs(z) > self._n_sigma:
                        flags["rate_anomalies"].append(
                            {
                                "ticker": sec.ticker,
                                "z_score": round(float(z), 2),
                                "current_rate_bps": sec.rate_bps,
                                "avg_rate_bps": round(sec.rate_30d_avg, 1),
                            }
                        )

        blackboard["anomaly_flags"] = flags


# ---------------------------------------------------------------------------
# ML report agent
# ---------------------------------------------------------------------------

class MLReportAgent:
    """Summarises ML pipeline outputs: model performance, backtest, anomalies."""

    def __init__(self) -> None:
        self.name = "ml_report_agent"

    def run(self, blackboard: Blackboard) -> None:
        lines: List[str] = []
        lines.append("ML Pipeline Report")
        lines.append("=" * 55)

        artifact: Optional[ModelArtifact] = blackboard.get("model_artifact")
        if artifact:
            lines.append(f"\nModel: {artifact.model_type}")
            lines.append(f"  Train R²: {artifact.train_score:.4f}")
            lines.append(f"  Val R²:   {artifact.val_score:.4f}")
            for k, v in artifact.metrics.items():
                lines.append(f"  {k}: {v:.4f}")

        bt: Optional[BacktestResult] = blackboard.get("backtest_result")
        if bt and bt.fold_scores:
            lines.append(
                f"\nWalk-Forward Backtest ({len(bt.fold_scores)} folds):"
            )
            lines.append(f"  Mean R²: {bt.mean_score:.4f} ± {bt.std_score:.4f}")
            lines.append(
                "  Fold scores: "
                + ", ".join(f"{s:.3f}" for s in bt.fold_scores)
            )

        anomalies = blackboard.get("anomaly_flags")
        if anomalies:
            ra = anomalies.get("return_anomalies", [])
            rate_a = anomalies.get("rate_anomalies", [])
            if ra:
                lines.append("\nReturn Anomalies Detected:")
                for a in ra:
                    lines.append(
                        f"  {a['ticker']:<6} z={a['z_score']:+.1f}  "
                        f"ret={a['latest_return']:.2%}"
                    )
            if rate_a:
                lines.append("\nBorrow Rate Anomalies Detected:")
                for a in rate_a:
                    lines.append(
                        f"  {a['ticker']:<6} z={a['z_score']:+.1f}  "
                        f"current={a['current_rate_bps']:.0f} bps  "
                        f"avg={a['avg_rate_bps']:.0f} bps"
                    )
            if not ra and not rate_a:
                lines.append("\nNo anomalies detected.")

        blackboard["ml_report"] = "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallback model (no sklearn)
# ---------------------------------------------------------------------------

class _NaiveMeanRegressor:
    """Predict the training-set mean.  Used when sklearn is unavailable."""

    def __init__(self) -> None:
        self._mean: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "_NaiveMeanRegressor":
        self._mean = float(np.mean(y))
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.full(len(X), self._mean)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        preds = self.predict(X)
        ss_res = float(np.sum((y - preds) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
