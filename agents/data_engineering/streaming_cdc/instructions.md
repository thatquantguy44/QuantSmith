# Streaming & CDC Instructions

## Operating Rules

- Key every CDC event and carry the source's per-key monotonic sequence (LSN,
  offset, row version). Apply with `apply_cdc`; an event at or below the applied
  sequence is a duplicate or stale and is counted, not applied.
- Prefer full row images. Partial updates are merged onto the current row and are
  only order-safe when each key's events arrive in sequence.
- Treat deletes as sequenced tombstones; a stale insert must not resurrect a key.
- Aggregate on event time, not arrival time. Choose `allowed_lateness` from the
  feed's observed delay distribution and state it.
- Never drop a late event: use `late_policy="side_output"` and reconcile the side
  output, or `"restate"` and record revisions with `record_revisions` so readers
  query by knowledge time (`0102`).
- Report the CDC counts and the late side output to `pipeline_observability`.

## Checks

- Does every event carry a per-key sequence, and is it applied through the guard?
- Are updates full images, or is per-key ordering guaranteed?
- Is allowed lateness justified by measured delays?
- Is every late event in the side output or a restatement, with nothing dropped?
- Do backtests read restated windows by knowledge time?

## Output Contract

Use clear Markdown. Present `CDC Application` (sequence source, image type, report
counts), `Windows` (size, allowed lateness, late policy, revisions), `Late Data`,
and `Bitemporal Recording`. Name the runtime symbols (`ChangeEvent`, `apply_cdc`,
`TimedEvent`, `window_aggregate`, `record_revisions`).

## Spec-Driven Role

Streaming requirements become `REQ-*`; idempotent replay, stale-event rejection,
watermark emission, late-event accounting, and knowledge-time visibility become
testable `AC-*`; double-applied replays, silent late drops, and look-ahead from
restated bars become `RISK-*`. The standard is `instructions/pipeline_engineering.md`
→ *Change-Safe Pipelines*; the runtime is `src/quantsmith/pipelines/streaming_cdc.py`;
the spec is `specs/0111-change-safe-data-engineering/`. Hands off to
`provenance/bitemporal_data`, `data_engineering/backfill_reprocessing`, and
`data_engineering/pipeline_observability`.
