"""Anomaly tools. Spec ``0099`` (REQ-004, REQ-006).

Univariate robust z-scores (median and MAD), and multivariate outliers by
robust Mahalanobis distance (Minimum Covariance Determinant), Isolation Forest,
or Local Outlier Factor. Multivariate methods work on robustly standardized
columns ((x − median) / (1.4826·MAD)), with a strictly positive, heavily skewed
column (skew > 2) log-transformed first so a long tail does not by itself make
rows look anomalous while real extremes keep their magnitude; the robust covariance is fitted on a
seeded subsample of at most ``MCD_FIT_ROWS`` rows and every row is scored
against it. Estimators are fitted to score this dataset only and
are never returned or reused (NFR-005). Results are counts and aggregate
profiles of the flagged rows — never the rows themselves.
"""

from __future__ import annotations

from typing import List, Literal, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .registry import Params, ToolContext, analysis_tool
from .utils import NUMERIC_ROLES

ROBUST_Z_SCALE = 0.6745
MCD_FIT_ROWS = 5_000
# Above the default 20 so a group of up to ~35 similar outliers cannot mask itself by being its own neighbourhood.
LOF_NEIGHBORS = 35


def robust_scale(A: np.ndarray) -> np.ndarray:
    """Columns log-transformed when strictly positive and skewed above 2, then robustly standardized."""
    out = np.empty_like(A, dtype="float64")
    for j in range(A.shape[1]):
        x = A[:, j].astype("float64")
        if x.min() > 0 and np.ptp(x) > 0 and stats.skew(x) > 2:
            x = np.log(x)
        med = np.median(x)
        scale = 1.4826 * np.median(np.abs(x - med))
        if scale == 0:
            scale = x.std() or 1.0
        out[:, j] = (x - med) / scale
    return out


class OutliersParams(Params):
    columns: Optional[List[str]] = None
    threshold: float = 3.5


@analysis_tool(name="detect_outliers", category="anomalies", version="1.0.0",
               params=OutliersParams, columns={"columns": NUMERIC_ROLES})
def detect_outliers(df: pd.DataFrame, p: OutliersParams, ctx: ToolContext) -> dict:
    """Share of values per numeric column with a robust z-score beyond the threshold."""
    cols = p.columns or ctx.columns({"continuous_numeric"})
    expected = float(2 * stats.norm.sf(p.threshold))
    out = []
    for col in cols:
        x = pd.to_numeric(df[col], errors="coerce").dropna().to_numpy(dtype="float64")
        if x.size == 0:
            continue
        med = float(np.median(x))
        mad = float(np.median(np.abs(x - med)))
        if mad == 0:
            out.append({"column": col, "n": int(x.size), "skipped": "median absolute deviation is zero"})
            continue
        z = ROBUST_Z_SCALE * (x - med) / mad
        k = int((np.abs(z) > p.threshold).sum())
        skew = float(stats.skew(x, bias=False)) if x.size > 2 and np.ptp(x) > 0 else None
        out.append({"column": col, "n": int(x.size), "median": med, "mad": mad, "outliers": k, "skew": skew,
                    "outlier_pct": k / x.size, "expected_pct": expected,
                    "excess_ratio": (k / x.size) / expected if expected > 0 else None,
                    "high": int((z > p.threshold).sum()), "low": int((z < -p.threshold).sum())})
    out.sort(key=lambda d: (-(d.get("outlier_pct") or 0), d["column"]))
    return {"threshold": p.threshold, "columns": out}


class MultivariateParams(Params):
    columns: Optional[List[str]] = None
    method: Literal["mahalanobis", "isolation_forest", "lof"] = "mahalanobis"
    quantile: float = 0.999
    contamination: float = 0.01
    max_columns: int = 10


def outlier_flags(A: np.ndarray, method: str, *, seed: int, quantile: float = 0.999,
                  contamination: float = 0.01) -> tuple:
    """Boolean outlier flags for the rows of ``A`` and the method's settings.

    Mahalanobis flags rows whose robust distance exceeds the chi-square
    ``quantile``; Isolation Forest and LOF flag the ``contamination`` share of
    rows they score as most anomalous (an explicit, recorded share rather than
    the libraries' "auto" offsets, which flag a fifth of ordinary data).
    """
    n = A.shape[0]
    Z = robust_scale(A)
    if method == "mahalanobis":
        from sklearn.covariance import MinCovDet

        fit_rows = np.arange(n)
        if n > MCD_FIT_ROWS:
            fit_rows = np.sort(np.random.default_rng(seed).choice(n, size=MCD_FIT_ROWS, replace=False))
        mcd = MinCovDet(random_state=seed).fit(Z[fit_rows])
        cut = float(stats.chi2.ppf(quantile, df=A.shape[1]))
        return mcd.mahalanobis(Z) > cut, {"threshold_d2": cut, "expected_pct": 1 - quantile,
                                           "fit_rows": int(len(fit_rows)), "transform": "log if skewed, robust scale"}
    if method == "isolation_forest":
        from sklearn.ensemble import IsolationForest

        model = IsolationForest(n_estimators=200, random_state=seed, contamination=contamination)
        return model.fit_predict(Z) == -1, {"n_estimators": 200, "contamination": contamination}
    from sklearn.neighbors import LocalOutlierFactor

    k = min(LOF_NEIGHBORS, n - 1)
    flags = LocalOutlierFactor(n_neighbors=k, contamination=contamination).fit_predict(Z) == -1
    return flags, {"n_neighbors": k, "contamination": contamination}


@analysis_tool(name="detect_multivariate_outliers", category="anomalies", version="1.0.0",
               params=MultivariateParams, columns={"columns": NUMERIC_ROLES}, expensive=True)
def detect_multivariate_outliers(df: pd.DataFrame, p: MultivariateParams, ctx: ToolContext) -> dict:
    """Rows unusual across several numeric columns at once, by robust Mahalanobis distance, Isolation Forest, or LOF."""
    cols = sorted(p.columns or ctx.columns({"continuous_numeric"}))[: p.max_columns]
    out = {"method": p.method, "columns": cols}
    if len(cols) < 2:
        return {**out, "skipped": "fewer than two continuous numeric columns"}
    X = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    n = int(len(X))
    if n < max(ctx.min_n, 3 * len(cols)):
        return {**out, "n": n, "skipped": "too few complete rows"}
    A = X.to_numpy(dtype="float64")
    flagged, extra = outlier_flags(A, p.method, seed=ctx.seed, quantile=p.quantile, contamination=p.contamination)
    count = int(flagged.sum())
    profile = None
    if count >= ctx.min_cell:
        profile = [{"column": c, "median_flagged": float(np.median(A[flagged, i])),
                    "median_all": float(np.median(A[:, i]))} for i, c in enumerate(cols)]
    return {**out, **extra, "n": n, "outliers": count, "outlier_pct": count / n, "profile": profile}
