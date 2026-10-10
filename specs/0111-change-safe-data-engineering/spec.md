# Spec: Change-safe data engineering

- **ID:** 0111-change-safe-data-engineering
- **Status:** Draft
- **Author:** QuantSmith
- **Approver:** (pending)
- **Last updated:** 2026-10-10

> WHAT and WHY only. Implementation lives in `plan.md`.
> Slice A of the data-engineering expansion (`docs/handoff.md` → reserved `0107`):
> correctness when data changes — streams, schemas, and restatements.

## Problem & Context

`0011` makes one batch pipeline correct, `0101` runs hundreds of them safely, and
`0102` records lineage and what was known when. None of them covers the moments a
quant data platform most often goes silently wrong:

- **Streams and CDC.** Connectors deliver insert/update/delete events at least
  once and not always in order. Applied naively, replays double-count and a stale
  update overwrites a newer one. Event-time aggregates (bars, VWAPs) are finalized
  while late prints can still arrive, and late prints are dropped without a trace.
- **Schema changes.** Vendors add, drop, rename, widen, or null-relax columns.
  Whether that is safe depends on whether readers or writers upgrade first, and
  drift is usually discovered after a backtest has already consumed it.
- **Restatements.** When a vendor restates a file, everything downstream is wrong.
  Teams recompute too little (stale tables), too much (wasted compute), or swap
  results in piecemeal so readers see half-old, half-new data.

## Goals

- Apply CDC events idempotently and order-safely, with replays and stale events
  counted rather than applied.
- Aggregate event-time windows under a watermark, account for every late event,
  and record restatements bitemporally.
- Classify every schema change by the direction it breaks, enforce a declared
  compatibility mode, read old data with a new schema safely, and detect drift in
  delivered rows before load.
- Plan exactly the reprocessing a restatement requires, execute it as new immutable
  versions under fleet limits, compare old and new, and publish all-or-nothing.

## Non-Goals

- A streaming engine, Kafka/Debezium client, or schema-registry server (adapters
  wrap those; this is the deterministic core).
- Sliding or session windows (tumbling windows in this slice).
- Automatic rename detection (a rename is a removal plus an addition).
- dbt, Spark, Ray/Dask, lakehouse formats, FinOps, and the reference-data pack
  (slices B and C of `0107`).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall apply CDC events so that replays and events older than a key's applied sequence are not applied, deletes are sequenced tombstones, and full-image events converge to the same table in any arrival order. | must |
| REQ-002 | The system shall emit an event-time window only when the watermark (max event time minus allowed lateness) passes its end, and account for every late event as a side output or a numbered restatement. | must |
| REQ-003 | The system shall record window revisions with the knowledge time they were emitted, writable to the `0102` bitemporal store. | should |
| REQ-004 | The system shall classify every field-level schema change (added, removed, type widened/narrowed/changed, nullability tightened/relaxed, default changed) with whether it breaks backward and/or forward compatibility. | must |
| REQ-005 | The system shall enforce a declared compatibility mode, find the first violating version in a history, and read old-schema rows with a new schema only when backward compatible. | must |
| REQ-006 | The system shall report delivered-row drift against a declared schema: unknown columns, missing required columns, nulls in non-nullable columns, and type mismatches, with counts. | must |
| REQ-007 | The system shall plan reprocessing for restated versions as exactly the runs downstream of them in the lineage graph, in dependency order. | must |
| REQ-008 | The system shall execute a plan under `0101` fleet limits, re-running each run against restated or re-computed inputs and writing new immutable versions with recorded lineage; failures isolate their dependents. | must |
| REQ-009 | The system shall compare old and new outputs by key and publish all superseding versions at once only when execution succeeded and every comparison passes its gate, returning the previous pointers. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Same inputs produce the same tables, windows, classifications, plans, and diffs. |
| NFR-002 | Point-in-time correctness | No late event or restatement is visible before its knowledge time. |
| NFR-003 | Honest reporting | Nothing is dropped silently: duplicates, stale events, late events, drift, and blocked swaps are all reported. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a CDC stream, when applied and then replayed, then the replay applies nothing; a stale update or insert does not overwrite or resurrect; full-image events in 50 shuffled orders with replays converge to one table. | REQ-001, NFR-001 |
| AC-002 | Given trades with in-lateness and too-late arrivals, when windowed, then windows emit only when the watermark passes their end, too-late events are in the side output, open windows are reported or flushed, and every event is accounted for. | REQ-002, NFR-003 |
| AC-003 | Given restate mode, when a late print arrives, then the window is re-emitted as revision 2; recorded bitemporally, an as-of read before the restatement sees revision 1 and after sees revision 2. | REQ-003, NFR-002 |
| AC-004 | Given two schema versions, when compared, then each change has the right kind and break directions (widening breaks forward only; required add breaks backward only; nullable removal breaks neither; tightening breaks backward). | REQ-004 |
| AC-005 | Given modes and a history, when checked, then violations are listed per change, the first violating version is found, and old rows read with a backward-compatible schema get defaults and promotions while a breaking schema is refused. | REQ-005 |
| AC-006 | Given delivered rows with type, null, missing, and unknown-column drift, when checked, then each is counted per column. | REQ-006, NFR-003 |
| AC-007 | Given lineage with an unrelated branch, when a source is restated, then the plan contains exactly the downstream runs in order and rejects invalid restatements. | REQ-007 |
| AC-008 | Given a plan, when executed under pool limits, then new versions are written with lineage tracing to the restated source, old versions are untouched, and a failing run marks its dependents `upstream_failed`. | REQ-008 |
| AC-009 | Given execution results, when swapping, then a failed run, failed gate, or missing comparison swaps nothing; a passing swap moves every superseded pointer and returns the previous ones. | REQ-009, NFR-003 |

## Data & Dependencies

- Runtimes: `src/quantsmith/pipelines/streaming_cdc.py`, `schema_evolution.py`,
  `reprocessing.py` (standard library only).
- Builds on `0011` (pipelines), `0101` (fleet limits), `0102` (lineage, bitemporal),
  `0039` (data contracts).
- Agents: new `data_engineering/streaming_cdc`, `data_engineering/schema_evolution`,
  `data_engineering/backfill_reprocessing`.
- Standard: `instructions/pipeline_engineering.md` → *Change-Safe Pipelines*.
- No private data or credentials are written to this repository.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Replayed CDC events double-apply. | Inflated positions or volumes. | Per-key applied sequence (AC-001). |
| RISK-002 | Partial-update CDC delivered out of order merges into a wrong row. | Silent field-level corruption. | Documented: partial updates are order-safe only in sequence; prefer full images (AC-001). |
| RISK-003 | Late prints silently dropped or visible before arrival. | Wrong bars; look-ahead in backtests. | Side output or restatement; bitemporal recording (AC-002, AC-003). |
| RISK-004 | A breaking schema change ships unnoticed. | Loads fail or, worse, mis-parse. | Mode enforcement and drift detection (AC-005, AC-006). |
| RISK-005 | Reprocessing misses or over-reaches downstream. | Stale tables or wasted compute. | Lineage-derived plan (AC-007). |
| RISK-006 | Readers see half-old, half-new data. | Inconsistent research and reports. | All-or-nothing swap with gates; rollback pointers (AC-009). |

## Assumptions & Open Questions

- Assumption: CDC sources provide a per-key monotonic sequence (LSN, offset, version).
- Assumption: transforms re-run deterministically given their inputs and code version.
- Open question: sliding/session windows; a schema-registry adapter; persisting
  pointers as warehouse views.

## Exceptions

None.
