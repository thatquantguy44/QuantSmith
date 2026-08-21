# Spec: FRED Point-In-Time Panel Adapter

- **ID:** 0045-fred-point-in-time
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-12

## Problem & Context

Spec `0044` shipped a backtest engine whose no-look-ahead guarantee is
structural — but it covers the *simulation loop only*. It cannot
establish that the weights it was handed were built without look-ahead,
and stated that limit plainly. For a macro backtest, that limit is where
almost all real leakage lives: economic series are **revised**, and a
backtest that reads today's revised GDP while pretending to trade in 2015
is silently using information that did not exist.

`joshualutkemuller/fred-bronze-to-gold-pipeline` already solves the hard
half. Its `gold_fred_point_in_time` table carries FRED's true vintage
columns:

```sql
gold_fred_point_in_time(
  series_id TEXT, observation_date TEXT, realtime_start TEXT,
  realtime_end TEXT, value REAL, revision_number INTEGER,
  is_missing INTEGER, ingested_at TEXT)
```

`realtime_start` / `realtime_end` bound the window during which a given
value *was* the published value for that observation date. Reading them
correctly is the difference between a leak-free macro backtest and the
usual one.

This spec adds the adapter that reads that table and produces a
vintage-correct panel the `0044` engine can consume, closing the gap
between "the engine doesn't leak" and "the inputs don't either".

## Goals

- Add `src/quantsmith/pipelines/fred_point_in_time.py`: load
  `gold_fred_point_in_time` rows from the pipeline's local SQLite output
  (stdlib `sqlite3`, no new dependency) and answer vintage-correct
  questions about them.
- `as_of_value`: the value for a given `(series_id, observation_date)` **as
  it was published on a given as-of date** — the vintage active then, not
  the latest revision.
- `as_of_snapshot`: for each series, the most recent observation whose
  value was actually *known* by the as-of date, respecting publication lag.
- `build_panel` / `panel_to_returns`: assemble an as-of-date-indexed panel
  and convert it to period returns, shaped to drop straight into
  `run_backtest`.
- Prove the property that matters with a revision fixture: a series
  revised after the fact must return its **original** value for an as-of
  date before the revision, never the revised one.

## Non-Goals

- **No data fetching and no API key.** This slice reads a SQLite file the
  operator produced by running the FRED pipeline locally; the
  `FRED_API_KEY` stays with them and never enters this repository (P9),
  matching the boundary `0039` and `adapters/alert_delivery/` already draw.
- **No signal logic.** Producing weights from the panel is `0001`/`0006`/
  `0041`/`0007`'s job; this supplies leak-free inputs.
- **No writing to the FRED database.** Read-only; this SDK does not own
  that pipeline's schema and must not migrate it.
- **No re-implementation of the gold layer.** The upstream pipeline owns
  bronze→silver→gold; this reads the published contract.
- **No other gold tables in this slice.** `gold_fred_macro_feature_daily`
  and the curve/spread tables are richer but derived; the point-in-time
  table is the one that carries the vintage guarantee.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `load_observations` shall read `gold_fred_point_in_time` from a SQLite file into typed records, optionally filtered by series, and shall not write to the database. | must |
| REQ-002 | `as_of_value` shall return the value whose `[realtime_start, realtime_end]` window contains the as-of date, and `None` when no vintage was published by then. | must |
| REQ-003 | `as_of_snapshot` shall return, per series, the most recent `observation_date` whose value was known as of the given date — never an observation published later. | must |
| REQ-004 | Rows flagged `is_missing` shall be treated as absent, not as a zero or a stale carry-forward. | must |
| REQ-005 | `build_panel` shall produce an as-of-date-indexed matrix of series values, and `panel_to_returns` shall convert consecutive panel levels to period returns aligned for `run_backtest`. | must |
| REQ-006 | A missing database file, a missing table, or an empty result shall raise a clear, named error rather than silently returning an empty panel. | must |
| REQ-007 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | The same database and arguments always produce the same panel. |
| NFR-002 | Dependency isolation | Standard library only (`sqlite3`, `datetime`). |
| NFR-003 | Read-only | The adapter opens the database in a read-only mode and issues no DDL or DML. |
| NFR-004 | Repository hygiene | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`, `backtest` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a fixture database mirroring the real DDL, when `load_observations` runs, then every row is returned as a typed record with dates parsed. | REQ-001 |
| AC-002 | Given a series whose value for an observation date was revised later, when `as_of_value` is asked for a date **before** the revision, then it returns the original value, not the revised one. | REQ-002 |
| AC-003 | Given the same series, when asked for a date **after** the revision, then it returns the revised value. | REQ-002 |
| AC-004 | Given an as-of date before any vintage was published, when `as_of_value` runs, then it returns `None`. | REQ-002 |
| AC-005 | Given an observation published with a lag, when `as_of_snapshot` runs for a date inside that lag, then the observation is absent from the snapshot. | REQ-003 |
| AC-006 | Given a row flagged `is_missing`, when the snapshot is built, then that series has no value rather than a zero. | REQ-004 |
| AC-007 | Given a panel of levels, when `panel_to_returns` runs, then each return equals the period-over-period change of the point-in-time levels. | REQ-005 |
| AC-008 | Given a panel built from the fixture, when it is fed to `run_backtest`, then the backtest completes and its periods align with the panel. | REQ-005 |
| AC-009 | Given a nonexistent database path or a database without the table, when `load_observations` runs, then it raises an error naming the problem. | REQ-006 |
| AC-010 | Given the adapter and a fixture database, when the same call is made twice, then the results are identical. | NFR-001 |
| AC-011 | Given the three catalogs, when inspected, then each lists spec `0045` and `fred_point_in_time.py`. | REQ-007 |

## Data & Dependencies

Reads the local SQLite output of
`joshualutkemuller/fred-bronze-to-gold-pipeline`
(`python -m fred_pipeline run --local --db-path fred_local.db`),
specifically `gold_fred_point_in_time`. Produced by the operator; this
repository holds neither the key nor the data. Standard library only.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The upstream gold schema changes and the adapter silently reads the wrong columns. | A panel that looks fine but is wrong. | Column names are asserted at load time against the expected set, and a mismatch raises rather than degrading (REQ-006). The upstream DDL is quoted in `plan.md` so a drift is visible in review. |
| RISK-002 | `realtime_end` conventions differ (open-ended vintages may use a sentinel far-future date, or `NULL`). | An active vintage could be excluded, returning `None` where a value exists. | Both are handled: a `NULL` or empty `realtime_end` is treated as open-ended. Covered by a fixture case. |
| RISK-003 | A user builds a panel over as-of dates denser than the series' true publication frequency and reads carried-forward values as new information. | Apparent signal that is actually a flat line resampled. | `as_of_snapshot` returns the observation date alongside the value, so a caller can see staleness; the limitation is stated in the module docstring rather than hidden. |
| RISK-004 | The adapter guarantees vintage-correct *inputs*, but a caller can still construct a leaky signal from them. | Leakage re-enters downstream. | Same honest boundary `0044` drew: stated in the docstring. The `leakage` gate and `instructions/point_in_time.md` remain the backstop. |

## Assumptions & Open Questions

- Assumption: `realtime_start`/`realtime_end` follow FRED's convention —
  inclusive bounds on the window during which a value was current.
- Assumption: reading a SQLite file the operator produced is the right
  boundary, keeping the API key and any usage limits with them.
- Open question: should a later slice also consume
  `gold_fred_macro_feature_daily` for pre-computed transforms, once the
  point-in-time path is trusted end to end?

## Exceptions

None.
