# Data Ingestion Agents

This folder groups agents that bring external data into a quant workflow —
database and warehouse connections, file reading across formats, and API pulls.

They share a common job: turn a raw source into a typed, validated, reproducible
dataset with a data contract, without leaking secrets or the future.

## Agents

| Agent | Handles |
| --- | --- |
| `database_connectivity/` | SQL databases and warehouses (Postgres, Snowflake, BigQuery, …): connections, safe queries, point-in-time pulls, snapshots. |
| `file_ingestion/` | Files across formats (CSV, Parquet, Excel, JSON/JSONL, XML, fixed-width, …): typed loading, encoding, schema, chunking. |
| `api_ingestion/` | REST / streaming / vendor APIs: auth, pagination, rate limits, retries, as-of capture, raw payload archival. |

## Group Workflow

```
sources/<source-id>.yml (catalog lookup)
  → database_connectivity | file_ingestion | api_ingestion
  → typed, validated snapshot → data contract + dataset card → data_quality
```

Before connecting, check `sources/` for the source's registered connection
method, quality notes, and `credential_ref` (resolved via
`agents/secrets_management/credential_access`, never inlined). Choose the
ingress agent by source type. Every path converges on the same output: an
immutable or reproducibly identified dataset, explicit schema and
point-in-time semantics, and the contracts required by downstream quality
checks — with the resulting `data_contract.md` naming the `source_id` it
traces to. See `instructions/data_source_catalog.md`.

## Shared Principles

Every ingestion agent upholds the constitution (`instructions/engineering_principles.md`)
and, in particular:

- **Secrets never enter the repo** (P9). Credentials come from environment or a
  secrets manager; connection strings and keys are never committed or logged.
- **Reproducible by construction** (P4). Capture a point-in-time snapshot with an
  identifier/hash so the same pull can be reproduced. Prefer immutable snapshots
  over "latest".
- **Point-in-time correctness.** Record when each field was actually knowable
  (publication/revision lag); avoid pulling revised data as if it were original.
  See `instructions/point_in_time.md`.
- **Typed and validated, not inferred-and-hoped.** Declare the schema; validate on
  load; fail loudly on contract violations.
- **Emit a data contract.** Output `templates/data/data_contract.md` (schema, keys,
  point-in-time rules, missingness) and a dataset card. Feeds the `data_quality`
  agent and the `data-contract-check` hook.

Each agent's own `instructions.md` states its format-specific rules; the shared
rules across all three (source-catalog lookup, credential resolution, snapshot
capture, point-in-time, load-time validation) live once in
`instructions/data_ingestion.md`.

## Where They Fit

Ingestion agents supply the Planning and Design stages: they establish what data
exists, how it is shaped, and what can be relied on — before features or models
are built on top of it.
