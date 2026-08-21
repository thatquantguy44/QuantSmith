# Data Source Catalog Instructions

## Purpose

Use this instruction set to register and maintain the inventory of data
sources a workflow draws on — APIs, databases, vendor feeds, websites. It
backs `sources/` (see `sources/README.md` for the index and
`templates/data/source_catalog_entry.yml` for the schema). The goal is one
centralized, reviewable catalog answering three questions for every source
in use: what is it, how good is it, and how do I connect to it — without
ever storing the connection secret itself.

This is distinct from, and upstream of, two things already in the SDK:

- `templates/data/data_contract.md` describes a specific **dataset** pulled
  from a source (schema, keys, point-in-time rules). A source catalog entry
  describes the **origin** that dataset came from; a `data_contract_refs`
  field links the two.
- `adapters/data_access/external_apis/*.md` documents the **generic
  technical mechanics** of a known public API (FRED, SEC EDGAR, Treasury,
  …) — reusable across any adopter. A `sources/*.yml` entry is the
  **adopter's own registration** that they actually use it, with their own
  quality assessment, credential pointer, and status.

## Required Inputs

- The source's identity, type, and owner.
- A plain-language description of what it provides and why it's used.
- An honest quality assessment (completeness, timeliness, known issues) —
  not a vendor's marketing claim.
- Point-in-time characteristics: does it support as-of queries, what is its
  revision policy.
- Connection method and a **pointer** to where the credential lives — never
  the credential itself.

## Expected Output

- One `sources/<source-id>.yml` file per source, conforming to
  `templates/data/source_catalog_entry.yml`.
- An entry in `sources/README.md`'s index table.
- A `credential_ref` naming a secret-manager key or environment variable —
  resolved at runtime by `agents/secrets_management/credential_access`,
  never inlined as a value here.

## Standards

- **One file per source.** Many small, independently reviewable files beat
  one large manifest that generates merge conflicts and hides a single
  source's change in a big diff — the same reasoning behind `specs/NNNN-slug/`
  and `agents/*/` in this SDK.
- **Point to the secret, never paste it.** `credential_ref` is a name or
  path into a secrets manager / environment, checked by the `source-catalog`
  gate's heuristic scan for anything that looks like an actual key value.
- **Quality is stated, not assumed.** A source with unknown or unassessed
  quality says so (`completeness: unknown`) rather than defaulting to
  "high."
- **Point-in-time characteristics are explicit.** A source that only serves
  latest/restated values is marked as such — this is exactly the leakage
  surface `instructions/point_in_time.md` exists to catch, one layer
  upstream of where a feature or backtest would hit it.
- **Every dataset pulled from a source traces back to it.** A
  `data_contract.md` for a dataset should name the `source_id` it came
  from; a source entry lists the `data_contract_refs` that depend on it.

## Checks

- Does every `sources/*.yml` file declare the required fields (source_id,
  name, type, owner, description, access_level, quality, connection,
  status)?
- Is every file in `sources/` listed in `sources/README.md`'s index?
- Does `credential_ref` look like a pointer (a name/path), not a pasted
  secret value?
- Is the point-in-time behavior (`supports_asof`, `revision_policy`)
  stated, not left blank?
- Does a dataset's `data_contract.md` name the `source_id` it traces to?

## Common Failure Modes

- A credential value pasted into `credential_ref` "just for now."
- A source registered once and never revisited — `quality.last_assessed`
  goes stale and nobody notices because nothing checks it.
- A restated-data source used as if it were point-in-time because nobody
  marked `revision_policy`.
- Datasets with no `source_id` back-reference, so a data-quality incident
  can't be traced to its origin without asking around.

## Spec-Driven Alignment

This standard backs `sources/` (spec `0027-source-catalog`). "Every source
contract-complete" and "every dataset traces to a source" become testable
`AC-*`/`NFR-*`; a pasted credential value or an unmarked revision policy
become `RISK-*`. Backed operationally by the `source-catalog` gate
(`hooks/stages/source-catalog-check.sh`). See
`instructions/data_quality.md`, `instructions/point_in_time.md`, and
`agents/data_ingestion/` (the agents that consume a registered source when
pulling a dataset from it).
