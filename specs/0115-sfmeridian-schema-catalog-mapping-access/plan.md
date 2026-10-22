# Plan: SFMeridian — Schema Catalog, Semantic Mapping & Access

- **Spec:** 0115-sfmeridian-schema-catalog-mapping-access (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-22

## Approach

Add four standard-library modules and one bridge package to `sfmeridian`, all
reached through new tools in the shared registry so apps and agents see the
same surface:

```text
plugins/sfmeridian/src/sfmeridian/
  catalog.py          # REQ-001–REQ-004: introspect/declared snapshots, store, Resolver, diff, reconcile
  access.py           # REQ-009–REQ-011: 0058 roster clearance, column classes, redact_rows, scrub
  mapping.py          # REQ-005–REQ-008: Vocabulary (pack, amendments, 0063), binding + metric-source validation
  governed/packs.py   # REQ-007, REQ-012: the only quantsmith import (resolve_packs, validate_pack, 0008 compile)
  semantic_tools.py   # REQ-013: catalog.*, mapping.*, metrics.list, glossary.lookup, access.describe
  steward.py          # REQ-014: StewardPolicy, report builder, four verifiers, run_steward
  data/pack_amendments.json                 # REQ-007: proposals in 0081 format, named reviewer
  data/agents/semantic_mapping_steward.json # REQ-014 manifest
```

Changes to existing modules: `config.py` validates `catalog.<profile>`,
binding shapes, and `metric_sources` shapes (meaning is left to
`mapping.validate`); `index.load_index` drops exemplars listed as excluded in
`drift.json`; `tools.ToolRegistry.call` maps `CatalogError` and scrubs error
text; `agent.run_agent` scrubs decision arguments and policy errors in the
trace; `research.start` folds clearance-withheld columns into the research
context's sensitive columns.

## Key Decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Snapshot identity | SHA-256 of profile, dialect, default schema, tables; date only in `history.json` | Unchanged catalogs write nothing; two introspections agree. |
| Introspection SQL | Fixed per dialect; allowlists applied in Python | Nothing caller-supplied reaches SQL; no paramstyle differences. |
| Drift effect | `drift.json` read by `load_index` | Retrieval exclusion without rewriting the index; reversible. |
| Vocabulary | Pack + shipped proposals + `0063` | No plugin-private meaning; proposals are visible and reviewable. |
| Evidence | Reviewed exemplar reading the column, or a configured promoter | Ties every binding to something a person reviewed. |
| Ratio rule | Numerator and denominator are bound, summed measures; ratio dimensions must exist on both | `0008` "same rows" holds by construction; refuses by-counterparty utilization. |
| Rates | `aggregation: none`/`avg`, never `sum`; not compiled to `0008` | Pack additivity; served through metric source queries in `0116`. |
| Pack review | Reviewer recorded in `pack_amendments.json`; pack file untouched | Only the reviewer changes review state, through `0081`. |
| Access | `0058` semantics, fail closed on unreadable roster | Matches the SDK's viewer access control. |
| Credentials | Injected connections; driver errors reduced to type; scrub traces | Nothing secret can be echoed into an artifact. |

## Data Flow

`config.validate` → `repos.index` (0114) → `catalog.snapshot` → `catalog.diff`
→ `catalog.reconcile` (writes `drift.json`; search excludes) →
`mapping.validate` (reads snapshot, exemplars, drift, vocabulary) →
`mapping.amendments` → `mapping.propose_amendment` (writes
`<inbox>/pack_amendments/<id>.json`) → steward report.

## Testing Strategy

`tests/test_sfmeridian_mapping.py` names each `AC-*`. Fixtures: declared
catalogs v1/v2 (`fixtures/catalog/`), a mapping config
(`fixtures/sfmeridian.mapping.yml`), a roster (`fixtures/access/roster.yml`),
the `0114` query repository, and the `0121` research database. Dialect
introspection uses fake DB-API connections that record SQL.

## Deviations

- `0113` A-008's by-counterparty utilization is refused rather than computed
  (see `spec.md` Exceptions).
- `0113` T-032 is split: the binding and availability rules are here; the
  `Reader` that executes metric source queries is `0116`.
