# Synthetic Data Disclosure — `examples/nl_analytics/`

Companion report for `examples/nl_analytics/` (spec `0080-nl-analytics-insights`,
T-018). Required whenever any data point, figure, or visual in that example
uses synthetic, simulated, or otherwise non-actual data. See
`instructions/data_provenance.md` for the priority stack and standards this
report enforces.

- **Artifact:** `examples/nl_analytics/` (registry, fact rows, transcript,
  committed sample response)
- **Author:** nl_analytics package owner (spec `0080`)
- **Last updated:** 2026-09-29
- **Reviewer / sign-off:** _(pending)_

## Priority Check

- [x] Actual, sourced data was the first option considered for every item below.
- [x] Synthetic data was used only because this is a packaged, offline worked
      example meant to run identically for anyone who clones the repository —
      no live desk-funding-cost feed exists in this environment, and a
      committed example cannot depend on one.

## Disclosure Table

| Location (section / chart / field) | What's synthetic | Why real data wasn't used | Generation method | Real-data follow-up |
| --- | --- | --- | --- | --- |
| `examples/nl_analytics/data.json` | All 9 fact rows: `funding_cost` for 3 desks (`rates`, `credit`, `fx`) over 3 synthetic day periods (1, 2, 3) | No live treasury/funding-cost feed is available in this SDK's offline environment; the example must be reproducible without any credential or network call (NFR-003) | Hand-authored fixed values, chosen only to walk through the level → grouped → comparison narrative in `transcript.md` (a mild day-over-day rise from 250 to 255 to 270 in total, concentrated in the `rates` desk) — not sampled from or modeled on any real book | Not applicable — this is a permanent worked example, not a production dataset; an adopter wires their own governed reader (`AnswerContext.reader`) against real data instead of replacing this file |
| `examples/nl_analytics/registry.json` | The `funding_cost` metric's `owner: "treasury-ops"` field | Illustrative ownership label for a fictional desk, needed for the citation shown in every answer | Placeholder string, not a real team or system | Not applicable — same as above |
| `examples/nl_analytics/sample_response.json` | The entire committed response (headline, insights, chart, table) | Derived entirely from the synthetic `data.json` above via the real, unmodified `answer()` pipeline — pinned so the worked example has a stable, reviewable expected output | Produced by running `quantsmith-nl-analytics ask` against `data.json`/`registry.json` and capturing its `--json` output verbatim | Regenerate by re-running the command in `transcript.md` if `data.json` or the pipeline's deterministic behavior changes |

## Traceability

- No row in `data.json`, `registry.json`, or `sample_response.json` claims to
  be real; `transcript.md` states up front that every command runs against
  this directory's synthetic fixtures.
- The *mechanics* demonstrated (plan governance, chart selection, insight
  grounding, write-back dry-run/commit/idempotency, persisted-insight
  comparison) are the real, tested `src/quantsmith/nl_analytics/` code path
  — only the input rows are synthetic.
- If this example is ever regenerated against real data, this report is
  updated or removed in the same change.

## Open Items

- None.
