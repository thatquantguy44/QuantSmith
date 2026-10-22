# SFMeridian

Securities finance intelligence plugin (QuantSmith specs `0113`–`0120`):
grounded answers to securities-lending questions from your own databases,
learned from a configurable repository of reviewed SQL queries, with
structural limits on hallucination. A separate distributable (`sfmeridian`)
that apps embed without the rest of QuantSmith.

**Status: 0.1.0 — Phase 1 (`0114`).** Shipped: configuration, query-repository
indexing (local, pinned Git, object store), cited exemplars and learned
structure (join graph, metric candidates, filter patterns), search, the
reviewed feedback inbox, governance catalogs, the shared tool registry, the
agent loop harness, and the first loop agent, `query_librarian`. Not yet:
schema catalogs and semantic mapping (`0115`), SQL composition, verification,
and execution (`0116`), grounded answers and the evaluation gate (`0117`),
the MCP server and Claude Code plugin (`0118`).

Standard library only (Python 3.11+); no runtime dependencies.

## Quick start

```sh
cp ../../templates/sfmeridian/sfmeridian.yml ./sfmeridian.yml   # gitignored; fill in your repos
export PYTHONPATH=src
python -m sfmeridian --config sfmeridian.yml config validate
python -m sfmeridian --config sfmeridian.yml index
python -m sfmeridian --config sfmeridian.yml search "utilization by security"
python -m sfmeridian --config sfmeridian.yml agent run query_librarian --save
python -m sfmeridian --config sfmeridian.yml tool list
```

Try it on the synthetic fixtures: `--config fixtures/sfmeridian.fixture.yml`.

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
