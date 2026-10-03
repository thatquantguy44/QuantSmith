"""Synthetic data generators for spec 0095 tests and examples. Everything returned is synthetic.

Each generator is seeded, deterministic, and uses a known generating process, so an estimator can be
checked against the truth it should recover. Passing these checks proves the arithmetic is right;
it says nothing about performance on real companies.
"""

from __future__ import annotations

import math
import random
from datetime import timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .validation import CENSORED, day


def simulate_competing_risks(n: int, seed: int, rates: Mapping[str, float], formation_start: str,
                             formation_end: str, observation_end: str, covariate_beta: float = 0.0,
                             covariate_cause: str = "next_round") -> List[Dict[str, Any]]:
    """Companies with constant cause-specific hazards (per day), one binary covariate, and censoring at the end.

    ``covariate_beta`` multiplies the hazard of ``covariate_cause`` by exp(beta) when the covariate is 1.
    The all-cause time is exponential; the cause is drawn in proportion to the cause hazards.
    """
    rng = random.Random(f"surv-{seed}")
    start, end, obs = day(formation_start), day(formation_end), day(observation_end)
    span = (end - start).days
    subjects: List[Dict[str, Any]] = []
    for i in range(n):
        formed = start + timedelta(days=rng.randrange(span + 1))
        x = 1.0 if rng.random() < 0.5 else 0.0
        hz = {c: r * (math.exp(covariate_beta * x) if c == covariate_cause else 1.0) for c, r in rates.items()}
        total = sum(hz.values())
        t = rng.expovariate(total)
        u, acc, cause = rng.random() * total, 0.0, None
        for c, h in hz.items():
            acc += h
            if u <= acc:
                cause = c
                break
        cause = cause or next(iter(hz))
        ended = formed + timedelta(days=max(1, math.ceil(t)))
        event = cause
        if ended > obs:
            ended, event = obs, CENSORED
        subjects.append({"id": f"syn-co-{i:05d}", "formation_date": formed.isoformat(), "end_date": ended.isoformat(),
                         "event": event, "features_vector": (x,), "features": {"x": x},
                         "feature_known_at": {"x": formed.isoformat()}, "synthetic": True})
    return subjects


def true_cif(rates: Mapping[str, float], cause: str, t: float) -> float:
    """Analytic cumulative incidence under constant cause-specific hazards."""
    total = sum(rates.values())
    return rates[cause] / total * (1.0 - math.exp(-total * t))


def simulate_series(n_periods: int, seed: int, base: float = 20.0, noise_sd: float = 3.0,
                    emergence_start: Optional[int] = None, growth: float = 0.25, seasonal_amp: float = 0.0,
                    period_of_year: int = 4) -> List[float]:
    """Count series: flat-ish baseline plus noise, optional seasonality, optional exponential growth from ``emergence_start``."""
    rng = random.Random(f"series-{seed}")
    out = []
    for t in range(n_periods):
        level = base * (1.0 + seasonal_amp * math.sin(2 * math.pi * (t % period_of_year) / period_of_year))
        if emergence_start is not None and t >= emergence_start:
            level *= math.exp(growth * (t - emergence_start + 1))
        out.append(max(0.0, round(level + rng.gauss(0.0, noise_sd), 3)))
    return out


def _poisson(rng: random.Random, lam: float) -> int:
    """Knuth's method; exact for the modest means used here."""
    if lam <= 0:
        return 0
    if lam > 500:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, prod = math.exp(-lam), 0, rng.random()
    while prod > limit:
        k += 1
        prod *= rng.random()
    return k


def simulate_poisson_series(n_periods: int, seed: int, mean: float = 20.0, emergence_start: Optional[int] = None,
                            growth: float = 0.25) -> List[float]:
    """Poisson counts with an optional exponential-growth emergence: the realistic noise for event counts."""
    rng = random.Random(f"pois-{seed}")
    out = []
    for t in range(n_periods):
        lam = mean * (math.exp(growth * (t - emergence_start + 1)) if emergence_start is not None and t >= emergence_start else 1.0)
        out.append(float(_poisson(rng, lam)))
    return out


def simulate_block_graph(n_nodes: int, seed: int, p_in: float = 0.30, p_out: float = 0.02,
                         start: str = "2020-01-01", months: int = 36) -> Tuple[List[Tuple[str, str, str]], Dict[str, int]]:
    """Two-block graph; each edge gets a random known_at. Returns ``(edges, block_of_node)``."""
    rng = random.Random(f"graph-{seed}")
    block = {f"org-{i:03d}": (0 if i < n_nodes // 2 else 1) for i in range(n_nodes)}
    nodes = sorted(block)
    t0 = day(start)
    edges = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            if rng.random() < (p_in if block[a] == block[b] else p_out):
                edges.append((a, b, (t0 + timedelta(days=rng.randrange(months * 30))).isoformat()))
    return sorted(edges, key=lambda e: (e[2], e[0], e[1])), block


def simulate_triangle(n_quarters: int, seed: int, completeness: Sequence[float], level: float = 1000.0,
                      noise_sd: float = 0.0, completeness_noise_sd: float = 0.0) -> Tuple[List[float], List[List[Optional[float]]]]:
    """Reporting-lag triangle. ``completeness[k]`` is the share of a quarter's final amount reported after k lags.

    Returns ``(finals, triangle)`` where ``triangle[q][k]`` is the cumulative reported amount for event
    quarter q after k lags, or None when that lag has not elapsed as of the latest quarter.
    """
    rng = random.Random(f"tri-{seed}")
    lags = len(completeness)
    finals = [level * (1.0 + 0.02 * q) * (1.0 + rng.gauss(0.0, noise_sd)) for q in range(n_quarters)]
    tri: List[List[Optional[float]]] = []
    for q in range(n_quarters):
        shape = list(completeness)
        if completeness_noise_sd:                        # this quarter fills in a little faster or slower
            shape = [min(1.0, c * (1.0 + rng.gauss(0.0, completeness_noise_sd))) for c in completeness[:-1]] + [1.0]
            shape = [min(shape[i], shape[i + 1]) for i in range(len(shape) - 1)] + [1.0]
        row: List[Optional[float]] = []
        for k in range(lags):
            row.append(finals[q] * shape[k] if q + k <= n_quarters - 1 else None)
        tri.append(row)
    return finals, tri
