"""Synthetic transaction data with planted, known structure. Spec ``0099`` (tests, example, benchmark).

Every effect here is planted on purpose so a test can check the investigator
finds it — or, for the overnight window, rejects the tempting explanation:

* ``region`` = international has a fraud rate 5.7× domestic, at every hour and amount;
* hours 1–4 carry 62% less volume than other hours while fraud *volume* per hour
  is flat, so the overnight fraud *rate* is higher only because the denominator
  is smaller;
* ``amount`` rises by half after ``SHIFT_DAY`` (a dated regime shift);
* rows with ``device_id`` missing (18%) have twice the fraud rate;
* ``balance`` is correlated with ``amount``.

Synthetic data only (spec ``0025`` disclosure); no real customer, account or transaction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

START = pd.Timestamp("2026-01-01")
DAYS = 120
SHIFT_DAY = 80
OVERNIGHT = (1, 2, 3, 4)
OVERNIGHT_WEIGHT = 0.38          # volume per overnight hour relative to other hours (62% less)
DOMESTIC_RATE = 0.012
INTERNATIONAL_RATIO = 5.7
INTERNATIONAL_SHARE = 0.08
DEVICE_MISSING_SHARE = 0.18
DEVICE_MISSING_RATIO = 2.0
COUNTRIES = ("US", "CA", "GB", "DE", "FR", "MX")
NOTES = ("customer paid at checkout", "recurring monthly subscription charge", "refund issued after review",
         "card present purchase at store", "online order shipped to home", "transfer between own accounts")
SENTINEL = "ZZ-SENTINEL-7d3f"


def transactions(rows: int = 30_000, seed: int = 7, *, sentinel: bool = False) -> pd.DataFrame:
    """A synthetic transaction table with the planted effects listed in the module docstring."""
    rng = np.random.default_rng(seed)
    weights = np.array([OVERNIGHT_WEIGHT if h in OVERNIGHT else 1.0 for h in range(24)])
    hours = rng.choice(24, size=rows, p=weights / weights.sum())
    days = rng.integers(0, DAYS, size=rows)
    minutes = rng.integers(0, 60, size=rows)
    ts = START + pd.to_timedelta(days, unit="D") + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m")
    international = rng.random(rows) < INTERNATIONAL_SHARE
    country = np.where(international, rng.choice(COUNTRIES[2:], size=rows), rng.choice(COUNTRIES[:2], size=rows))
    amount = rng.lognormal(mean=3.6, sigma=0.9, size=rows) * np.where(days >= SHIFT_DAY, 1.5, 1.0)
    balance = amount * 4 + rng.normal(0, 60, size=rows) + 500
    velocity = rng.gamma(2.0, 1.5, size=rows)
    device_missing = rng.random(rows) < DEVICE_MISSING_SHARE
    device = np.where(device_missing, None, rng.choice(["ios", "android", "web"], size=rows)).astype(object)
    # Hour factor keeps fraud volume per hour flat: rate ∝ 1 / volume weight, mean 1 over rows.
    hour_factor = (weights.sum() / 24) / weights[hours]
    rate = DOMESTIC_RATE * np.where(international, INTERNATIONAL_RATIO, 1.0) * hour_factor
    rate = rate * np.where(device_missing, DEVICE_MISSING_RATIO, 1.0) / (1 + DEVICE_MISSING_SHARE * (DEVICE_MISSING_RATIO - 1))
    is_fraud = (rng.random(rows) < np.clip(rate, 0, 1)).astype(int)
    customers = rng.integers(0, 1500, size=rows)
    df = pd.DataFrame({
        "transaction_id": [f"T{i:07d}" for i in range(rows)],
        "customer_id": [f"C{c:05d}" for c in customers],
        "transaction_date": ts,
        "amount": np.round(amount, 2),
        "balance": np.round(balance, 2),
        "velocity_24h": np.round(velocity, 3),
        "country": country,
        "region": np.where(international, "international", "domestic"),
        "device_id": device,
        "note": rng.choice(NOTES, size=rows),
        "is_fraud": is_fraud,
    })
    order = np.argsort(ts.values, kind="stable")
    df = df.iloc[order].reset_index(drop=True)
    df["transaction_id"] = [f"T{i:07d}" for i in range(rows)]
    if sentinel:
        df.loc[17, "transaction_id"] = SENTINEL
        df.loc[23, "note"] = f"customer note {SENTINEL} please call back"
    return df


def quality_defects(seed: int = 3) -> pd.DataFrame:
    """A small table with planted quality defects and their exact counts (see ``QUALITY_COUNTS``)."""
    rng = np.random.default_rng(seed)
    n = 200
    df = pd.DataFrame({
        "order_id": [f"O{i:05d}" for i in range(n)],
        "order_date": pd.date_range("2026-01-01", periods=n, freq="h"),
        "amount": np.round(rng.lognormal(3, 0.5, n), 2),
        "status": rng.choice(["open", "closed", "pending"], size=n),
        "region": ["north"] * n,
        "channel": ["web"] * 198 + ["phone"] * 2,
        "code": [str(i) if i % 4 else f"X{i}" for i in range(n)],
    })
    df.loc[[5, 9, 13], "amount"] = [-10.0, -3.5, -1.0]
    df.loc[[40, 41], "order_date"] = pd.Timestamp("2031-01-01")
    df.loc[[60, 61, 62, 63], "order_id"] = "O00001"
    dupes = df.iloc[[100, 101]].copy()
    df = pd.concat([df, dupes], ignore_index=True)
    return df


QUALITY_COUNTS = {
    "duplicate_rows": 2,           # rows 100 and 101 appended again
    "duplicate_order_ids": 6,      # 4 rows reuse O00001 (1 + 4 → 4 repeats) plus the 2 appended duplicates
    "constant": ["region"],
    "near_constant": ["channel"],  # 198 of 202 = 98.0% … see test for the threshold used
    "negative_amount": 3,
    "future_dates": 2,             # with as_of 2026-12-31
    "mixed_type_column": "code",   # 50 of 200 non-numeric
}


def wide(rows: int = 1_000_000, seed: int = 11) -> pd.DataFrame:
    """The transaction table plus nine more columns: 20 columns in all (benchmark shape, AC-021)."""
    df = transactions(rows, seed)
    rng = np.random.default_rng(seed + 1)
    for i in range(5):
        df[f"feature_{i}"] = np.round(rng.normal(100 + 10 * i, 15, rows), 3)
    for i in range(4):
        df[f"segment_{i}"] = rng.choice([f"s{j}" for j in range(4 + i)], size=rows)
    return df
