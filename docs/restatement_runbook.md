# Restatement runbook

What to do when a source changes underneath you: a vendor restates history, a
feed changes its schema, or a stream delivers late or replayed data. Runtimes and
contract: spec `0111` (`streaming_cdc.py`, `schema_evolution.py`,
`reprocessing.py`) on top of `0101` (fleet limits) and `0102` (lineage,
bitemporal). Agents: `data_engineering/backfill_reprocessing`,
`schema_evolution`, `streaming_cdc`.

---

## A vendor restated historical data

1. **Register, don't overwrite.** Load the restated file as a new version of the
   dataset and register it as a source (`LineageGraph.register_source`) with its
   retrieval time. The old version stays — it is your baseline and rollback.
2. **Record the knowledge time.** If the series feeds backtests, append the
   restated values to the `BitemporalStore` with `recorded_at` = when you received
   the restatement, so backtests dated earlier still see the original values.
3. **Plan.** `plan_reprocessing(graph, [Restatement(old, new)])`. Review the run
   list: it is exactly what is downstream. If something you expected is missing,
   its lineage was never recorded — fix that first; do not hand-add tables.
4. **Run under limits.** `execute_plan(..., tag="<vendor>-<date>", config=<fleet
   config>, pools_for=..., persist=...)`. Use the production pools so the backfill
   cannot starve the nightly jobs. Check `result.ok`; a failed run marks its
   dependents `upstream_failed` — fix and re-run with a new tag.
5. **Compare.** `compare(dataset, old_rows, new_rows, key=...)` for every
   reprocessed dataset. Read the diffs: how many rows changed, and the largest
   numeric change per column. Set each gate deliberately (`max_changed_fraction`).
6. **Publish.** `swap(pointers, result, diffs, gate)`. It moves every pointer or
   none. If it is blocked, read `blocked` — do not swap tables one by one.
7. **Record.** Keep `SwapOutcome.previous` with the decision (who, why, diffs).
   **Rollback** = restore those pointers.

---

## A feed changed its schema

1. Get the new schema and compare: `compatibility(old, new)`. Read every change.
2. `check(old, new, mode)` with the mode that matches who upgrades first
   (readers first → `backward`; writers first → `forward`; both → `full`).
3. If it violates the mode, push back on the producer or plan a two-step change
   (add with a default first, remove later). A rename is a removal plus an addition.
4. Before replaying history under the new schema, use `evolve_rows`; it refuses
   when the change is not backward compatible.

---

## A delivery doesn't match its schema

1. `detect_drift(schema, rows)` before load. Unknown columns, missing required
   columns, nulls in non-nullable columns, and type mismatches are counted per column.
2. Quarantine the file; do not coerce values to make it load.
3. If the drift is an intended change, go to *A feed changed its schema*.

---

## A stream double-counted or lost late prints

1. **Double counts:** events must carry a per-key sequence (LSN/offset/version)
   and go through `apply_cdc`. Check the report: `duplicates` and `stale` are
   replays and out-of-order events that were correctly skipped. If updates are
   partial (not full row images), per-key ordering must be guaranteed upstream.
2. **Late prints:** check `allowed_lateness` against the feed's measured delays.
   Late events are in `WindowRun.late` (side output) or appear as restatements
   (`revision > 1`) — they are never dropped. Record restatements with
   `record_revisions` so backtests read them by knowledge time.
