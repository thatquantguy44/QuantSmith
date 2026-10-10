# Plan: Change-safe data engineering

- **Spec:** 0111-change-safe-data-engineering (`spec.md`)
- **Status:** Draft
- **Author:** QuantSmith
- **Last updated:** 2026-10-10

> HOW. Requires the approved `spec.md`.

## Approach

Three small standard-library modules, each reusing an approved runtime rather than
re-implementing it: windows write restatements to `0102`'s `BitemporalStore`;
reprocessing plans from `0102`'s `LineageGraph` and executes on `0101`'s
`run_fleet`. Each module validates before it mutates and reports everything it
did not apply.

## Agent Routing

```text
data_ingestion/* (connectors, files, APIs)
  -> data_engineering/schema_evolution      # check new schema; detect drift before load
  -> data_engineering/streaming_cdc         # apply CDC; window under a watermark
  -> provenance/lineage_capture + bitemporal_data (0102)
  -> data_engineering/backfill_reprocessing # restatement -> plan -> run -> compare -> swap
  -> data_engineering/pipeline_concurrency (0101) limits; pipeline_observability (0019)
```

## Architecture & Components

- `streaming_cdc.py`: `ChangeEvent`, `CdcState`, `CdcReport`, `apply_cdc`;
  `TimedEvent`, `WindowResult`, `WindowRun`, `window_aggregate` (tumbling, arrival
  order, watermark = max event time − allowed lateness, `side_output` | `restate`,
  optional `flush`), `record_revisions` (latest revision per window and knowledge
  time, written in knowledge-time order).
- `schema_evolution.py`: `Field`, `Schema` (validated), `Change`, `Compatibility`,
  `compatibility`, `check(mode)`, `first_violation`, `evolve_rows` (backward read with
  defaults and int→float promotion), `DriftReport`, `detect_drift` (bool is not a number).
- `reprocessing.py`: `Restatement`, `PlannedRerun`, `ReprocessPlan`,
  `plan_reprocessing` (consumer BFS from restated versions, topological order),
  `execute_plan` (one `FleetJob` per re-run, deps from the plan, optional pools,
  `persist` hook, lineage recorded under a lock, versions `<old>+<tag>`),
  `ReprocessResult`, `compare`/`Diff`, `max_changed_fraction`, `swap`/`SwapOutcome`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Sequence guards, watermark emission, mode checks, lineage-derived plans. |
| P5 Reversibility | yes | New versions only; swap returns previous pointers. |
| P6 Observability | yes | CDC report, late side output, drift report, diffs, blocked reasons. |
| P9 Security & data | yes | No network, no credentials. |
| P10 Honest reporting | yes | Nothing dropped silently (NFR-003). |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `apply_cdc` | T-001 |
| REQ-002 | `window_aggregate` | T-002 |
| REQ-003 | `WindowResult.known_at`, `record_revisions` | T-002 |
| REQ-004 | `compatibility` | T-003 |
| REQ-005 | `check`, `first_violation`, `evolve_rows` | T-003 |
| REQ-006 | `detect_drift` | T-003 |
| REQ-007 | `plan_reprocessing` | T-004 |
| REQ-008 | `execute_plan` | T-004 |
| REQ-009 | `compare`, `swap` | T-004 |
| NFR-001..003 | deterministic orderings; reports; no mutation before validation | T-001..T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| CDC ordering | Per-key sequence guard | Global ordering | Connectors guarantee per-key order at best; a global order is not available. |
| Late data | Side output or restatement | Drop | Dropping is silent data loss (NFR-003). |
| Schema rules | Avro-style widening table | Any numeric change allowed | Narrowing and string↔number changes corrupt values. |
| Reprocess output | New immutable versions | Overwrite in place | Overwrite destroys the rollback target and the comparison baseline. |
| Publication | All-or-nothing pointer swap | Per-table swap | Per-table swaps expose mixed old/new states. |

## Validation Strategy

AC-001..AC-009 map to `tests/test_change_safety.py` (see `tasks.md`).

## Rollout, Observability & Rollback

Library functions. Adopt per pipeline: schema check and drift at ingestion, CDC
application in streaming loaders, reprocessing when a source is restated. Rollback
of a reprocessing is restoring `SwapOutcome.previous`.
