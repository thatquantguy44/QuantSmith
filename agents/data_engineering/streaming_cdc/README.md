# Streaming & CDC Agent

## Purpose

The Streaming & CDC Agent makes streamed and change-data-capture data correct
under the conditions streams actually deliver: at-least-once replays, out-of-order
events, and late prints. It applies CDC events idempotently by per-key sequence,
aggregates event-time windows under a watermark, and accounts for every late event
as a side output or a bitemporally recorded restatement.

## Use When

- A table is fed by a CDC connector (Debezium, DMS, a vendor change feed) and
  replays or out-of-order events are possible.
- Bars, VWAPs, or other event-time aggregates are built from a live feed and late
  prints arrive after a window looked complete.
- A backtest must see the first print of a bar as of then and the restatement only after.
- Streamed counts or positions look inflated (double-applied replays).

## Inputs

- Change events with key, op (insert/update/delete), per-key sequence, and payload (full image preferred).
- Timed events with event time, arrival time, and value; window size and allowed lateness.
- The late-data policy (side output or restate) and where restatements are recorded.

## Outputs

- A materialized table plus a CDC report (applied, duplicates, stale, deletes).
- Window results with revision numbers and knowledge times; the late side output; open windows.
- Bitemporal facts for every window revision (`0102`).
- Handoffs to `provenance/bitemporal_data`, `backfill_reprocessing`, and `pipeline_observability`.

## Example Requests

- "Our Debezium feed replays after restarts and positions double — make it idempotent."
- "Build 5-minute VWAP bars that wait for late prints but don't wait forever."
- "Late trades are disappearing from our bars. Where do they go?"
- "Make the backtest see the bar as first published, not the restated one."

## Required Review Themes

- Every CDC event is applied only if its sequence is newer than the key's applied sequence.
- Updates carry full row images, or ordered delivery per key is guaranteed.
- Windows emit only once the watermark passes their end; allowed lateness is justified.
- No late event is dropped silently; restatements are recorded with knowledge time.
