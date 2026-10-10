# Streaming & CDC Tasks

## Make A CDC Feed Idempotent

Input: a CDC connector's event format and delivery guarantees.

Output: an `apply_cdc` design keyed on per-key sequence, with the report counts to monitor.

## Design Event-Time Windows

Input: a feed, the aggregate, and its observed delay distribution.

Output: window size, justified allowed lateness, and late policy for `window_aggregate`.

## Account For Late Data

Input: a pipeline that drops or mishandles late events.

Output: a side-output reconciliation or a restatement design recorded bitemporally.

## Review A Streaming Pipeline

Input: an existing streaming or CDC pipeline.

Output: findings on replay safety, ordering, watermarks, and late-data handling, with fixes.
