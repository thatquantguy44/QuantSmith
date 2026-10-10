# Spec: Lineage and bitemporal provenance

- **ID:** 0102-lineage-bitemporal-provenance
- **Status:** Approved
- **Author:** QuantSmith
- **Approver:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-10

> WHAT and WHY only. Implementation lives in `plan.md`.
> First slice of the platform expansion roadmap (`docs/handoff.md` → What's Next #0).

## Problem & Context

Every number in a quant report has to answer two questions: *where did it come
from?* and *what did we know, and when?* The SDK answers them only in pieces.
`0025` requires a citation at the point of use but nothing produces one; `0011`
and `0101` record run status but not which input versions a run read; `0045`
handles vintages for FRED alone. So a restated vendor file cannot be traced to the
signals it fed, a report cannot prove its numbers came from the versions it
cites, and a backtest can quietly read a value revised after its decision date —
look-ahead the `leakage` gate's text heuristics cannot see.

## Goals

- Record content-hashed, immutable dataset versions, the external sources they
  came from, and the transform runs (code version, parameters) that produced them.
- Trace any version to its sources, at dataset and column level; list everything
  downstream of a changed input.
- Verify rows against their recorded hash; emit `0025`-ready citations and
  OpenLineage-shaped run events.
- Keep facts on two timelines (valid time and knowledge time), append-only, so any
  query can be answered as of what was known at a given moment.
- Flag any fact used in a decision before it was known.

## Non-Goals

- A lineage server, UI, or metadata catalog (Marquez, DataHub, OpenMetadata are
  targets for the emitted events, not replacements).
- Automatic lineage capture by parsing SQL or bytecode; lineage is declared by the
  run that knows it.
- Vendor licensing and entitlement enforcement (reserved for `0108`).
- Durable storage; the reference is in-memory and serializable.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall identify each dataset version by a canonical content hash and treat a version as immutable: one producer, one hash. | must |
| REQ-002 | The system shall record a transform run only when every input is a registered source or produced version with a matching hash, its outputs are new, it names a code version, its parameters are serializable, and its column map refers only to its own inputs and outputs. | must |
| REQ-003 | The system shall trace a version to all upstream sources and runs, list all downstream versions, and trace a column to its source columns while reporting undeclared hops as gaps. | must |
| REQ-004 | The system shall verify rows against a version's recorded hash and produce a point-of-use citation naming the version, hash, and sources with retrieval times. | must |
| REQ-005 | The system shall export a run as an OpenLineage-shaped COMPLETE event with dataset-version and column-lineage facets. | should |
| REQ-006 | The system shall store facts with valid time and knowledge time, append-only, rejecting backdated knowledge and contradictory facts recorded at the same instant for overlapping validity. | must |
| REQ-007 | The system shall answer value-as-of(valid time, knowledge time) and snapshot queries with the latest knowledge at or before the knowledge time, support retractions, and list a fact's full revision trail. | must |
| REQ-008 | The system shall flag facts used in a decision that were recorded after the decision time. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Reproducibility | Hashes are independent of key order; the same inputs give the same hashes, traces, and query answers. |
| NFR-002 | Point-in-time correctness | No query returns a fact recorded after its knowledge time. |
| NFR-003 | Honest reporting | Undeclared column lineage is reported as a gap, never inferred; failed recordings leave no partial state. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given rows with reordered keys, when hashed, then the hashes match; given a version re-registered with different content, then it is rejected as immutable. | REQ-001, NFR-001 |
| AC-002 | Given a run with an unknown or stale input, a reused run id, an existing output, no code version, unserializable params, or a foreign column-map entry, when recorded, then it is rejected and nothing is partially recorded. | REQ-002, NFR-003 |
| AC-003 | Given a two-run lineage from two sources, when traced, then both sources and both runs (upstream first) are returned, impact lists all downstream versions, and column trace returns source columns or a named gap. | REQ-003, NFR-003 |
| AC-004 | Given a recorded version, when its rows are verified, then original rows pass and altered rows fail; its citation names version, hash, and every source with retrieval time. | REQ-004 |
| AC-005 | Given a recorded run, when exported, then the event is COMPLETE, serializable, and carries job, run, code version, dataset versions, and column lineage. | REQ-005 |
| AC-006 | Given an append-only store, when knowledge is backdated, contradicted at the same instant, given an empty interval, or lacks a source, then it is rejected. | REQ-006 |
| AC-007 | Given advance, second, and third estimates of a value, when queried at successive knowledge times, then each returns the estimate known then; snapshots exclude facts not yet known; revisions list all three; a retraction hides the value going forward only. | REQ-007, NFR-002 |
| AC-008 | Given a fact restated after a decision date, when the restated fact is used for that decision, then it is flagged; the as-of fact is not. | REQ-008, NFR-002 |

## Data & Dependencies

- Runtime: `src/quantsmith/pipelines/provenance.py` (standard library only).
- Builds on `0025` (citations), `0027` (source ids), `0011`/`0101` (runs),
  `0045` (FRED vintages — a special case of the bitemporal store).
- Agents: new `provenance/lineage_capture` and `provenance/bitemporal_data`;
  existing `data_engineering/data_governance`, `data_quality`, `backtest_review`.
- Standard: `instructions/data_provenance.md` → *Lineage And Bitemporal Records*.
- No private data or credentials are written to this repository.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A version is silently overwritten in place. | Citations point to data that changed. | Immutable versions; `verify` detects drift (AC-001, AC-004). |
| RISK-002 | Lineage is recorded for outputs whose inputs were never registered. | Traces end in nothing; orphan outputs. | Unknown inputs rejected (AC-002). |
| RISK-003 | Column lineage is guessed. | False confidence in a trace. | Undeclared hops are gaps (AC-003). |
| RISK-004 | Knowledge is backdated to make a revision look known earlier. | Look-ahead disguised as history. | Monotonic knowledge clock (AC-006). |
| RISK-005 | A backtest reads the latest restatement. | Inflated performance. | `as_of` by knowledge time; `lookahead_violations` (AC-007, AC-008). |
| RISK-006 | Hashing large datasets row-by-row is slow. | Teams skip it. | Reference hashes rows; adopters may hash files or Parquet row groups and pass the hash — the contract is the hash, not the method. |

## Assumptions & Open Questions

- Assumption: runs declare their own lineage (the code that reads inputs knows them).
- Open question: durable backend (SQLite/Parquet) and a `quantsmith-lineage` CLI.
- Open question: hook `0011`/`0101` runners so every run records lineage automatically.

## Exceptions

None.
