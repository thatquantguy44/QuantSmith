# Data Quality Instructions

## Purpose

Use this instruction set to review datasets, feature tables, labels, joins, and transformations before they support modeling, backtesting, or production workflows.

## Required Inputs

- Dataset name, source, owner, and permissions — if the source is cataloged,
  its `sources/<source-id>.yml` entry's `quality` block is the starting
  point, not a fresh assessment from scratch. See
  `instructions/data_source_catalog.md`.
- Schema and expected grain.
- Date range, frequency, and refresh schedule.
- Primary keys, natural keys, and join keys.
- Timestamp fields and their meanings.
- Transformations, filters, imputations, and exclusions.
- Intended downstream use.

## Expected Output

- Data quality findings.
- Lineage summary.
- Coverage and missingness summary.
- Join and identity risk review.
- Point-in-time correctness assessment.
- Required validation checks.
- Dataset card updates.

## Standards

- Always identify dataset grain.
- Always distinguish event time, effective time, publication time, ingestion time, and availability time when relevant.
- Validate join cardinality before trusting joined data.
- Summarize row counts, entity counts, date ranges, missingness, duplicates, and stale records.
- Treat restatements, revisions, backfills, and vendor corrections as model risk.
- Document whether historical data is point-in-time or current-snapshot.
- Document any exclusions that can create survivorship bias.

## Checks

- Do row counts and entity counts match expectations before and after joins?
- Are duplicate keys expected or accidental?
- Are null rates stable across time, entity type, and source?
- Are timestamp boundaries aligned with the intended decision time?
- Can labels leak future information into features?
- Are filters using future outcomes or current membership lists?
- Are source permissions compatible with intended use?

## Common Failure Modes

- Row explosion after many-to-many joins.
- Using current identifiers or classifications for historical entities.
- Training on restated values that were unavailable at the time.
- Filling missing values in a way that embeds future information.
- Ignoring entities that disappeared before the end of the sample.
- Confusing exchange date, report date, ingest date, and availability date.

## Spec-Driven Alignment

This standard backs Planning and Design. Data-quality findings become `RISK-*`;
data requirements become `REQ-*`/`NFR-*`; unresolved point-in-time or leakage
issues become blocking `AC-*`. Point-in-time correctness is correct-by-construction
(constitution P4), not an after-the-fact warning; see
`instructions/point_in_time.md`. Capture the result as
`templates/data/data_contract.md` so the `data-contract-check` gate and downstream
stages can rely on the schema, keys, PIT rules, and missingness thresholds.
