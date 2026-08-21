# Data Source Catalog

The centralized inventory of data sources a workflow draws on — APIs,
databases, vendor feeds, websites — one file per source. See
`instructions/data_source_catalog.md` for the standard this catalog follows.

```
sources/
  <source-id>.yml    # one file per source, from templates/data/source_catalog_entry.yml
```

- `<source-id>` is a short, stable, kebab-case slug (matches the file's
  `source_id` field).
- Start from `templates/data/source_catalog_entry.yml`.
- The `source-catalog` hook (`hooks/stages/source-catalog-check.sh`)
  verifies every file here declares the required fields and is listed in
  the index below, and heuristically flags anything in `credential_ref`
  that looks like a pasted secret rather than a pointer.

## Index

| Source ID | Name | Type | Access | Status | Quality |
| --- | --- | --- | --- | --- | --- |
| [`fred`](fred.yml) | FRED / ALFRED (macro time series) | api | public | active | high |
| [`bls`](bls.yml) | BLS (labor market, CPI, PPI, wages) | api | public | active | high |
| [`eia`](eia.yml) | EIA (energy production, consumption, prices) | api | public | active | high |
| [`bea`](bea.yml) | BEA (GDP, personal income, national accounts) | api | public | active | high |
| [`census`](census.yml) | U.S. Census Bureau (economic, demographic, housing) | api | public | active | high |
| [`sec_edgar`](sec_edgar.yml) | SEC EDGAR (filings, XBRL, disclosure metadata) | api | public | active | high |

`fred.yml` is a filled-in reference showing the schema in use — the same
role `specs/0001-daily-momentum-signal/` plays for the spec format. Copy
its structure, not its content, for a real source. `bls`, `eia`, `bea`, and
`census` require or accept a free-registration API key (see each entry's
`connection.credential_ref`); `sec_edgar` requires a compliant User-Agent
header instead of a key.

## How This Connects

- **Datasets** — a dataset pulled from a registered source gets its own
  `templates/data/data_contract.md`; name the source's `source_id` in the
  contract's `Source` field, and list the contract's path in the source
  entry's `data_contract_refs`.
- **Credentials** — `connection.credential_ref` names a secrets-manager
  path or environment variable, never a value. Retrieval at runtime is
  `agents/secrets_management/credential_access`'s job.
- **Ingestion** — `agents/data_ingestion/{database_connectivity,
  file_ingestion,api_ingestion}/` look up a source's connection method and
  quality notes here before pulling from it.
- **Generic API mechanics** — for a known public API, the *technical*
  delivery rules (pagination, required metadata, vintage handling) live in
  `adapters/data_access/external_apis/*.md`, reusable across any adopter.
  The `sources/*.yml` entry is this repo's own registration that it's
  actually in use, with an owner, a quality assessment, and a status.

## Data Safety

A source entry is metadata and a connection pointer — never a credential
value, and, per this repository's own constraint, never company-specific
detail beyond what's needed to identify and connect to the source. Real,
sensitive connection specifics (an internal hostname, an internal system
name) are fine to register here using the same discretion any other
tracked file in this repo requires; if a source is genuinely too sensitive
to name at all, register it with a generic `name`/`description` and keep
the identifying detail in whatever your `credential_ref` points at instead.
