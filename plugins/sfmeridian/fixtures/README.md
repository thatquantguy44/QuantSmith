# Synthetic Data Disclosure — SFMeridian fixtures (specs `0114`, `0115`, `0116`, `0121`)

- **Artifact:** `plugins/sfmeridian/fixtures/` (`query_repo/**.sql`, `sfmeridian.fixture.yml`)
- **Author:** Joshua Lutkemuller, CFA (spec `0114`)
- **Last updated:** 2026-10-23
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
| `research/fixture_db.py` (builds `lending.sqlite` at test time), `research/sfmeridian.research.yml`, `research/contexts/*.yml` | Every loan, security, counterparty, account (`ACCT-…`), region, fee, quantity, collateral value, revenue figure, and timestamp, including the planted issues (missing APAC fees on 2026-10-14, a duplicate row, a negative fee, a zero quantity, a status typo, a prompt-injection note, utilization above 1, a category mismatch, inverted and late-published rates, a naive timestamp column, a margin shortfall, an accrual mismatch, a split above 1, a missing business date) | Real lending books, rates, and collateral are confidential and adopter-owned | Deterministic loops in `fixture_db.py` (no random sampling); planted values are literal and listed in its `EXPECTED` | An adopter declares real datasets in a gitignored `sfmeridian.yml` |
| `research/poc_synthetic_positions.csv` | The Dataset Intake Investigator POC's synthetic positions file, copied unchanged for the intake regression test | Same as the POC's own disclosure: a synthetic intake example | Hand-written by the POC author | None needed |
| `catalog/fixture_db.catalog.json`, `catalog/fixture_db.catalog.v2.json` | Every schema, table, column, type, key, and row-count estimate of the `fixture_db` profile, and the v2 changes (a dropped `sec_lending_book.status`, a retyped `borrow_rates.fee_bps`, an added `lendable_inventory.region`) | A real warehouse catalog is confidential and adopter-owned | Hand-written to match the tables and columns the fixture query repository references (spec `0115`); no data values | An adopter introspects their own profile or declares a catalog file in a gitignored `sfmeridian.yml` |
| `execution/fixture_db.py` (builds `fixture.sqlite` plus its attached `fixture.lending.sqlite` at test time), `execution/expected_results.json` | Every loan, inventory record, rate, revenue row, collateral balance, counterparty, and recall used to execute the reviewed fixture queries, plus their expected result rows | Real lending books and query results are confidential and adopter-owned | Deterministic literal rows in `fixture_db.py` (no randomness); synthetic IDs use `SEC-*`, `CP-*`, `LOAN-*`, and `RECALL-*`; expected results are reviewed alongside the seed | An adopter injects a read-only connection to the profile declared in their gitignored configuration |
| `access/roster.yml` | A `0058`-shaped roster with two fixture handles (`lending-lead`, `desk-analytics`) and their clearances | A real roster names real people's clearances | Hand-written; handles are fixture handles, not people | An adopter points `access.clearance_source` at their own `0058` roster |
| `sfmeridian.mapping.yml` | Concept bindings, metric sources, owners, column classes, and evidence references for the `fixture_db` profile | A real semantic mapping encodes an adopter's schema | Hand-written over the synthetic catalog and query repository (spec `0115`) | Adopter-local configuration only |
| `sfmeridian.fixture.yml` | Repository and database profile IDs, the `secret_ref` pointer, promoter handles | No real system is configured in a public repository | Hand-written; the `secret_ref` points at nothing | Adopter-local configuration only |

No fixture contains a real data value, result row, security identifier,
counterparty name, or credential. Synthetic execution values and result rows
are confined to the disclosed `execution/` fixture.
