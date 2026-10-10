# Plan: Lineage and bitemporal provenance

- **Spec:** 0102-lineage-bitemporal-provenance (`spec.md`)
- **Status:** Draft
- **Author:** QuantSmith
- **Last updated:** 2026-10-10

> HOW. Requires the approved `spec.md`.

## Approach

Two small, independent structures in one standard-library module. `LineageGraph` is
an append-only graph whose nodes are content-hashed dataset versions and whose
edges are transform runs; validation happens before any state changes, so a
rejected run leaves nothing behind. `BitemporalStore` is an append-only fact list
with a monotonic knowledge clock; every read filters by knowledge time first, so
point-in-time correctness holds by construction rather than by caller discipline.

## Agent Routing

```text
data_ingestion/* + sources/ catalog (0027)   # register_source(version, source_id, retrieved_at)
  -> provenance/lineage_capture               # record_run, trace, impact, cite, OpenLineage
  -> provenance/bitemporal_data               # record / as_of / revisions; vintage-aware reads
  -> backtest_review, data_quality            # lookahead_violations, verify
  -> data_engineering/data_governance         # catalog consumes OpenLineage events
  -> reporting-agent / analytics              # cite() at the point of use (0025)
```

## Architecture & Components

- `content_hash(rows)` — SHA-256 over canonical JSON (sorted keys).
- `DatasetVersion(dataset, version, content_hash)`, `.of(dataset, version, rows)`.
- `SourceRecord(version, source_id, retrieved_at, license)`.
- `TransformRun(run_id, transform, code_version, inputs, outputs, params,
  column_map, started_at)`.
- `LineageGraph` — `register_source`, `record_run`, `trace`, `impact`,
  `trace_column`, `verify`, `cite`, `to_openlineage`.
- `Fact(key, value, valid_from, valid_to, recorded_at, source, seq)`; `RETRACTED`.
- `BitemporalStore` — `record`, `retract`, `as_of`, `value_as_of`, `snapshot`,
  `revisions`; `lookahead_violations(used, decision_time)`.

## Interfaces & Data Contracts

- Validity is half-open `[valid_from, valid_to)`; `valid_to=None` is open-ended.
- Times are any mutually comparable type (dates, datetimes, one ISO format).
- Latest knowledge wins: highest `(recorded_at, seq)` at or before `known_at`.
- OpenLineage output: `eventType`, `eventTime`, `producer`, `schemaURL`, `run`
  (with a `quantsmith` facet: code version, params), `job`, `inputs`, `outputs`
  (with `version` and `columnLineage` facets). Shaped after OpenLineage 2-0-2;
  validate against the consumer's schema before relying on it.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Knowledge-time filter in every read; immutable versions; validation before mutation. |
| P5 Reversibility | yes | Append-only: corrections and retractions add facts; history is never lost. |
| P6 Observability | yes | Trace, impact, revisions, OpenLineage events. |
| P9 Security & data | yes | No network, no credentials; licence recorded, not enforced (`0108`). |
| P10 Honest reporting | yes | Column-lineage gaps reported, never guessed. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `content_hash`, `LineageGraph._claim` | T-001 |
| REQ-002 | `LineageGraph.record_run` | T-002 |
| REQ-003 | `trace`, `impact`, `trace_column` | T-003 |
| REQ-004 | `verify`, `cite` | T-003 |
| REQ-005 | `to_openlineage` | T-004 |
| REQ-006 | `BitemporalStore.record` | T-005 |
| REQ-007 | `as_of`, `snapshot`, `revisions`, `retract` | T-005 |
| REQ-008 | `lookahead_violations` | T-006 |
| NFR-001 | canonical hashing, deterministic sort orders | T-001, T-003 |
| NFR-002 | knowledge-time filter in `as_of` | T-005 |
| NFR-003 | gaps in `ColumnTrace`; validate-then-mutate | T-002, T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Version identity | Content hash + human version label | Label only | A label can be reused for different bytes; a hash cannot. |
| Lineage capture | Declared by the run | Parse SQL/code | Declared lineage is exact and testable; parsing is a later adapter. |
| Column lineage gaps | Report | Assume all-to-all | All-to-all is a guess presented as fact. |
| Corrections | Append with later knowledge time | Update in place | In-place updates destroy what was known when. |
| Backdating | Rejected | Allowed with a flag | Backdated knowledge is exactly how look-ahead hides. |

## Validation Strategy

AC-001..AC-008 map one-to-one to `tests/test_provenance.py` (see `tasks.md`).

## Rollout, Observability & Rollback

A library. Adopt incrementally: register sources at ingestion, record runs in the
`0011`/`0101` step wrappers, route OpenLineage events to the catalog, and move
vintage-sensitive series into the bitemporal store. Rollback is removing the calls;
no existing interface changes.

## Open Questions

- Durable backend and CLI; automatic recording from `0011`/`0101` runners.
- Migrate `0045`'s FRED panel onto `BitemporalStore` once a durable backend exists.
