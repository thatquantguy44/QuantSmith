# Local knowledge stores (spec 0092)

`knowledge_local/` at the repository root is **gitignored**. It holds the private, real
companions to the committed knowledge packs under `knowledge/`: real source notes, screening
decisions, verified cohorts, vendor evaluation material, and any local indexes. The committed
packs stay synthetic and reviewable; nothing sensitive belongs in them.

```
knowledge/venture_intelligence/          committed, synthetic, reviewable
knowledge_local/venture_intelligence/    ignored, real, yours
  store.yml        declares the domain's access level and owner (copy from this folder)
  memory/          workflow-memory store: inbox/ and catalogs for the 0049 write path
  cohorts/         verified company lists for evaluation
  vendor_notes/    database and vendor evaluation notes
  indexes/         local embedding or index snapshots, if you build any
```

Name each subfolder after the committed pack it pairs with (`credit_risk`, `short_term_markets`,
`venture_intelligence`, ...), so the pairing is obvious. `/research_local/` is the older, separate
market-research staging store and is unchanged.

## Rules

- A gitignored folder stops commits, **not** copies, backups, or screen shares. Keep filesystem
  permissions tight, and give the domain an access level in `store.yml` (default `restricted`).
  Retrieval applies that level before ranking (`quantsmith.pipelines.venture_knowledge`).
- Screening decisions are always `restricted`. Never place a credential, key, or personal email
  address in the store; the `memory` gate scans it when it exists and warns.
- If counsel says a store may not live in a developer checkout, point that one memory store at a
  protected location with `persistence: external` (see `memory_manifest_entry.yml`).
- `git ls-files knowledge_local` must print nothing; a test enforces it.

## Files in this template folder

| File | Use |
| --- | --- |
| `store.yml` | Copy to `knowledge_local/<domain>/store.yml` and fill in |
| `memory_manifest_entry.yml` | Entry to add to `memory/manifest.yaml` (or an external manifest) so the existing memory runtime reads the local store |
| `knowledge_sources_entry.yml` | Entry to add to your local `knowledge_sources.yml` so the `sources` MCP authority and the `knowledge` gate see the store |
