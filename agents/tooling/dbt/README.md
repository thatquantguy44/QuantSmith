# dbt Agent

## Purpose

The dbt Agent brings the SDK's data-contract and reproducibility discipline to dbt
projects. It reviews the compiled `manifest.json` for unowned models, missing
primary-key tests, unenforced contracts on public and mart models, unsafe
incremental models, wall-clock reads, unchecked source freshness, and misconfigured
snapshots, and it designs dbt models that are safe to backfill and replay.

## Use When

- A dbt project feeds research, signals, or reports and needs a correctness review.
- An incremental model duplicates or drops rows on re-run or backfill.
- Mart models need enforced contracts before downstream consumers rely on them.
- A model's output changes depending on the day it runs.

## Inputs

- The compiled `target/manifest.json` (from `dbt parse` or `dbt compile`).
- Which folders or `access: public` models are marts that need enforced contracts.
- The project's backfill and point-in-time requirements.

## Outputs

- Sorted findings from `review_manifest` (node, rule, severity, fix).
- Model designs: grain, `unique_key`, `is_incremental()` filters, `on_schema_change`,
  contracts, primary-key tests, source freshness, snapshots.
- Handoffs to `data_engineering/data_modeling`, `schema_evolution`, and `data_quality`.

## Example Requests

- "Review our dbt project before we point the factor models at it."
- "Our incremental trades model double-counts after backfills — why?"
- "Which mart models lack enforced contracts or primary-key tests?"
- "Make this model reproducible for a given as-of date."

## Required Review Themes

- Every model has an owner and a tested primary key.
- Public/mart models have enforced contracts.
- Incremental models have a `unique_key`, an `is_incremental()` filter, and a
  non-`ignore` `on_schema_change`.
- No model reads the wall clock; the as-of date is a var.
- Sources declare `loaded_at_field` and freshness thresholds.
