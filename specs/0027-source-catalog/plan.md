# Plan: Data Source Catalog

- **Spec:** 0027-source-catalog (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Add `sources/` as a directory-per-source catalog, its schema template, one
filled-in public reference entry, an index, and a gate — then wire the
three existing pieces that should have been pointing at a catalog all
along (`data_contract.md`, `credential_access`, `data_ingestion`) to
reference it instead of leaving connection/quality/PIT metadata implicit.

## Architecture & Components

```text
templates/data/source_catalog_entry.yml   (schema template, placeholders)
sources/
  README.md          (index: table + how-this-connects + data-safety note)
  fred.yml            (filled-in public reference, like specs/0001)
  <source-id>.yml      (real entries, added by adopters)

hooks/stages/source-catalog-check.sh
  1. required fields present per entry (alert-contract-check.sh idiom)
  2. every entry indexed (spec-index-check.sh idiom)
  3. credential_ref token-shape heuristic (reuses secret-scan-check.sh's regex)

Wiring:
  data_contract.md        --Source: sources/<source-id>.yml
  credential_access/       --resolves what credential_ref names
  data_ingestion/*         --checks sources/ before wiring a new connection
  data_quality.md          --quality block is the starting assessment
  point_in_time.md         --point_in_time block is the starting PIT answer
```

## Interfaces & Data Contracts

The per-source schema is defined in full in
`templates/data/source_catalog_entry.yml`'s comments and reproduced in
`instructions/data_source_catalog.md`. No other schema in this slice.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P9 Security & data | yes | `credential_ref` is a pointer by contract, checked by the gate's token-shape heuristic; the catalog itself is explicitly *not* where secrets or (by convention) genuinely undisclosable company detail live. |
| P4 Correct by construction | yes | Point-in-time and quality characteristics are registered once at the source, so every downstream dataset starts from a stated answer instead of re-deriving or assuming one. |
| P10 Honest reporting | yes | `quality.completeness: unknown` is a valid, expected value in the template — the schema doesn't force a confident-sounding default. |
| P5 Reversibility | yes | Docs/template/gate-only change, isolated on a branch. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `templates/data/source_catalog_entry.yml` | T-001 |
| REQ-002 | `sources/README.md`, `sources/fred.yml` | T-002 |
| REQ-003 | `hooks/stages/source-catalog-check.sh` | T-003 |
| REQ-004 | `templates/data/data_contract.md`, `credential_access/{README,instructions}.md`, `data_ingestion/{README,*/instructions}.md` | T-004 |
| NFR-001 | Gate tested in clean/missing-field/unindexed/token-shaped states | T-003 |
| NFR-002 | Validation gates | T-005 |
| NFR-003 | Reuse of `secret-scan`'s token patterns | T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| File layout | One file per source under `sources/` | A single `data_sources.yml` manifest, matching `knowledge_sources.yml` | A source catalog scales to many independently-owned, independently-changing entries — the same reasoning that already justifies `specs/NNNN-slug/` and `agents/*/` over a single file in this repo. Explained to the user as the explicit fork before building. |
| Git-tracking stance | `sources/*.yml` is meant to be tracked | Gitignore real entries by default, mirroring `role_context.yml`/`model_plugins.yml` | A source catalog is a shared team artifact by nature (the whole point of centralizing it); `role_context.yml`/`model_plugins.yml` are personal/proprietary local config, a different category. Stated explicitly as a Non-Goal so the distinction isn't lost. |
| Credential heuristic | Reuse `secret-scan`'s exact token-format regex | Invent a new pattern set for this gate | Consistency and proven precision beat a second, slightly different heuristic to maintain. |
| Reference example | FRED (public, already documented in `adapters/data_access/external_apis/fred.md`) | A synthetic/fictional example source | A real, safe, already-referenced public source demonstrates the schema without inventing a fake one, and reinforces the existing `external_apis/` documentation rather than duplicating it. |

## Validation Strategy

Run `hooks/stages/source-catalog-check.sh` directly in four states (the real
`fred.yml`, an unindexed copy, a copy missing a required field, a copy with
a token-shaped `credential_ref`) to confirm AC-001 through AC-004, then
`hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index
secret-scan source-catalog`, then the full `pytest tests/ -q` and `git diff
--check`. AC-005 is covered by direct inspection of the three wired files.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; the gate is additive to `run-stage.sh`'s `ALL` list and
does not change any existing gate's behavior.

## Open Questions

- Does a dedicated source-registration review agent become worth building
  once the catalog has enough entries that manual review doesn't scale?
