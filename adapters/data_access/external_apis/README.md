# External API Provider Profiles

External API profiles extend the generic `../api.md` adapter contract for
providers whose identifiers, release calendars, revision policies, vintages,
entitlements, or redistribution rules matter to quant workflows.

## Files

| File | Purpose |
| --- | --- |
| `fred.md` | FRED and ALFRED macroeconomic series. |
| `bls.md` | BLS labor, inflation, wage, productivity, and survey data. |
| `bea.md` | BEA national, regional, industry, and international accounts. |
| `census.md` | Census demographic, housing, business, and trade data. |
| `eia.md` | EIA petroleum, natural gas, electricity, coal, and renewables data. |
| `treasury.md` | U.S. Treasury rates, auctions, fiscal, and debt data. |
| `federal_reserve.md` | Federal Reserve statistical releases and board datasets. |
| `ny_fed.md` | NY Fed markets, rates, surveys, and reference datasets. |
| `sec_edgar.md` | SEC EDGAR filings, company facts, submissions, and XBRL data. |
| `finra.md` | FINRA reference, transparency, short interest, and market regulation data. |
| `sp_global.md` | S&P Global Market Intelligence, ratings, indices, and vendor APIs. |

## Standard Metadata

Provider adapters should preserve the fields below whenever available.

```yaml
provider: string
dataset: string
endpoint: string
series_id: string | null
security_id: string | null
observation_date: string | null
period: string | null
release_date: string | null
revision_date: string | null
vintage_date: string | null
frequency: string | null
units: string | null
seasonal_adjustment: string | null
source_url: string
retrieved_at_utc: string
entitlement_context: string | null
point_in_time_safe: boolean
```

## Design Rule

Provider profiles describe source-specific access and validation rules. Agents
decide which data is required; adapters retrieve, timestamp, validate, snapshot,
and return lineage evidence.
