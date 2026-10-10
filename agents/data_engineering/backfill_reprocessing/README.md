# Backfill & Reprocessing Agent

## Purpose

The Backfill & Reprocessing Agent turns a vendor restatement or a corrected
source into a safe, complete, reversible recomputation. It uses lineage to find
exactly what is downstream, re-runs it under fleet limits as new immutable
versions, compares old and new outputs, and publishes every change at once — or
none — with the previous pointers kept for rollback.

## Use When

- A vendor restates historical prices, fundamentals, or reference data.
- A bug fix in a transform means history must be recomputed.
- A large backfill must not overrun the warehouse or starve daily jobs.
- Readers must never see a mix of old and new results.

## Inputs

- The restated (or corrected) versions and the lineage graph (`0102`).
- How to recompute each transform from its input versions.
- Fleet limits and pools (`0101`); comparison keys and acceptance gates per dataset.
- The currently published pointers (views, aliases, table pointers).

## Outputs

- A reprocessing plan: exactly the downstream runs, in dependency order.
- New immutable versions with recorded lineage; a run manifest.
- Per-dataset diffs (added, removed, changed, max numeric change).
- An all-or-nothing swap outcome with the previous pointers; handoffs to
  `pipeline_observability`, `data_quality`, and `provenance/lineage_capture`.

## Example Requests

- "The vendor restated September prices. Recompute everything affected — nothing more."
- "Backfill two years after the fix without starving the nightly jobs."
- "Show me what changed before we publish the reprocessed signals."
- "Roll back last night's reprocessing."

## Required Review Themes

- The plan comes from lineage: nothing downstream missed, nothing unrelated re-run.
- Outputs are new versions; old versions stay intact for comparison and rollback.
- Execution respects fleet limits; failures isolate their dependents.
- Publication is gated by diffs and atomic; rollback is a pointer restore.
