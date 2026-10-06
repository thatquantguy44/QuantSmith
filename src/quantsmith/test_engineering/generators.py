"""Seeded generators for the model-testing helpers (spec 0098).

Every generator takes a seed and builds a local ``numpy.random.Generator`` from it, so output is
reproducible and the global NumPy random state is never read or changed. ``rng_for(seed, case)`` gives
each case its own independent stream, which is how a reported failure is regenerated from ``(seed, case)``.

The most useful generator is ``convex_instance``: it chooses the answer first (a point ``x*`` with active
constraints and positive multipliers) and then solves for the objective coefficients that make ``x*``
satisfy the KKT conditions. The optimum of the returned LP or QP is therefore known without an oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

Array = np.ndarray


def rng_for(seed: int, *stream: int) -> np.random.Generator:
    """An independent generator for ``(seed, *stream)``; never touches global state."""
    parts = [int(seed), *(int(s) for s in stream)]
    if any(p < 0 for p in parts):
        raise ValueError("seed and stream indices must be non-negative integers")
    return np.random.default_rng(np.random.SeedSequence(parts))


# ---- input specs for relation and differential checks -----------------------------------------

@dataclass(frozen=True)
class InputSpec:
    kind: str                      # scalar | vector | matrix | spd
    rows: int = 1
    cols: int = 1
    low: float = -1.0
    high: float = 1.0

    def shape(self) -> tuple:
        return {"scalar": (), "vector": (self.rows,), "matrix": (self.rows, self.cols), "spd": (self.rows, self.rows)}[self.kind]


def parse_input_spec(text: str) -> InputSpec:
    """``scalar``, ``vector:N``, ``matrix:RxC`` or ``spd:N``."""
    kind, _, dims = text.strip().partition(":")
    try:
        if kind == "scalar" and not dims:
            return InputSpec("scalar")
        if kind == "vector":
            return InputSpec("vector", rows=_positive(dims))
        if kind == "spd":
            return InputSpec("spd", rows=_positive(dims))
        if kind == "matrix":
            r, _, c = dims.lower().partition("x")
            return InputSpec("matrix", rows=_positive(r), cols=_positive(c))
    except ValueError:
        pass
    raise ValueError(f"input spec must be scalar, vector:N, matrix:RxC or spd:N, got {text!r}")


def _positive(text: str) -> int:
    n = int(text)
    if n < 1:
        raise ValueError("dimension must be at least 1")
    return n


def generate_inputs(spec: InputSpec | str, cases: int, seed: int = 0) -> list[Any]:
    """``cases`` inputs of the given shape; case ``i`` uses ``rng_for(seed, i)``."""
    spec = parse_input_spec(spec) if isinstance(spec, str) else spec
    out: list[Any] = []
    for i in range(max(0, int(cases))):
        rng = rng_for(seed, i)
        if spec.kind == "spd":
            out.append(spd_matrix(rng, spec.rows))
        elif spec.kind == "scalar":
            out.append(float(rng.uniform(spec.low, spec.high)))
        else:
            out.append(rng.uniform(spec.low, spec.high, size=spec.shape()))
    return out


def spd_matrix(rng: np.random.Generator, n: int, ridge: float = 0.1) -> Array:
    """A symmetric positive-definite matrix (a covariance-like input): ``G G'/n + ridge I``."""
    g = rng.standard_normal((n, n))
    return g @ g.T / n + ridge * np.eye(n)


def return_panel(seed: int, n_obs: int, n_assets: int, mean: float = 0.0005, vol: float = 0.01) -> Array:
    """Synthetic asset returns, shape ``(n_obs, n_assets)``: one common factor plus idiosyncratic noise."""
    rng = rng_for(seed)
    common = rng.standard_normal((n_obs, 1))
    idio = rng.standard_normal((n_obs, n_assets))
    return mean + vol * (0.5 * common + np.sqrt(0.75) * idio)


# ---- regression data with known coefficients ---------------------------------------------------

@dataclass(frozen=True, eq=False)
class RegressionData:
    X: Array
    y: Array
    beta: Array                    # true slopes
    intercept_value: float         # 0.0 when there is no intercept
    intercept: bool
    noise: float
    seed: int

    @property
    def coef(self) -> Array:
        """True coefficients in the ``fit`` convention: intercept first when there is one."""
        return np.r_[self.intercept_value, self.beta] if self.intercept else self.beta.copy()


def regression_dataset(seed: int, n_obs: int = 200, n_features: int = 4, noise: float = 0.0, intercept: bool = True) -> RegressionData:
    rng = rng_for(seed)
    X = rng.standard_normal((n_obs, n_features))
    beta = rng.choice([-1.0, 1.0], size=n_features) * rng.uniform(0.5, 3.0, size=n_features)
    c0 = float(rng.uniform(-2.0, 2.0)) if intercept else 0.0
    y = c0 + X @ beta + (noise * rng.standard_normal(n_obs) if noise else 0.0)
    return RegressionData(X, y, beta, c0, intercept, float(noise), int(seed))


# ---- convex LP / QP with a known optimum -------------------------------------------------------

@dataclass(frozen=True, eq=False)
class ConvexInstance:
    """minimise ``½ x'Qx + q'x`` subject to ``A x ≤ b`` (and ``x ≥ 0`` when ``nonneg``).

    ``x_star``, ``y_star`` (inequality multipliers), ``z_star`` (bound multipliers) and ``objective_star`` are
    known by construction (``None`` after ``relaxed``). ``unique_x`` says the optimal point is unique.
    """
    kind: str
    Q: Array
    q: Array
    A: Array
    b: Array
    nonneg: bool
    seed: int
    x_star: Array | None = None
    y_star: Array | None = None
    z_star: Array | None = None
    objective_star: float | None = None
    unique_x: bool = False

    def objective(self, x: Array) -> float:
        x = np.asarray(x, dtype=float)
        return float(0.5 * x @ self.Q @ x + self.q @ x)

    def gradient(self, x: Array) -> Array:
        return self.Q @ np.asarray(x, dtype=float) + self.q

    def scaled(self, k: float) -> ConvexInstance:
        """Multiply the objective by ``k > 0``: the optimal point is unchanged, the optimal value scales."""
        if not k > 0:
            raise ValueError("scale factor must be positive")
        return replace(self, Q=self.Q * k, q=self.q * k,
                       y_star=None if self.y_star is None else self.y_star * k,
                       z_star=None if self.z_star is None else self.z_star * k,
                       objective_star=None if self.objective_star is None else self.objective_star * k)

    def relaxed(self, delta: float | Array) -> ConvexInstance:
        """Loosen every ``A x ≤ b`` row by ``delta ≥ 0``; the optimum is no longer known."""
        d = np.broadcast_to(np.asarray(delta, dtype=float), self.b.shape)
        if (d < 0).any():
            raise ValueError("relaxation must be non-negative")
        return replace(self, b=self.b + d, x_star=None, y_star=None, z_star=None, objective_star=None, unique_x=False)


def convex_instance(seed: int, kind: str = "lp", n_vars: int = 4, n_ineq: int | None = None, nonneg: bool = False,
                    n_active: int | None = None) -> ConvexInstance:
    """Build an LP or QP whose optimum is known (KKT construction).

    Stationarity ``Qx* + q + A'y − z = 0`` with ``y, z ≥ 0`` and complementary slackness holds by
    construction, so ``x*`` is optimal (the problem is convex). LP defaults aim for a unique vertex.
    """
    if kind not in ("lp", "qp"):
        raise ValueError("kind must be 'lp' or 'qp'")
    n = int(n_vars)
    m = int(n_ineq) if n_ineq is not None else (n + 1 if kind == "lp" else max(1, n - 1))
    if n < 1 or m < 1:
        raise ValueError("n_vars and n_ineq must be at least 1")
    rng = rng_for(seed)
    A = rng.standard_normal((m, n))

    if nonneg:
        k = int(rng.integers(1, n + 1))                       # support size: at least one positive coordinate
        support = np.zeros(n, dtype=bool)
        support[rng.choice(n, size=k, replace=False)] = True
        x = np.where(support, rng.uniform(0.5, 2.0, size=n), 0.0)
        z = np.where(support, 0.0, rng.uniform(0.5, 2.0, size=n))
    else:
        support = np.ones(n, dtype=bool)
        x = rng.standard_normal(n)
        z = np.zeros(n)

    if n_active is None:
        n_active = min(m, int(support.sum())) if kind == "lp" else int(rng.integers(0, min(m, n) + 1))
    n_active = max(0, min(int(n_active), m))
    active = np.zeros(m, dtype=bool)
    active[rng.choice(m, size=n_active, replace=False)] = True

    y = np.where(active, rng.uniform(0.5, 2.0, size=m), 0.0)
    b = A @ x + np.where(active, 0.0, rng.uniform(0.5, 2.0, size=m))
    Q = np.zeros((n, n)) if kind == "lp" else spd_matrix(rng, n)
    q = z - A.T @ y - Q @ x

    unique = kind == "qp"
    if kind == "lp":
        rows = np.vstack([A[active], np.eye(n)[~support]]) if (active.any() or (~support).any()) else np.zeros((0, n))
        unique = bool(rows.shape[0] >= n and np.linalg.matrix_rank(rows) == n)
    obj = float(0.5 * x @ Q @ x + q @ x)
    return ConvexInstance(kind, Q, q, A, b, bool(nonneg), int(seed), x_star=x, y_star=y, z_star=z, objective_star=obj, unique_x=unique)
