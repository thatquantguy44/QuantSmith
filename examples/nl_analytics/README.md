# nl_analytics Worked Example

A three-day, three-question walkthrough of spec `0080`'s natural-language
analytics package (`src/quantsmith/nl_analytics/`) and its CLI
(`quantsmith-nl-analytics`, `src/quantsmith/nl_analytics/cli.py`).

## Files

- `registry.json` — a one-metric semantic-layer registry (`funding_cost`,
  owned by `treasury-ops`, grain `day`, dimension `desk`) loaded via
  `SemanticLayer.define`.
- `data.json` — nine synthetic fact rows (3 desks × 3 days). Entirely
  synthetic; see `../../docs/0080_synthetic_data_disclosure.md`.
- `transcript.md` — the three commands, one per day, with their real output.
- `sample_response.json` — the committed, pinned JSON response from the
  transcript's third (final) question, produced by `--json`.

## Run it yourself

```sh
DB=/tmp/nl_analytics_demo.db
rm -f "$DB"

PYTHONPATH=src python3 -m quantsmith.nl_analytics.cli ask \
  "what is total funding cost" \
  --registry examples/nl_analytics/registry.json \
  --data examples/nl_analytics/data.json \
  --today 1 --window 1 --db "$DB" --publish --commit --approve --run-id run-day1 --author desk-analyst
```

See `transcript.md` for all three days' commands and output side by side.
If `quantsmith` is installed (`pip install -e .`), the same commands work as
`quantsmith-nl-analytics ask ...` without the `PYTHONPATH=src python3 -m`
prefix.

## What's real vs. synthetic

Every number in this example comes from `data.json`, which is entirely
synthetic (`docs/0080_synthetic_data_disclosure.md` discloses it in full).
The mechanics demonstrated — plan governance, chart form rule, insight
grounding, write-back dry-run/commit/idempotency, and the persisted-insight
comparison — are exactly what runs against real data; only the input rows
here are made up.
