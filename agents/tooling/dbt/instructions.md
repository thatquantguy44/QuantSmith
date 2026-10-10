# dbt Instructions

## Operating Rules

- Review from the compiled manifest (`dbt parse`), not from hand-read SQL; run
  `review_manifest(json.load(open("target/manifest.json")))`.
- Give every model an owner (`meta.owner` or a `group`).
- Test a primary key on every model: `unique` + `not_null` on one column, or
  `dbt_utils.unique_combination_of_columns`.
- Enforce contracts (`contract: {enforced: true}`) on public and mart models; pair
  with `schema_evolution` before changing a contracted model.
- Incremental models need a `unique_key` (or a merge strategy that implies one), an
  `is_incremental()` filter, and `on_schema_change: fail` or `append_new_columns`.
- Never read the wall clock in a model; pass the as-of date as a `var` so a run is
  reproducible for any date and backfills reproduce history.
- Declare `loaded_at_field` and `warn_after`/`error_after` freshness on sources.
- Snapshots need `unique_key` and a `timestamp` (with `updated_at`) or `check` strategy.
- Field names assume manifest v10+ (dbt 1.5+); older manifests can only add findings.

## Checks

- Are there any `error` findings left?
- Does every incremental model survive a full backfill without duplicates?
- Are mart contracts enforced and versioned?
- Is every model reproducible for a given as-of date?

## Output Contract

Use clear Markdown. Present `Findings` (node, rule, severity, fix) grouped by rule,
then `Model Design` for any model redesigned. Name the runtime symbols
(`review_manifest`, `summarize`).

## Spec-Driven Role

dbt standards become `REQ-*`; primary keys, contracts, incremental safety,
reproducibility, and freshness become testable `AC-*`; duplicate-producing
backfills, silent column drops, and run-date-dependent models become `RISK-*`.
The runtime is `src/quantsmith/pipelines/dbt_review.py`; the spec is
`specs/0112-data-engineering-tooling/`. Hands off to
`data_engineering/data_modeling`, `data_engineering/schema_evolution`, and
`data_quality`.
