"""Fund and portfolio analytics for spec 0091.

Deterministic, standard-library functions for venture fund reporting and review:
multiples (DPI/RVPI/TVPI), XIRR, the cash-flow J-curve, Kaplan-Schoar PME, peer
percentile rank, a mark-consistency review, and seeded Monte Carlo of fund outcomes
and reserve policy.

What it does not do: set, approve, or certify a valuation, decide a follow-on, or
rank a fund. Review functions return *flags with numbers*; simulations return
distributions with their assumptions. People decide. Cash-flow sign convention: from
the limited partner's view, contributions are outflows and distributions inflows; the
latest reported NAV is a terminal inflow at its date.
"""

from __future__ import annotations

import math
import random
from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

FLOW_TYPES = ("contribution", "distribution", "nav")
DAYS_PER_YEAR = 365.0                     # XIRR day count: Actual/365 (conv.xirr)
MIN_PEERS = 10
MIN_TRIALS = 100
MARK_FLAG_CODES = ("missing_basis", "stale_mark", "markup_without_new_round", "mark_predates_latest_round",
                   "down_round_not_reflected", "price_deviates_from_last_round")


def _day(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


# ------------------------------------------------------------------ cash flows
def normalize_flows(flows: Sequence[Mapping[str, Any]], as_of: Optional[str] = None) -> List[Dict[str, Any]]:
    """Validate flows and keep those known on ``as_of`` (date and, if present, ``known_at``)."""
    cutoff = _day(as_of) if as_of else None
    out: List[Dict[str, Any]] = []
    for f in flows:
        if f.get("type") not in FLOW_TYPES:
            raise ValueError(f"unknown flow type {f.get('type')!r}")
        amount = float(f["amount"])
        if amount < 0:
            raise ValueError("flow amounts are positive; the type carries the sign")
        d = _day(f["date"])
        if cutoff and d > cutoff:
            continue
        if cutoff and f.get("known_at") and _day(f["known_at"]) > cutoff:
            continue
        out.append({"date": d, "type": f["type"], "amount": amount})
    order = {"contribution": 0, "distribution": 1, "nav": 2}
    return sorted(out, key=lambda x: (x["date"], order[x["type"]]))


def fund_multiples(flows: Sequence[Mapping[str, Any]], as_of: str,
                   max_nav_age_days: Optional[int] = None) -> Dict[str, Any]:
    """DPI, RVPI, and TVPI as of a date, using the latest NAV on or before it."""
    fl = normalize_flows(flows, as_of)
    paid_in = sum(f["amount"] for f in fl if f["type"] == "contribution")
    dist = sum(f["amount"] for f in fl if f["type"] == "distribution")
    navs = [f for f in fl if f["type"] == "nav"]
    nav = navs[-1]["amount"] if navs else 0.0
    nav_date = navs[-1]["date"] if navs else None
    if paid_in <= 0:
        raise ValueError("paid-in capital must be positive to compute multiples")
    warnings: List[str] = []
    if not navs:
        warnings.append("no_nav_reported")
    elif max_nav_age_days is not None and (_day(as_of) - nav_date).days > max_nav_age_days:
        warnings.append("nav_stale")
    dpi, rvpi = dist / paid_in, nav / paid_in
    return {"as_of": _day(as_of).isoformat(), "paid_in": paid_in, "distributions": dist, "nav": nav,
            "nav_date": nav_date.isoformat() if nav_date else None, "dpi": dpi, "rvpi": rvpi,
            "tvpi": dpi + rvpi, "warnings": warnings}


def deal_moic(invested: float, realized: float, unrealized: float) -> float:
    if invested <= 0:
        raise ValueError("invested cost must be positive")
    return (realized + unrealized) / invested


def _signed(fl: Sequence[Mapping[str, Any]]) -> List[Tuple[date, float]]:
    navs = [f for f in fl if f["type"] == "nav"]
    last_nav = navs[-1] if navs else None
    out: List[Tuple[date, float]] = []
    for f in fl:
        if f["type"] == "contribution":
            out.append((f["date"], -f["amount"]))
        elif f["type"] == "distribution":
            out.append((f["date"], f["amount"]))
        elif f is last_nav:
            out.append((f["date"], f["amount"]))
    return out


def _bisect(npv, lo: float, hi: float) -> Tuple[float, int]:
    f_lo = npv(lo)
    iters = 0
    for iters in range(1, 300):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
        if hi - lo < 1e-13:
            break
    return (lo + hi) / 2.0, iters


def xirr(flows: Sequence[Mapping[str, Any]], as_of: str, guess: float = 0.10) -> Dict[str, Any]:
    """Annualised IRR on dated flows (Actual/365) with the latest NAV as a terminal inflow.

    The rate grid is scanned for every sign change of the net present value, so flows that
    change sign more than once report *all* roots in ``roots`` (grid-limited) and warn that the
    IRR is not unique; ``irr`` is the root nearest ``guess``. Raises if there is no root.
    """
    sig = _signed(normalize_flows(flows, as_of))
    if len(sig) < 2 or not any(a < 0 for _, a in sig) or not any(a > 0 for _, a in sig):
        raise ValueError("XIRR needs at least one outflow and one inflow")
    t0 = min(d for d, _ in sig)
    years = [((d - t0).days / DAYS_PER_YEAR, a) for d, a in sig]

    def npv(r: float) -> float:
        return sum(a / (1.0 + r) ** t for t, a in years)

    grid = [-0.99 + 0.005 * k for k in range(int((10.0 + 0.99) / 0.005) + 1)]
    r = 10.0
    while r < 1e6:
        r *= 1.5
        grid.append(r)
    roots: List[float] = []
    iters = 0
    prev_r, prev_f = grid[0], npv(grid[0])
    for r in grid[1:]:
        f = npv(r)
        if prev_f == 0.0:
            roots.append(prev_r)
        elif prev_f * f < 0:
            root, iters = _bisect(npv, prev_r, r)
            roots.append(root)
        prev_r, prev_f = r, f
    if not roots:
        raise ValueError("XIRR has no root; check the sign of the flows")
    ordered = sorted(sig, key=lambda x: x[0])
    signs = [1 if a > 0 else -1 for _, a in ordered]
    flips = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    warnings = ["multiple_sign_changes_irr_may_not_be_unique"] if flips > 1 or len(roots) > 1 else []
    best = min(roots, key=lambda x: (abs(x - guess), x))
    return {"irr": best, "roots": roots, "iterations": iters, "warnings": warnings, "day_count": "Actual/365"}


def net_cash_flow_profile(flows: Sequence[Mapping[str, Any]], as_of: Optional[str] = None) -> Dict[str, Any]:
    """Running net of distributions minus contributions (NAV excluded): the J-curve's cash view."""
    fl = [f for f in normalize_flows(flows, as_of) if f["type"] != "nav"]
    running = 0.0
    points: List[Dict[str, Any]] = []
    for f in fl:
        running += f["amount"] if f["type"] == "distribution" else -f["amount"]
        points.append({"date": f["date"].isoformat(), "running_net": running})
    if not points:
        raise ValueError("no contribution or distribution flows")
    trough = min(points, key=lambda p: (p["running_net"], p["date"]))
    breakeven = next((p["date"] for p in points if p["running_net"] >= 0 and p["date"] >= trough["date"]
                      and trough["running_net"] < 0), None)
    return {"points": points, "trough": trough, "breakeven_date": breakeven}


def j_curve(flows: Sequence[Mapping[str, Any]], report_dates: Sequence[str]) -> List[Dict[str, Any]]:
    """Multiples and IRR at each report date, each using only information on or before it."""
    rows = []
    for rd in report_dates:
        try:
            m = fund_multiples(flows, rd)
        except ValueError:
            rows.append({"as_of": _day(rd).isoformat(), "error": "no_paid_in_capital_yet"})
            continue
        try:
            irr_v: Optional[float] = xirr(flows, rd)["irr"]
            reason = None
        except ValueError as exc:
            irr_v, reason = None, str(exc)
        rows.append({"as_of": m["as_of"], "dpi": m["dpi"], "rvpi": m["rvpi"], "tvpi": m["tvpi"],
                     "irr": irr_v, "irr_unavailable_reason": reason})
    return rows


# ------------------------------------------------------------- PME and benchmark
def index_level_at(index_levels: Mapping[str, float], when: date) -> float:
    """Level on or before ``when``; raises if the index starts later."""
    dated = sorted((_day(k), float(v)) for k, v in index_levels.items())
    prior = [lv for d, lv in dated if d <= when]
    if not prior:
        raise ValueError(f"index has no level on or before {when.isoformat()}")
    if prior[-1] <= 0:
        raise ValueError("index levels must be positive")
    return prior[-1]


def ks_pme(flows: Sequence[Mapping[str, Any]], index_levels: Mapping[str, float], as_of: str) -> Dict[str, Any]:
    """Kaplan-Schoar PME: future value of distributions plus NAV over future value of contributions."""
    fl = normalize_flows(flows, as_of)
    end = _day(as_of)
    i_end = index_level_at(index_levels, end)
    fv_contrib = fv_dist = 0.0
    navs = [f for f in fl if f["type"] == "nav"]
    for f in fl:
        factor = i_end / index_level_at(index_levels, f["date"])
        if f["type"] == "contribution":
            fv_contrib += f["amount"] * factor
        elif f["type"] == "distribution":
            fv_dist += f["amount"] * factor
    if navs:
        n = navs[-1]
        fv_dist += n["amount"] * (i_end / index_level_at(index_levels, n["date"]))
    if fv_contrib <= 0:
        raise ValueError("future value of contributions must be positive")
    return {"ks_pme": fv_dist / fv_contrib, "fv_contributions": fv_contrib, "fv_distributions_and_nav": fv_dist,
            "interpretation": "above 1 means the fund outperformed the index investment; says nothing about skill"}


def peer_percentile(value: float, peers: Sequence[Mapping[str, Any]], vintage: int, metric: str = "tvpi",
                    min_peers: int = MIN_PEERS) -> Dict[str, Any]:
    """Percentile rank among vintage-matched peers supplied by the caller. Refuses a thin or mismatched set."""
    pool = [float(p[metric]) for p in peers if int(p["vintage"]) == int(vintage)]
    if len(pool) < min_peers:
        raise ValueError(f"insufficient vintage-matched peers: {len(pool)} < {min_peers}")
    below = sum(1 for x in pool if x < value)
    ties = sum(1 for x in pool if x == value)
    rank = (below + 0.5 * ties) / len(pool)
    quartile = 1 if rank >= 0.75 else 2 if rank >= 0.5 else 3 if rank >= 0.25 else 4
    return {"percentile_rank": rank, "quartile": quartile, "n_peers": len(pool), "vintage": int(vintage),
            "metric": metric, "caveat": "benchmark composition, self-reporting, and survivorship limit this comparison"}


# ------------------------------------------------------------------- mark review
def review_marks(holdings: Sequence[Mapping[str, Any]], as_of: str, max_age_days: int,
                 price_tolerance: float) -> List[Dict[str, Any]]:
    """Flag inconsistencies in valuation marks. Returns flags with numbers; sets and approves nothing.

    Thresholds (``max_age_days``, ``price_tolerance``) are the caller's, from the valuation policy.
    Each holding: company_id, mark_date, fair_value, shares, basis, and optionally prior_mark_value,
    prior_mark_date, last_round_date, last_round_price.
    """
    end = _day(as_of)
    out: List[Dict[str, Any]] = []

    def flag(h: Mapping[str, Any], code: str, **detail: Any) -> None:
        out.append({"company_id": h["company_id"], "code": code, "detail": detail,
                    "decision_owner": "valuation committee"})

    for h in holdings:
        basis = str(h.get("basis") or "").strip()
        mark_date = _day(h["mark_date"])
        fv, shares = float(h["fair_value"]), float(h.get("shares") or 0)
        if not basis:
            flag(h, "missing_basis")
        age = (end - mark_date).days
        if age > max_age_days:
            flag(h, "stale_mark", age_days=age, max_age_days=max_age_days)
        lr_date = _day(h["last_round_date"]) if h.get("last_round_date") else None
        lr_price = float(h["last_round_price"]) if h.get("last_round_price") is not None else None
        prior_val = h.get("prior_mark_value")
        prior_date = _day(h["prior_mark_date"]) if h.get("prior_mark_date") else None
        if basis == "last_round" and prior_val is not None and fv > float(prior_val) \
                and (lr_date is None or (prior_date is not None and lr_date <= prior_date)):
            flag(h, "markup_without_new_round", prior_value=float(prior_val), fair_value=fv)
        if lr_date and lr_date > mark_date:
            flag(h, "mark_predates_latest_round", mark_date=mark_date.isoformat(), round_date=lr_date.isoformat())
        if shares > 0 and lr_price:
            implied = fv / shares
            deviation = implied / lr_price - 1.0
            if lr_date and lr_date > mark_date and implied > lr_price * (1.0 + price_tolerance):
                flag(h, "down_round_not_reflected", implied_price=implied, last_round_price=lr_price)
            elif basis == "last_round" and abs(deviation) > price_tolerance:
                flag(h, "price_deviates_from_last_round", implied_price=implied, last_round_price=lr_price,
                     deviation=deviation, tolerance=price_tolerance)
    return out


# ------------------------------------------------------------------- simulation
def _check(n: int, p_loss: float, alpha: float, xmin: float, cap: float, trials: int) -> None:
    if n < 1:
        raise ValueError("n_companies must be at least 1")
    if not 0.0 <= p_loss <= 1.0:
        raise ValueError("p_loss must be in [0, 1]")
    if alpha <= 0 or xmin <= 0 or cap < xmin:
        raise ValueError("alpha and xmin must be positive and cap at least xmin")
    if trials < MIN_TRIALS:
        raise ValueError(f"trials must be at least {MIN_TRIALS}")


def _company_multiple(rng: random.Random, p_loss: float, alpha: float, xmin: float, cap: float) -> float:
    if rng.random() < p_loss:
        return 0.0
    u = rng.random()
    return min(xmin * (1.0 - u) ** (-1.0 / alpha), cap)


def _quantile(sorted_vals: Sequence[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _summary(values: List[float], extra: Dict[str, Any]) -> Dict[str, Any]:
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    var = sum((x - mean) ** 2 for x in s) / (n - 1) if n > 1 else 0.0
    out = {"trials": n, "mean": mean, "mcse": math.sqrt(var / n),
           "q05": _quantile(s, 0.05), "q25": _quantile(s, 0.25), "q50": _quantile(s, 0.5),
           "q75": _quantile(s, 0.75), "q95": _quantile(s, 0.95),
           "p_below_1x": sum(1 for x in s if x < 1.0) / n}
    out.update(extra)
    return out


def simulate_fund(n_companies: int, p_loss: float, alpha: float, xmin: float, cap: float, trials: int,
                  seed: int) -> Dict[str, Any]:
    """Distribution of the gross fund multiple with equal checks and heavy-tailed outcomes.

    Each company returns 0 with probability ``p_loss``, else a Pareto(alpha, xmin) multiple
    capped at ``cap``. Gross: before fees, timing, and partial losses. Seeded and deterministic.
    """
    _check(n_companies, p_loss, alpha, xmin, cap, trials)
    fund: List[float] = []
    top_share: List[float] = []
    for t in range(trials):
        rng = random.Random(f"{seed}-{t}")
        ms = [_company_multiple(rng, p_loss, alpha, xmin, cap) for _ in range(n_companies)]
        total = sum(ms)
        fund.append(total / n_companies)
        top_share.append(max(ms) / total if total > 0 else 0.0)
    return _summary(fund, {
        "mean_top_company_share_of_proceeds": sum(top_share) / trials,
        "assumptions": {"n_companies": n_companies, "p_loss": p_loss, "alpha": alpha, "xmin": xmin, "cap": cap,
                        "seed": seed, "gross": "before fees, timing, and partial losses; equal checks"}})


def alpha_sensitivity(alphas: Sequence[float], **params: Any) -> Dict[float, Dict[str, Any]]:
    """Re-run ``simulate_fund`` across tail parameters with the same seed."""
    return {a: simulate_fund(alpha=a, **params) for a in alphas}


def bootstrap_fund(cohort_multiples: Sequence[float], n_companies: int, trials: int, seed: int) -> Dict[str, Any]:
    """Fund multiples built by resampling a supplied cohort of company multiples with replacement.

    Also reports the share of trials below the equal-outcome null (every company returns the
    cohort mean). A cohort under 30 companies carries a ``small_sample`` warning.
    """
    if not cohort_multiples:
        raise ValueError("cohort is empty")
    if any(m < 0 for m in cohort_multiples):
        raise ValueError("multiples cannot be negative")
    _check(n_companies, 0.0, 1.0, 1.0, 1.0, trials)
    pool = list(cohort_multiples)
    null = sum(pool) / len(pool)
    fund = []
    for t in range(trials):
        rng = random.Random(f"{seed}-{t}")
        fund.append(sum(rng.choice(pool) for _ in range(n_companies)) / n_companies)
    warnings = ["small_sample"] if len(pool) < 30 else []
    return _summary(fund, {"equal_outcome_null": null,
                           "share_below_equal_outcome_null": sum(1 for x in fund if x < null) / trials,
                           "warnings": warnings,
                           "assumptions": {"cohort_size": len(pool), "n_companies": n_companies, "seed": seed}})


def simulate_reserves(n_companies: int, p_loss: float, alpha: float, xmin: float, cap: float, check: float,
                      reserve_fraction: float, follow_on_size: float, hit_rate: float, false_positive_rate: float,
                      breakout_multiple: float, follow_on_dilution: float, trials: int, seed: int) -> Dict[str, Any]:
    """Gross multiple under a follow-on reserve policy, under explicit selection assumptions.

    Reserve pool = ``reserve_fraction`` x initial capital. Each company that will reach
    ``breakout_multiple`` is identified with probability ``hit_rate``; others with
    ``false_positive_rate``. Identified companies get ``follow_on_size`` while the pool lasts,
    earning the company's multiple times ``follow_on_dilution`` (a higher entry price).
    The result depends entirely on those assumptions, which are returned with it.
    """
    _check(n_companies, p_loss, alpha, xmin, cap, trials)
    for name, v in (("reserve_fraction", reserve_fraction), ("hit_rate", hit_rate),
                    ("false_positive_rate", false_positive_rate), ("follow_on_dilution", follow_on_dilution)):
        if v < 0:
            raise ValueError(f"{name} cannot be negative")
    if hit_rate > 1 or false_positive_rate > 1:
        raise ValueError("rates must be at most 1")
    if check <= 0 or follow_on_size <= 0:
        raise ValueError("check and follow_on_size must be positive")
    pool = reserve_fraction * n_companies * check
    max_follow_ons = int(pool // follow_on_size)
    vals: List[float] = []
    deployed_share: List[float] = []
    for t in range(trials):
        rng = random.Random(f"{seed}-{t}")
        ms = [_company_multiple(rng, p_loss, alpha, xmin, cap) for _ in range(n_companies)]
        flagged = [i for i, m in enumerate(ms)
                   if rng.random() < (hit_rate if m >= breakout_multiple else false_positive_rate)]
        chosen = flagged[:max_follow_ons]
        initial = n_companies * check
        deployed = initial + len(chosen) * follow_on_size
        proceeds = sum(check * m for m in ms) + sum(follow_on_size * ms[i] * follow_on_dilution for i in chosen)
        vals.append(proceeds / deployed)
        deployed_share.append(deployed / (initial + pool) if initial + pool else 0.0)
    return _summary(vals, {"mean_share_of_total_capital_deployed": sum(deployed_share) / trials,
                           "max_follow_ons": max_follow_ons,
                           "assumptions": {"n_companies": n_companies, "p_loss": p_loss, "alpha": alpha, "xmin": xmin,
                                           "cap": cap, "check": check, "reserve_fraction": reserve_fraction,
                                           "follow_on_size": follow_on_size, "hit_rate": hit_rate,
                                           "false_positive_rate": false_positive_rate,
                                           "breakout_multiple": breakout_multiple,
                                           "follow_on_dilution": follow_on_dilution, "seed": seed,
                                           "note": "illustrative: selection skill and dilution are assumed, not estimated"}})


def reserve_policy_table(fractions: Sequence[float], **params: Any) -> Dict[float, Dict[str, Any]]:
    """Compare reserve fractions on identical simulated outcomes (common random numbers)."""
    return {f: simulate_reserves(reserve_fraction=f, **params) for f in fractions}
