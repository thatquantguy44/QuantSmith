# Lineage Capture Agent

## Purpose

The Lineage Capture Agent makes every dataset, signal, and report number traceable
to the exact source pulls and code that produced it. It records content-hashed,
immutable dataset versions, registers where external data came from, records each
transform run with its code version, parameters, inputs, outputs, and column
mapping, and answers trace, impact, verification, and citation questions.

## Use When

- A report or model needs to prove which data versions it used (`0025` citations).
- A vendor restates a file and you need every downstream table and signal to recompute.
- A number looks wrong and you need its column-level path back to source.
- Lineage must be sent to a catalog (Marquez, DataHub, OpenMetadata) as OpenLineage.
- A pipeline is being reviewed for reproducibility and auditability.

## Inputs

- Source pulls: dataset, version label, rows or hash, `sources/` catalog id, retrieval time, licence.
- Transform runs: run id, transform, code version (commit), parameters, inputs, outputs, column map.
- The version, column, or run to trace, verify, cite, or export.

## Outputs

- A `LineageGraph` with registered sources and recorded runs.
- Traces (sources and runs, upstream first), impact lists, column traces with gaps.
- Hash verification results and point-of-use citations.
- OpenLineage-shaped run events; handoffs to `data_governance` and `bitemporal_data`.

## Example Requests

- "Which vendor files fed this momentum signal, and at which commit was it built?"
- "The vendor restated 2026-09 prices — what do we need to recompute?"
- "Trace `close_usd` in this table back to its source columns."
- "Emit OpenLineage events for last night's runs."

## Required Review Themes

- Every external input is registered with a source id and retrieval time.
- Every run names a code version and serializable parameters.
- Versions are immutable; restatements are new versions.
- Column lineage is declared or reported as a gap — never guessed.
- Citations include version, hash, and sources.
