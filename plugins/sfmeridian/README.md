# SFMeridian

Securities finance intelligence plugin (QuantSmith specs `0113`–`0120`):
grounded answers to securities-lending questions from your own databases,
learned from a configurable repository of reviewed SQL queries, with
structural limits on hallucination. A separate distributable (`sfmeridian`)
that apps embed without the rest of QuantSmith.

**Status: 0.1.0 — Phases 1, 2, and 2b (`0114`, `0115`, `0121`).** Shipped:
configuration, query-repository indexing (local, pinned Git, object store),
cited exemplars and learned structure (join graph, metric candidates, filter
patterns), search, the reviewed feedback inbox, governance catalogs, the
shared tool registry, the agent loop harness; schema catalog snapshots,
drift exclusion, the governed semantic mapping, metric-source availability,
pack-amendment proposals, and access controls (`0115`); adaptive dataset
research (`0121`); three loop agents, `query_librarian`,
`semantic_mapping_steward`, and `lending_data_researcher`; and the first three
`0116` slices (executable fixture, token-bound verifier, four-dialect policy,
cost guard, and query-only execution with redaction/provenance/replay). Not
yet: SQL composition, governed Reader/routing, and agents (remaining `0116`),
grounded answers and the evaluation gate (`0117`), the MCP server and Claude
Code plugin (`0118`).

**Contributors:** current state, the next build (`0116`), open decisions, and
repo conventions are in `specs/0113-seclending-intelligence-plugin/handoff.md`.

Standard library only (Python 3.11+); no runtime dependencies. The governed
bridge (`sfmeridian.governed`) uses the QuantSmith SDK when it is importable
(`0081` pack resolution and validation, `0008` metric compilation) and
otherwise reads packs as JSON from `governed_tier.packs_root`.

## Quick start

```sh
cp ../../templates/sfmeridian/sfmeridian.yml ./sfmeridian.yml   # gitignored; fill in your repos
export PYTHONPATH=src
python -m sfmeridian --config sfmeridian.yml config validate
python -m sfmeridian --config sfmeridian.yml index
python -m sfmeridian --config sfmeridian.yml search "utilization by security"
python -m sfmeridian --config sfmeridian.yml agent run query_librarian --save
python -m sfmeridian --config sfmeridian.yml agent run semantic_mapping_steward --save
python -m sfmeridian --config sfmeridian.yml tool list
```

Try it on the synthetic fixtures: `--config fixtures/sfmeridian.fixture.yml`
(indexing), `--config fixtures/sfmeridian.mapping.yml` (catalog, mapping,
access).

## Schema catalog, semantic mapping & access (`0115`)

- **Catalog** (`catalog.<profile>`): `source: file` reads a declared catalog;
  `source: introspect` runs fixed dictionary `SELECT`s through a connection
  the host injects (`clients["connections"][profile]["connect"]`). Snapshots
  are content-addressed under `<index.dir>/catalog/<profile>/`; `catalog.diff`
  classifies changes; `catalog.reconcile` excludes exemplars that reference
  missing objects from search (`drift_policy: exclude`).
- **Mapping** (`semantic_mapping.<profile>`): bind `0081` pack metrics, the
  shipped pack-amendment proposals (`data/pack_amendments.json`), or `0063`
  concepts to catalog columns with viewpoint, unit, PIT column, owner, and
  evidence (a reviewed exemplar reading the column, or a promoter's
  confirmation). `mapping.validate` reports every binding, every governed
  metric (bound, invalid, or unbound with what is missing), and every
  `governed_tier.metric_sources` entry (available or unavailable).
- **Pack review**: the `securities_financing_prime` pack is `draft`; its named
  reviewer is Joshua Lutkemuller, CFA. Amendments are staged for review
  (`mapping.propose_amendment`), never written into the pack.
- **Access**: `access.clearance_source` names a `0058` roster; columns in
  `access.column_classes` whose class requires more clearance than the
  caller has are withheld from research and flagged in `catalog.describe`.

## For app developers

Apps depend only on the tool contract (`sfmeridian.tools.default_registry()`;
`CONTRACT_VERSION` follows SemVer). Agents use the same tools through the loop
harness (`sfmeridian.agent.run_agent`); decisions reserved for people
(`feedback.promote`, `feedback.discard`) are `human_only` and never granted to
an agent. Inject a language model by passing a completion function to
`sfmeridian.agent.ModelPolicy`; nothing in the package calls a network.

## Query front-matter

See `templates/sfmeridian/query_front_matter.sql`. Files without
front-matter index as `unreviewed`; malformed or inconsistent files are
rejected with a reason; only `reviewed` files serve as primary exemplars.
