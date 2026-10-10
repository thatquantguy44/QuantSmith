# Bitemporal Data Instructions

## Operating Rules

- Record each fact with its validity interval `[valid_from, valid_to)`, the time it
  became known (`recorded_at`, from the source's publication or retrieval time —
  never the time you happened to load it into a backfill), and its source.
- Append corrections as new facts with a later knowledge time; use `retract` for
  withdrawals. Never edit or delete history.
- Load history in knowledge-time order; the store rejects backdated knowledge.
- Read for decisions with `as_of(key, valid_at, known_at=decision_time)` or
  `snapshot`; never with the latest value.
- Run `lookahead_violations` over the facts a backtest used; any hit is a defect.
- Use `revisions` to show how a value changed and which source changed it.
- For FRED series, `0045` already provides vintages; this store generalizes it.

## Checks

- Does every fact carry a source and a defensible knowledge time?
- Were any facts loaded with load time instead of publication time?
- Does every backtest read by knowledge time, with zero look-ahead violations?
- Are retractions modelled as tombstones rather than deletions?

## Output Contract

Use clear Markdown. Present `Facts Recorded`, `As-Of Answers` (valid time, knowledge
time, value, source), `Revision Trail`, and `Look-Ahead Check`. Name the runtime
symbols (`BitemporalStore`, `record`, `retract`, `as_of`, `value_as_of`,
`snapshot`, `revisions`, `lookahead_violations`).

## Spec-Driven Role

Point-in-time needs become `REQ-*`; append-only recording, no backdating, as-of
correctness, retraction, revision trails, and look-ahead detection become testable
`AC-*`; backdated knowledge, overwritten history, and backtests reading
restatements become `RISK-*`. The standard is `instructions/data_provenance.md` and
`instructions/point_in_time.md`; the runtime is
`src/quantsmith/pipelines/provenance.py`; the spec is
`specs/0102-lineage-bitemporal-provenance/`. Hands off to `backtest_review`,
`provenance/lineage_capture`, and `data_quality`.
