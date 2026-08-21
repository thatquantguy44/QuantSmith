"""Acceptance tests for spec 0045 -- FRED point-in-time panel adapter.

The fixture mirrors the upstream DDL from
``fred_pipeline/io/local_store.py`` exactly, so a schema drift shows up here.

Each test is named for the acceptance criterion it covers (see
``specs/0045-fred-point-in-time/tasks.md``).
"""

from __future__ import annotations

import datetime
import sqlite3

import pytest

from quantsmith.pipelines.backtesting import BacktestConfig, run_backtest
from quantsmith.pipelines.fred_point_in_time import (
    FredPitError,
    as_of_snapshot,
    as_of_value,
    build_panel,
    load_observations,
    panel_to_returns,
)

DDL = """
CREATE TABLE IF NOT EXISTS gold_fred_point_in_time (
    series_id TEXT, observation_date TEXT, realtime_start TEXT, realtime_end TEXT,
    value REAL, revision_number INTEGER, is_missing INTEGER, ingested_at TEXT
);
"""

D = datetime.date

# (series, observation_date, realtime_start, realtime_end, value, revision, is_missing)
ROWS = [
    # GDPX for 2026-01-01: first published 2026-02-01 at 100.0, revised
    # 2026-03-01 to 105.0. This pair is the whole point of the module.
    ("GDPX", "2026-01-01", "2026-02-01", "2026-02-28", 100.0, 0, 0),
    ("GDPX", "2026-01-01", "2026-03-01", None, 105.0, 1, 0),
    # A later observation, published with a lag: not visible before 2026-04-01.
    ("GDPX", "2026-02-01", "2026-04-01", None, 110.0, 0, 0),
    # A second series with an open-ended vintage from the start.
    ("CPIX", "2026-01-01", "2026-01-15", None, 50.0, 0, 0),
    ("CPIX", "2026-02-01", "2026-02-15", None, 55.0, 0, 0),
    # A missing-flagged row: must behave as absent, never as a zero.
    ("NILX", "2026-01-01", "2026-01-15", None, None, 0, 1),
]


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "fred_local.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(DDL)
    conn.executemany(
        "INSERT INTO gold_fred_point_in_time "
        "(series_id, observation_date, realtime_start, realtime_end, value, "
        "revision_number, is_missing, ingested_at) VALUES (?,?,?,?,?,?,?,'2026-08-12')",
        ROWS,
    )
    conn.commit()
    conn.close()
    return str(path)


# --- AC-001: rows load as typed records ---


def test_load_observations_parses_rows_AC_001(db):
    obs = load_observations(db)
    assert len(obs) == len(ROWS)
    first = next(o for o in obs if o.series_id == "GDPX" and o.revision_number == 0)
    assert first.observation_date == D(2026, 1, 1)
    assert first.realtime_start == D(2026, 2, 1)
    assert first.realtime_end == D(2026, 2, 28)
    assert first.value == 100.0

    # An empty/NULL realtime_end is normalised to open-ended.
    revised = next(o for o in obs if o.series_id == "GDPX" and o.revision_number == 1)
    assert revised.realtime_end is None

    # Filtering by series works.
    assert {o.series_id for o in load_observations(db, series_ids=["CPIX"])} == {"CPIX"}


# --- AC-002: before the revision, the ORIGINAL value (the decisive property) ---


def test_pre_revision_returns_original_value_AC_002(db):
    obs = load_observations(db)
    value = as_of_value(obs, "GDPX", D(2026, 1, 1), as_of=D(2026, 2, 15))
    assert value == 100.0, "a revision published later must never leak backwards"


# --- AC-003: after the revision, the revised value ---


def test_post_revision_returns_revised_value_AC_003(db):
    obs = load_observations(db)
    assert as_of_value(obs, "GDPX", D(2026, 1, 1), as_of=D(2026, 3, 15)) == 105.0


# --- AC-004: before any publication, nothing ---


def test_before_first_publication_returns_none_AC_004(db):
    obs = load_observations(db)
    assert as_of_value(obs, "GDPX", D(2026, 1, 1), as_of=D(2026, 1, 20)) is None


# --- AC-005: publication lag hides a later observation ---


def test_publication_lag_hides_observation_AC_005(db):
    obs = load_observations(db)

    # The 2026-02-01 print is not published until 2026-04-01.
    mid_march = as_of_snapshot(obs, D(2026, 3, 15), ["GDPX"])
    assert mid_march["GDPX"].observation_date == D(2026, 1, 1)
    assert mid_march["GDPX"].value == 105.0

    after = as_of_snapshot(obs, D(2026, 4, 2), ["GDPX"])
    assert after["GDPX"].observation_date == D(2026, 2, 1)
    assert after["GDPX"].value == 110.0


# --- AC-006: a missing-flagged row is absent, not zero ---


def test_missing_flag_yields_no_value_AC_006(db):
    obs = load_observations(db)
    snapshot = as_of_snapshot(obs, D(2026, 6, 1), ["NILX"])
    assert "NILX" not in snapshot
    assert as_of_value(obs, "NILX", D(2026, 1, 1), as_of=D(2026, 6, 1)) is None


# --- AC-007: returns are period-over-period changes of PIT levels ---


def test_panel_to_returns_AC_007(db):
    obs = load_observations(db)
    panel = build_panel(obs, [D(2026, 2, 20), D(2026, 3, 15)], ["CPIX"])

    # CPIX: 50.0 known on 2026-02-20 (the 2026-02-01 print lands 2026-02-15)...
    assert panel.values[0][0] == 55.0
    assert panel.values[1][0] == 55.0

    returns = panel_to_returns(panel)
    assert len(returns) == len(panel.as_of_dates) - 1
    assert returns[0][0] == pytest.approx(0.0)

    # A real move across a revision boundary is picked up.
    gdp_panel = build_panel(obs, [D(2026, 2, 15), D(2026, 3, 15)], ["GDPX"])
    assert gdp_panel.values[0][0] == 100.0
    assert gdp_panel.values[1][0] == 105.0
    assert panel_to_returns(gdp_panel)[0][0] == pytest.approx(0.05)


# --- AC-008: the panel composes with the 0044 backtest engine ---


def test_panel_feeds_backtest_AC_008(db):
    obs = load_observations(db)
    as_of_dates = [D(2026, 2, 15), D(2026, 3, 15), D(2026, 4, 2), D(2026, 5, 1)]
    panel = build_panel(obs, as_of_dates, ["GDPX", "CPIX"])
    returns = panel_to_returns(panel)

    weights = [[0.5, 0.5] for _ in range(len(returns) - 1)]
    result = run_backtest(
        weights, returns, BacktestConfig(transaction_cost_bps=1.0, periods_per_year=12)
    )

    assert len(result.periods) == len(weights)
    assert result.equity_curve


# --- AC-009: a bad path or table raises, never silently empties ---


def test_missing_db_or_table_raises_AC_009(db, tmp_path):
    with pytest.raises(FredPitError, match="not found"):
        load_observations(str(tmp_path / "nope.db"))

    empty = tmp_path / "empty.db"
    sqlite3.connect(str(empty)).close()
    with pytest.raises(FredPitError, match="table"):
        load_observations(str(empty))

    with pytest.raises(FredPitError, match="table"):
        load_observations(db, table="gold_does_not_exist")


# --- AC-010: deterministic ---


def test_deterministic_AC_010(db):
    a = load_observations(db)
    b = load_observations(db)
    assert a == b

    dates = [D(2026, 2, 15), D(2026, 3, 15)]
    pa = build_panel(a, dates, ["GDPX", "CPIX"])
    pb = build_panel(b, dates, ["GDPX", "CPIX"])
    assert pa == pb
    assert panel_to_returns(pa) == panel_to_returns(pb)
