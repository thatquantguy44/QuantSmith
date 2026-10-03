# Worked Example: Three Days of Natural-Language Analytics

Spec `0080-nl-analytics-insights`, T-018. Every command below runs against
the synthetic data in this directory (`registry.json`, `data.json` — see
`../../docs/0080_synthetic_data_disclosure.md`) and a local, gitignored
SQLite file the first command creates.

```sh
DB=/tmp/nl_analytics_demo.db
rm -f "$DB"
```

## Day 1 — a level question, published

```sh
PYTHONPATH=src python3 -m quantsmith.nl_analytics.cli ask \
  "what is total funding cost" \
  --registry examples/nl_analytics/registry.json \
  --data examples/nl_analytics/data.json \
  --today 1 --window 1 \
  --db "$DB" --publish --commit --approve --run-id run-day1 --author desk-analyst
```

```
status: answered
headline: funding_cost is 250 as of period 1.
plan: metric 'funding_cost'; for periods 1-1 (day); defaults applied: window
  - [level] funding_cost is 250 as of period 1.
caveats:
  - Small sample: only 3 row(s) behind this answer.
citations:
  - funding_cost — owner: treasury-ops
  - as of period 1

| metric | value |
| --- | --- |
| funding_cost | 250.0 |

write-back: committed (1 record(s), run_id=run-day1)
```

This answer's one `level` insight is committed to the SQLite store under
`run-day1` — the record a later "since yesterday" question will find.

## Day 2 — a grouped question, chat-only (no `--publish`)

```sh
PYTHONPATH=src python3 -m quantsmith.nl_analytics.cli ask \
  "what is total funding cost by desk" \
  --registry examples/nl_analytics/registry.json \
  --data examples/nl_analytics/data.json \
  --today 2 --window 1 \
  --db "$DB"
```

```
status: answered
headline: funding_cost is 255 as of period 2.
plan: metric 'funding_cost'; by desk; for periods 2-2 (day); defaults applied: window
  - [level] funding_cost is 255 as of period 2.
  - [concentration] desk = rates holds 49.0% of funding_cost (HHI 0.379 across 3 groups).
caveats:
  - Small sample: only 3 row(s) behind this answer.
citations:
  - funding_cost — owner: treasury-ops
  - as of period 2

| desk | value |
| --- | --- |
| rates | 125.0 |
| credit | 82.0 |
| fx | 48.0 |
```

Asking "by desk" groups the answer into a bar-shaped chart (`data_visualization`'s
form rule) and surfaces a concentration insight. No `--publish` here — this
is a plain chat answer, demonstrating that asking a question never writes
anywhere unless explicitly told to (RISK-004's "no side effects" guarantee).
Because it wasn't published, day 2's own total is never itself persisted —
only day 1's record exists in the store when day 3 asks its question below.

## Day 3 — "since yesterday", comparing against the persisted record

```sh
PYTHONPATH=src python3 -m quantsmith.nl_analytics.cli ask \
  "what is total funding cost since yesterday" \
  --registry examples/nl_analytics/registry.json \
  --data examples/nl_analytics/data.json \
  --today 3 --window 1 \
  --db "$DB" --publish --commit --approve --run-id run-day3 --author desk-analyst --json
```

Output: see the committed `sample_response.json` in this directory.

The `KeywordInterpreter`'s "yesterday" phrase does double duty (a documented
behavior, not new to T-018 — see
`test_ac016_respond_yesterday_reference_shifts_as_of_by_one` in
`tests/test_nl_analytics.py`): it both shifts the plan's own window to
yesterday (period 2, so "now" is freshly computed from period 2's raw
rows — 255) *and* asks for the most recent persisted record visible as of
one period before the request's `as_of` (period 2, so only day 1's
`run-day1` record at period 1 is visible — 250, since day 2 was never
published). The result is a genuine, correctly-grounded `change` insight:
funding cost is up 5 (+2.0%) since the last thing this desk was told.

## What this demonstrates

- **Question → governed plan → chart → insights → narrative**, with no
  free-form SQL anywhere (`plan.py`'s `QueryPlan` has no SQL/code field).
- **Write-back is opt-in and dry-run by default** — day 2's question never
  touches the store; day 1 and day 3 commit only because `--publish
  --commit --approve` was passed.
- **Idempotency and reversibility** live in `writeback.py`/
  `writeback_sqlite.py` (T-012/T-020) and are exercised by
  `tests/test_nl_analytics.py`, not repeated here.
- **A multi-day "since yesterday" comparison** reads the write-back store
  as of the request, never the wall clock (NFR-002) — see
  `writeback.prior_insights`.

## Cleanup

```sh
rm -f /tmp/nl_analytics_demo.db
```

The SQLite file is never committed — `*.db` is gitignored repo-wide; only
this transcript and the one pinned `sample_response.json` are.
