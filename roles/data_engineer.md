# Data Engineer Role

## What You Do

You own data pipelines, quality, observability, and contract enforcement. Your job is to get clean, validated, point-in-time-correct data to researchers and portfolios so their work is trustworthy.

## Your Core Agents

**Pipeline Design & Execution:**
- `data_engineering/pipeline_builder/` — compile source → transform → sink intent into a DAG + readiness review
- `data_engineering/pipeline_orchestration/` — execute DAG with idempotent, partitioned, retry-safe runs
- `data_engineering/pipeline_deployment/` — promote pipelines across environments (dry-run → canary → production)

**Data Quality & Contracts:**
- `data_ingestion/` group agents (database, file, API) — pull external data safely
- `data_ingestion/data_quality/` — validates schema, keys, missingness, freshness
- `data_quality/` — deep lineage/join/timestamp/leakage review

**Observability & Operations:**
- `data_engineering/pipeline_observability/` — monitors freshness, SLA, downtime, lineage
- `data_engineering/data_governance/` — catalog, ownership, access policy, classification
- `data_engineering/data_modeling/` — dimensional/warehouse design (grain, keys, slowly-changing)

**Handoff Partners:**
- → **Quant Researcher** provides validated datasets with data contracts
- → **Portfolio Manager** provides real-time market/position data
- → **Risk Manager** provides risk factors (vols, correlations) with SLAs
- ← **Everyone** requests data; you enforce contracts and SLAs

## Your Key Specs

| Spec | What | Use When |
| --- | --- | --- |
| `0011-data-pipeline-orchestration` | DAG runner with no hand-coding | Executing a declared source → transform → sink pipeline |
| `0019-pipeline-observability` | Freshness/SLA/lineage monitoring | Tracking pipeline health and detecting data downtime |
| `0042-pipeline-builder` | Design-time DAG compiler + readiness review | Planning a pipeline before you code it |
| `0027-source-catalog` | Centralized source registry | Cataloging APIs/DBs/feeds with quality/point-in-time/credential metadata |
| `0039-ingestion-data-contract` | Validates row sets against declared contracts | Checking ingested data for schema/key/quality breaches |

## Your Quality Gates

**Critical:**
- `pipeline-contract` — your manifests must be validated against the checklist
- `data-contract` — ingested data must pass contract validation
- `data-provenance` — no synthetic data in production without disclosure
- `secret-scan` — credentials must never touch your code/logs

**Informational:**
- `role-context` — domain-specific data requirements (e.g., point-in-time for backtesting)

## Development Workflow

```
1. Receive a data request (e.g., "I need daily returns by ticker, 5 years, real-time")
   ↓
2. Source discovery via source_catalog (0027)
   ↓
3. Design pipeline intent:
     - Source: Yahoo Finance API, CRSP database, vendor feed
     - Transform: clean nulls, handle splits, calc returns, lag for point-in-time
     - Sink: Parquet partitioned by date/ticker + real-time Kafka topic
   ↓
4. Use pipeline_builder (0042) to compile intent → DAG + readiness review
   ↓
5. Code transforms (Python/SQL); unit test each step
   ↓
6. Define data contract (schema, keys, freshness SLA, quality rules)
   ↓
7. Test ingestion via 0039 contract validator
   ↓
8. Deploy via pipeline_deployment (dev → staging → prod)
   ↓
9. Wire monitoring via pipeline_observability (0019)
   ↓
10. Live on production; watch SLA and trigger alerts on breach
```

## Common Workflows

- **"Build a data pipeline"** → pipeline_builder (0042) design → orchestration (0011) execution → observability (0019) monitoring
- **"Validate this data source"** → data_quality → ingestion_data_contract (0039)
- **"What's the lineage for returns?"** → pipeline_observability (0019) lineage + source_catalog (0027)
- **"Why did yesterday's run fail?"** → pipeline_orchestration logs + observability dashboards
- **"Set up SLA monitoring"** → pipeline_observability (0019) for this dataset

## Handoff Details

**To Quant Researcher:**
- "Here's your daily CRSP returns data, validated against the data contract"
- Data contract includes: schema (date, ticker, return), quality rules (no nulls, no duplicates), SLA (delivered by 8am ET)
- Point-in-time lag documented: "Returns for day D are available by 5pm D+1"

**To Portfolio Manager:**
- "Real-time market data is live; you can rebalance intraday"
- "If SLA is breached, you'll get an alert + decision log entry"

**To Risk Manager:**
- "Factor volatilities updated daily at 5pm; correlations weekly at 8am Monday"
- "Macro data (FRED, BLS) has publication lag; we cache vintages for point-in-time"

**From Quant Researcher:**
- "I need these fields from CRSP: permnumber, date, ret, vol30; point-in-time for 1990-2023"
- "Data must be embargoed (no lookahead) for backtesting"

## Specs You Reference But Don't Own

- `0006-ml-return-forecasting` (quants use your data)
- `0044-backtesting` (backtest engine uses your data; you ensure no look-ahead)
- `0046-walk-forward` (fold construction relies on your point-in-time correctness)

## What You Don't Own

- Signal development (that's quant researcher)
- Risk calculation (that's risk manager; you give them data)
- Backtest logic (quants own that; you ensure data is clean)
- Model governance (that's compliance)

## Critical Principles

1. **Point-in-time correctness** — data available for date D on or after D (never before)
2. **No synthetic data in production** — mark synthetic with disclosure
3. **Data contracts everywhere** — every dataset has schema + quality rules + SLA
4. **Observability by default** — monitor freshness, lineage, SLA; alert on breach
5. **Credentials never in code** — use credential_access agents for secrets
