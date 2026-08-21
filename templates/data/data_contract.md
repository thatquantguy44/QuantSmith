# Data Contract: <dataset name>

- **Owner:**
- **Source:** `sources/<source-id>.yml` — see the data source catalog (`sources/README.md`)
  for connection, quality, and point-in-time notes for the origin; this contract
  covers the dataset itself.
- **Spec:** NNNN-short-slug (if applicable)
- **Last updated:** YYYY-MM-DD

> A data contract states what a consumer can rely on. It is checkable: the
> `data-contract-check` hook looks for schema, keys, point-in-time rules, and
> missingness rules.

## Grain & Keys

- **Grain:** one row per … (e.g. per (date, security)).
- **Primary/join key(s):** …
- **Uniqueness:** the key is unique per grain (no duplicates).

## Schema

| Column | Type | Nullable | Description |
| --- | --- | --- | --- |
| date | date | no | Observation date |
| security_id | string | no | Point-in-time security identifier |
| … | … | … | … |

## Point-in-Time Rules

- Availability: each field is knowable as of … (state publication/revision lag).
- Vintage: use original vintage, not latest revision? yes/no.
- As-of join semantics: … (how consumers should join without look-ahead).

## Missingness & Quality Rules

| Rule | Threshold | Action on breach |
| --- | --- | --- |
| Max missing per column | e.g. < 1% | fail load / alert |
| Duplicate keys | 0 | fail load |
| Value range check | e.g. price > 0 | quarantine row |
| Freshness | updated by … | alert |

## Lineage & Access

- Upstream dependencies: (name the `source_id` from `sources/`; add this
  contract's path to that source's `data_contract_refs`)
- Access constraints / private-data handling:
- Refresh schedule:

## Change Policy

How schema or semantics may change, and how consumers are notified (versioning).
