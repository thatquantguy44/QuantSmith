# dbt Tasks

## Review A dbt Project

Input: `target/manifest.json` and the mart folders.

Output: `review_manifest` findings grouped by rule, with fixes.

## Make An Incremental Model Backfill-Safe

Input: an incremental model that duplicates or drops rows.

Output: `unique_key`, `is_incremental()` filter, `on_schema_change`, and a test.

## Contract A Mart

Input: a public or mart model.

Output: an enforced contract, primary-key tests, and a versioning plan with `schema_evolution`.

## Make A Model Reproducible

Input: a model that reads the wall clock.

Output: an as-of `var` and the backfill command that reproduces history.
