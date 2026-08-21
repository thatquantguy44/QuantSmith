"""Reference pipeline for spec 0045 -- FRED point-in-time panel adapter.

Spec ``0044``'s backtest engine guarantees its own simulation loop does not
look ahead, and says plainly that the guarantee stops there: it cannot vouch
for the weights it is handed. For a macro backtest that limit is where nearly
all real leakage lives, because economic series are **revised**. A backtest
that reads today's revised GDP while pretending to trade in 2015 is using a
number that did not exist then.

``joshualutkemuller/fred-bronze-to-gold-pipeline`` already solves the hard
half: its ``gold_fred_point_in_time`` table carries FRED's true vintage
columns, ``realtime_start`` and ``realtime_end``, which bound the window during
which a value *was* the published figure for an observation date. This module
reads that table and answers vintage-correct questions against it, so the
inputs to a backtest are as leak-free as the loop consuming them.

The decisive behaviour: ask for a series' value as of a date **before** a later
revision, and you get the number that was actually published then -- never the
revision.

Two boundaries are deliberate:

* **No credentials, no fetching.** This reads a SQLite file the operator
  produced by running that pipeline locally. The ``FRED_API_KEY`` stays with
  them and never enters this repository (P9), the same boundary ``0039`` and
  ``adapters/alert_delivery/`` draw.

* **Leak-free inputs are not a leak-free signal.** This module can hand a
  caller honest data; it cannot stop that caller building a look-ahead signal
  from it. ``instructions/point_in_time.md`` and the ``leakage`` gate remain
  the backstop.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

DEFAULT_TABLE = "gold_fred_point_in_time"

_EXPECTED_COLUMNS = {
    "series_id",
    "observation_date",
    "realtime_start",
    "realtime_end",
    "value",
    "revision_number",
    "is_missing",
}

Matrix = List[List[Optional[float]]]


class FredPitError(RuntimeError):
    """Raised when the point-in-time source cannot be read as expected."""


@dataclass(frozen=True)
class PitObservation:
    """One published vintage of one observation.

    ``realtime_end`` of ``None`` means the vintage is still current (the
    upstream data uses either a NULL/empty value or a far-future sentinel;
    both are normalised to ``None`` here).
    """

    series_id: str
    observation_date: datetime.date
    realtime_start: datetime.date
    realtime_end: Optional[datetime.date]
    value: Optional[float]
    revision_number: int = 0
    is_missing: bool = False

    def active_on(self, as_of: datetime.date) -> bool:
        """Was this the published vintage on ``as_of``?"""
        if as_of < self.realtime_start:
            return False
        return self.realtime_end is None or as_of <= self.realtime_end

    def known_by(self, as_of: datetime.date) -> bool:
        """Had this vintage been published by ``as_of``?"""
        return self.realtime_start <= as_of


@dataclass(frozen=True)
class SnapshotEntry:
    """A series' latest known value on an as-of date, with its vintage date.

    ``observation_date`` travels with the value so a caller can see staleness
    — a three-month-old print resampled daily is not new information, and
    without the date it looks identical to a fresh one.
    """

    observation_date: datetime.date
    value: float


@dataclass(frozen=True)
class PanelResult:
    as_of_dates: List[datetime.date]
    series_ids: List[str]
    values: Matrix
    observation_dates: List[List[Optional[datetime.date]]]


# ---------------------------------------------------------------------------
# Loading -- REQ-001 / REQ-006
# ---------------------------------------------------------------------------


def _parse_date(raw: object) -> Optional[datetime.date]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None


def load_observations(
    db_path: str,
    series_ids: Optional[Sequence[str]] = None,
    table: str = DEFAULT_TABLE,
) -> List[PitObservation]:
    """Read point-in-time rows from the pipeline's local SQLite output.

    Opened read-only; issues no DDL or DML. Raises ``FredPitError`` rather than
    degrading if the file, the table, or the expected columns are absent — a
    silently empty panel would be worse than a failure.
    """
    if not os.path.exists(db_path):
        raise FredPitError(f"database file not found: {db_path}")

    uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:  # pragma: no cover - environment dependent
        raise FredPitError(f"could not open {db_path} read-only: {exc}") from exc

    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cur.fetchone() is None:
            raise FredPitError(f"table {table!r} not found in {db_path}")

        cur.execute(f"PRAGMA table_info({table})")
        present = {row[1] for row in cur.fetchall()}
        missing = _EXPECTED_COLUMNS - present
        if missing:
            raise FredPitError(
                f"table {table!r} is missing expected column(s): "
                f"{', '.join(sorted(missing))} — upstream schema may have changed"
            )

        sql = (
            f"SELECT series_id, observation_date, realtime_start, realtime_end, "
            f"value, revision_number, is_missing FROM {table}"
        )
        params: Tuple[object, ...] = ()
        if series_ids:
            placeholders = ",".join("?" for _ in series_ids)
            sql += f" WHERE series_id IN ({placeholders})"
            params = tuple(series_ids)
        cur.execute(sql, params)
        rows = cur.fetchall()
    finally:
        conn.close()

    observations: List[PitObservation] = []
    for series_id, obs_raw, rt_start_raw, rt_end_raw, value, revision, missing_flag in rows:
        obs_date = _parse_date(obs_raw)
        rt_start = _parse_date(rt_start_raw)
        if obs_date is None or rt_start is None:
            continue  # a row without an observation or publication date says nothing
        observations.append(
            PitObservation(
                series_id=str(series_id),
                observation_date=obs_date,
                realtime_start=rt_start,
                realtime_end=_parse_date(rt_end_raw),
                value=None if value is None else float(value),
                revision_number=int(revision or 0),
                is_missing=bool(missing_flag),
            )
        )
    return observations


# ---------------------------------------------------------------------------
# Vintage-correct access -- REQ-002 / REQ-003 / REQ-004
# ---------------------------------------------------------------------------


def _usable(obs: PitObservation) -> bool:
    """A missing-flagged or null row is absent, never a zero (REQ-004)."""
    return not obs.is_missing and obs.value is not None


def as_of_value(
    observations: Sequence[PitObservation],
    series_id: str,
    observation_date: datetime.date,
    as_of: datetime.date,
) -> Optional[float]:
    """The value published for ``observation_date`` as it stood on ``as_of``.

    Selected by window containment on the vintage's own
    ``realtime_start``/``realtime_end`` — so a revision published after
    ``as_of`` can never be returned. Ties inside one window break on the
    highest ``revision_number``. Returns ``None`` when nothing had been
    published by then.
    """
    candidates = [
        o
        for o in observations
        if o.series_id == series_id
        and o.observation_date == observation_date
        and o.active_on(as_of)
        and _usable(o)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda o: o.revision_number).value


def as_of_snapshot(
    observations: Sequence[PitObservation],
    as_of: datetime.date,
    series_ids: Optional[Sequence[str]] = None,
) -> Dict[str, SnapshotEntry]:
    """Per series, the latest observation whose value was known by ``as_of``.

    Publication lag falls out of the data rather than needing a parameter: an
    observation whose first vintage starts after ``as_of`` simply is not
    visible yet.
    """
    wanted = set(series_ids) if series_ids else None
    latest: Dict[str, SnapshotEntry] = {}

    for obs in observations:
        if wanted is not None and obs.series_id not in wanted:
            continue
        if not obs.known_by(as_of) or not obs.active_on(as_of) or not _usable(obs):
            continue
        current = latest.get(obs.series_id)
        if current is None or obs.observation_date > current.observation_date:
            latest[obs.series_id] = SnapshotEntry(obs.observation_date, obs.value)
    return latest


# ---------------------------------------------------------------------------
# Panel assembly -- REQ-005
# ---------------------------------------------------------------------------


def build_panel(
    observations: Sequence[PitObservation],
    as_of_dates: Sequence[datetime.date],
    series_ids: Sequence[str],
) -> PanelResult:
    """An as-of-date-indexed panel of point-in-time values.

    Observation dates travel alongside the values so staleness is visible to
    the caller instead of being indistinguishable from fresh data.
    """
    dates = list(as_of_dates)
    ids = list(series_ids)
    values: Matrix = []
    obs_dates: List[List[Optional[datetime.date]]] = []

    for as_of in dates:
        snapshot = as_of_snapshot(observations, as_of, ids)
        values.append([snapshot[s].value if s in snapshot else None for s in ids])
        obs_dates.append([snapshot[s].observation_date if s in snapshot else None for s in ids])

    return PanelResult(as_of_dates=dates, series_ids=ids, values=values, observation_dates=obs_dates)


def panel_to_returns(panel: PanelResult) -> List[List[float]]:
    """Period-over-period changes of the point-in-time levels.

    ``returns[k]`` is the change into ``as_of_dates[k + 1]``, so the result is
    one row shorter than the panel and drops straight into
    ``backtesting.run_backtest``. A period with a missing or non-positive prior
    level contributes ``0.0`` rather than a fabricated move.
    """
    out: List[List[float]] = []
    for k in range(1, len(panel.values)):
        prev_row = panel.values[k - 1]
        row = panel.values[k]
        out.append(
            [
                (curr / prev - 1.0)
                if (curr is not None and prev is not None and prev > 0)
                else 0.0
                for curr, prev in zip(row, prev_row)
            ]
        )
    return out
