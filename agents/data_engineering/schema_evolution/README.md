# Schema Evolution Agent

## Purpose

The Schema Evolution Agent decides whether a schema change is safe and catches
schema drift before bad rows load. It classifies every field-level change by the
direction it breaks (backward: new readers on old data; forward: old readers on
new data), enforces a declared compatibility mode across a version history, reads
old data with a new schema only when that is safe, and compares delivered rows to
the declared schema.

## Use When

- A vendor or upstream team announces a schema change (new, dropped, retyped, or
  null-relaxed columns).
- A load failed or, worse, mis-parsed after an unannounced change.
- History must be replayed under a newer schema.
- A compatibility policy (backward, forward, full) needs choosing and enforcing.

## Inputs

- The old and new schema versions (fields, types, nullability, defaults), or a history.
- The compatibility mode and which side (readers or writers) upgrades first.
- A sample of delivered rows for drift detection.

## Outputs

- A per-field change classification with backward/forward break flags.
- Mode violations and the first violating version in a history.
- A drift report (unknown, missing, null, and type-mismatch counts per column).
- A migration path (defaults, backfill, consumer upgrade order); handoffs to
  `data_ingestion/*`, `data_quality`, and `backfill_reprocessing`.

## Example Requests

- "The vendor widened `volume` from int to long and added `currency` — is that safe?"
- "Which schema version in this history broke our readers?"
- "Check today's file against the contract before we load it."
- "Can we replay three years of v1 files with the v3 schema?"

## Required Review Themes

- Every change is classified; none is summarized away.
- The declared mode matches the upgrade order (readers first = backward).
- Added required fields have defaults or are nullable before old data is replayed.
- Drift is checked before load; a drifting file is quarantined, not coerced.
