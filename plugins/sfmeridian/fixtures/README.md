# Synthetic Data Disclosure — SFMeridian fixtures (spec `0114`)

- **Artifact:** `plugins/sfmeridian/fixtures/` (`query_repo/**.sql`, `sfmeridian.fixture.yml`)
- **Author:** Joshua Lutkemuller, CFA (spec `0114`)
- **Last updated:** 2026-10-22
- **Reviewer / sign-off:** Joshua Lutkemuller, CFA, 2026-10-22 — approved for
  tests only. Not approved for any real query repository, schema, or answer.

## Priority Check

- [x] Actual sourced data was considered first.
- [x] Real query repositories, schemas, and counterparty data were not used:
      they are adopter-confidential (spec `0113` non-goals), and these
      fixtures exist only to prove the indexer, search, inbox, and loop agent.

## Disclosure Table

| Location (section / chart / field) | What's synthetic | Why real data wasn't used | Generation method | Real-data follow-up |
| --- | --- | --- | --- | --- |
| `query_repo/**.sql` | Every query, table name (`lendable_inventory`, `sec_lending_book`, `program_revenue`, …), column, handle (`desk-analytics`, `lending-lead`), and query ID | A real lending desk's SQL and schema are confidential and adopter-owned | Hand-written by the spec author to cover each indexer path: reviewed, draft, deprecated, unannotated, malformed, inconsistent parameters, duplicate IDs, CTEs, aliases, `USING`, and Oracle/Databricks quoting; no data values, no random sampling | An adopter points `query_repositories` at their own repository in a gitignored `sfmeridian.yml` |
| `sfmeridian.fixture.yml` | Repository and database profile IDs, the `secret_ref` pointer, promoter handles | No real system is configured in a public repository | Hand-written; the `secret_ref` points at nothing | Adopter-local configuration only |

No fixture contains a data value, result row, real security identifier,
counterparty name, or credential.
