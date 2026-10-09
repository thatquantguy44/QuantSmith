# Write-Back Contract: <target-name>

> The reviewable contract for one natural-language-analytics write-back target
> (spec `0080`, REQ-010/REQ-011). Copy this file next to your deployment as
> `<target>_writeback_contract.md`. Loaded and validated by
> `quantsmith.nl_analytics.writeback.load_contract`; the database itself, its
> credentials, and its driver are never named here — only what may be written,
> and under what conditions.

## Target

- **Name:** <target-name> — matches the `target` a caller passes to `publish()`.
- **Store:** <e.g. "local SQLite file", "team Postgres schema"> — descriptive
  only; the connection itself is caller-injected.
- **Owner:** <team or person accountable for this target>

## Schema

The columns a write-back record may carry. Every record `build_records`
produces has all of these; a record with an extra column, or missing one, is
rejected before the writer is ever called.

| Column | Type | Meaning |
| --- | --- | --- |
| `record_key` | string | Idempotency key — hash of `run_id` and the insight's position. Primary key. |
| `run_id` | string | The `0070` run that produced this record. |
| `question_hash` | string | Hash of the original natural-language question. |
| `plan_hash` | string | `QueryPlan.content_hash()` — the governed query this record answers. |
| `metric` | string | The governed metric name (`0008`). |
| `metric_definition_hash` | string | Hash of the metric's definition at compute time — detects a later redefinition. |
| `dimensions_json` | string | JSON array of the plan's declared dimensions. |
| `window_start` | integer | Plan window start period. |
| `window_end` | integer | Plan window end period. |
| `as_of` | integer | The as-of bound the answer was computed under. |
| `insight_kind` | string | One of `level`, `change`, `contributor`, `trend`, `outlier`, `concentration`. |
| `values_json` | string | JSON of the insight's `values` — the numbers the statement rests on. |
| `headline` | string | The insight's rendered statement. |
| `interpreter_mode` | string | Which interpreter produced the plan (e.g. `keyword/1`). |
| `author_handle` | string | Pseudonymous handle (`0049` resolution) — never an email. |
| `created_at` | integer | When this record was written (caller-supplied, not a clock read here). |
| `reversed_at` | integer or null | Set by `reverse()`; null means the record still stands. |

## Idempotency

- **Key:** `record_key` (see Schema). A `publish()` commit that repeats an
  already-written key writes zero new rows for that key.

## Allowed Columns

- **Insert:** exactly the Schema columns above — no more, no fewer.
- **Update:** none. Write-back is append-only; the only permitted mutation is
  `reverse()` setting `reversed_at` on rows matching a `run_id`, never deleting
  or rewriting any other column.

## Source-Table Deny-List

Write-back never touches a source or fact table. One glob pattern per bullet
(`*` matches anything), parsed by `writeback.load_contract` — write the
pattern itself, not a sentence about it. Replace these two starting-point
patterns with the actual tables `0080`'s own `reader` reads from:

- `fact_*`
- `source_*`

## Approval

- **`auto_approve`:** `false` — a commit requires `approved=True` on the call.
  Set `true` only for a target where the accountable owner has decided every
  commit through this contract needs no per-request confirmation (spec
  REQ-011); record that decision here, not just in code.
- **`approver_roles`:** `<role, role>` — optional. A committed write's approver must hold one of these roles in
  `access/roster.yml`; the target is refused while the roster has no entries. Delete the line for no role check.
- **`require_distinct_approver`:** `false` — `true` rejects a commit approved by its own author.

Every committed record carries `approver_handle` (spec `0080` REQ-023). When an approved commit names no
approver, the approver is the request's author, and the record says so.

## Reversal

- Reversal is by `run_id`: every record from one run is tombstoned together
  (`reversed_at` set), never deleted. A record's history stays intact.

## Reference Implementation

- The SQLite target (`quantsmith.nl_analytics.writeback_sqlite.SQLiteWriter`)
  is the first supported target (owner decision, 2026-09-24): a local,
  gitignored file, `ON CONFLICT(record_key) DO NOTHING` for idempotency, and
  an `UPDATE ... SET reversed_at` for reversal. Copy its contract file at
  `examples/nl_analytics/writeback_contract.md` as a starting point.
