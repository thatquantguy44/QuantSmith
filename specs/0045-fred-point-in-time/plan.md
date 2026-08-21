# Plan: FRED Point-In-Time Panel Adapter

- **Spec:** 0045-fred-point-in-time (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-12

## Approach

One new module, `src/quantsmith/pipelines/fred_point_in_time.py`,
standard library only (`sqlite3`, `datetime`). Read-only against the FRED
pipeline's local SQLite output; produces a vintage-correct panel shaped
for `backtesting.run_backtest` (`0044`). Neither `backtesting.py` nor the
upstream pipeline is modified.

## Architecture & Components

The upstream contract this reads, quoted so a schema drift is visible in
review (`fred_pipeline/io/local_store.py`):

```sql
CREATE TABLE IF NOT EXISTS gold_fred_point_in_time (
    series_id TEXT, observation_date TEXT, realtime_start TEXT, realtime_end TEXT,
    value REAL, revision_number INTEGER, is_missing INTEGER, ingested_at TEXT
);
```

```text
fred_point_in_time.py
  PitObservation  -- series_id, observation_date (date), realtime_start (date),
                     realtime_end (date | None = open-ended), value (float | None),
                     revision_number (int), is_missing (bool)

  load_observations(db_path, series_ids=None, table="gold_fred_point_in_time")
      open sqlite3 in read-only URI mode          (NFR-003)
      verify the table exists and its columns cover the expected set,
          else raise FredPitError                  (REQ-006 / RISK-001)
      parse ISO date strings; empty/NULL realtime_end -> None (open-ended)

  as_of_value(observations, series_id, observation_date, as_of)
      # the vintage whose window contains as_of:
      #   realtime_start <= as_of <= (realtime_end or +inf)
      # ties broken by the highest revision_number
      # is_missing rows are skipped entirely       (REQ-004)
      -> float | None                              (REQ-002)

  as_of_snapshot(observations, as_of, series_ids=None)
      # per series, the LATEST observation_date whose value was known by
      # as_of -- i.e. some vintage with realtime_start <= as_of.
      # Publication lag falls out of the data: an observation whose first
      # vintage starts after as_of simply is not visible yet. (REQ-003)
      -> {series_id: SnapshotEntry(observation_date, value)}

  build_panel(observations, as_of_dates, series_ids)
      -> PanelResult(as_of_dates, series_ids, values: Matrix,
                     observation_dates: Matrix)     (REQ-005)
      # observation_dates travel alongside the values so a caller can see
      # staleness rather than mistaking a carry-forward for news (RISK-003)

  panel_to_returns(panel)
      -> Matrix of period-over-period changes, len == len(as_of_dates) - 1
      # aligned so returns[k] is the change into as_of_dates[k+1]
```

## Interfaces & Data Contracts

Consumes the upstream gold table (read-only, quoted above). Produces
plain `List`/`Matrix` structures matching the `Vector`/`Matrix`
convention used across `pipelines/`, so `panel_to_returns` output feeds
`run_backtest` with no adapter in between.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Vintage selection is a window containment test on the data's own `realtime_start`/`realtime_end`; there is no path that returns a later revision for an earlier as-of date. |
| P9 No credentials | yes | Reads a file the operator produced. The `FRED_API_KEY` never enters this repository — the same boundary `0039` and `alert_delivery` draw. |
| P10 Honest reporting | yes | `as_of_snapshot` returns the observation date with the value so staleness is visible; RISK-004 states plainly that leak-free inputs do not prevent a caller building a leaky signal from them. |
| P5 Reversibility | yes | Additive, read-only; no existing module or upstream schema changes. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `load_observations`, `PitObservation` | T-001 |
| REQ-002 | `as_of_value` window containment | T-001 |
| REQ-003 | `as_of_snapshot` latest-known selection | T-001 |
| REQ-004 | `is_missing` rows skipped | T-001 |
| REQ-005 | `build_panel`, `panel_to_returns` | T-001 |
| REQ-006 | Table/column verification, `FredPitError` | T-001 |
| REQ-007 | Three catalogs | T-003 |
| NFR-001 – NFR-003 | Pure functions, stdlib, read-only URI | T-001 |
| NFR-004 | Validation gates | T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Data boundary | Read a SQLite file the operator produced | Call the FRED API from this repo | P9: this SDK holds no credentials. It also keeps rate limits and usage with the key's owner, and makes the run reproducible from a fixed file rather than a live endpoint. |
| Vintage selection | Window containment on `realtime_start`/`realtime_end` | Take `max(revision_number)` at or before the as-of date | Revision number orders revisions but does not say *when* each became current; only the realtime window answers "what was published then". Revision number is used solely to break ties inside one window. |
| Open-ended vintages | `NULL`/empty `realtime_end` treated as open | Require a sentinel far-future date | Both conventions appear in FRED-derived data; treating absent as open-ended avoids silently excluding the currently-active vintage (RISK-002). |
| Missing values | `is_missing` rows skipped entirely | Carry forward, or substitute zero | A zero is a number a model will happily trade on; absence is the truth. Carry-forward is the caller's choice to make explicitly, not the adapter's to make silently. |
| Staleness | Return observation dates alongside values | Return values only | Without the observation date a caller cannot tell a fresh print from a three-month-old one resampled daily (RISK-003). |

## Validation Strategy

`tests/test_fred_point_in_time.py` builds a **temporary SQLite fixture
mirroring the upstream DDL exactly**, including a revised series, an
open-ended vintage, a publication-lagged observation, and an
`is_missing` row. One test per acceptance criterion (AC-001 – AC-010).

The decisive test is AC-002/AC-003: a series revised after the fact must
return its *original* value for an as-of date before the revision and the
revised value after — that single property is what separates a leak-free
macro backtest from the usual one. AC-008 feeds the resulting panel
through `run_backtest` to prove the two modules compose. Then the
documentation gate set plus `backtest`, the full `pytest tests/ -q`, and
`git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit and push. Rollback is reverting the commit; no
existing module or upstream schema changes. The real run remains blocked
on the operator producing `fred_local.db`; this module is what makes that
step a wiring exercise.

## Open Questions

- Should a later slice consume `gold_fred_macro_feature_daily` for
  pre-computed transforms once this path is trusted? (Carried from
  `spec.md`.)
