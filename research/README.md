# Market Research Reference Store

A committed, **fictional-content-only** reference store demonstrating the target
metadata schema of `specs/0056-market-research-knowledge-base/` (status: Draft).
It backs the **Research** view in `apps/knowledge-console` (the terminal).

## What this is — and is not

This is a schema demo, the same role `memory/` plays for `0002`/`0048`: copy the
structure, not the content. It is **not** a compliant implementation of `0056`.
In particular it has none of:

- the knowledge-base MCP interface / `knowledge://market_research/...` namespace (REQ-002, REQ-003)
- entitlement / information-barrier enforcement before retrieval (REQ-006, NFR-001, NFR-008)
- a quarantine pipeline that actually detects secrets/PII/MNPI (REQ-011) —
  `review_status: quarantined` items below are hand-labeled, not detected
- an email connector (REQ-016–019) — `RES-0006` shows the *shape* of a
  tagged-email item, not a working scanner
- audit logging of retrieval decisions (REQ-012, NFR-007)

What it does provide: real, filterable, citable reference data — asset class,
source type, access level, review status, provenance, supersession — so the
terminal's Research view has something honest to render while `0056` is Draft.

**Real firm, client, fund-manager, MNPI, or licensed third-party research must
never be committed here.** Every item in `market_research/index.yaml` is
fictional (fake authors, fake firms, fake tickers) — see `0056`'s Non-Goals.

## Layout

```
research/
  manifest.yaml              # domains, default access level, freshness policy
  market_research/
    index.yaml                # reference items (see field notes in the file)
```

## Read path

`src/quantsmith/knowledge_console/research.py` (`load_research_store`,
`build_research_model`) parses this tree with the same dependency-free YAML
subset parser `0048`'s `workflow_memory` module uses — no new dependency. The
Node terminal app calls it via `python -m quantsmith.knowledge_console research`,
the same pattern it uses for the `memory/`-backed model.
