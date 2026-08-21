# Data Ingestion Standard

How QuantSmith brings external data — databases, files, and APIs — into a
workflow reproducibly, point-in-time correctly, and without leaking a
secret or the future. This is the shared standard behind
`agents/data_ingestion/{database_connectivity,file_ingestion,api_ingestion}/`.
Each of the three agents already states its own format-specific operating
rules (SQL safety, file parsing, API pagination); this standard is the one
place the rules they all share live, so a shared rule is fixed once instead
of drifting across three copies.

## Why This Standard

Every ingestion path — SQL, file, or API — fails the same three ways
regardless of format: it captures "latest" instead of a reproducible
point-in-time snapshot, it inlines a credential instead of resolving one, or
it trusts the raw payload's shape instead of validating it. Fixing these
once, at the ingestion boundary, is cheaper than catching them downstream in
every feature, model, or backtest that depends on the pull.

## Rules

1. **Check the source catalog first.** Before wiring a new connection, look
   up `sources/<source-id>.yml` for the registered connection method,
   quality notes, point-in-time characteristics, and `credential_ref`. See
   `instructions/data_source_catalog.md`. If the source isn't registered
   yet, register it rather than connecting around the catalog.
2. **Credentials are resolved, never inlined.** `credential_ref` names a
   secrets-manager path or environment variable; the actual value is
   retrieved through `agents/secrets_management/credential_access` at
   runtime. A credential value never appears in code, logs, or a committed
   file (constitution P9).
3. **Capture a reproducible snapshot, not "latest."** Every pull records an
   identifier or content hash, the exact query/parameters/endpoint used, and
   an as-of timestamp, so the same pull can be reproduced later
   (constitution P4). Prefer an immutable snapshot over a live "current
   state" read whenever the downstream use needs to be reproducible.
4. **Respect point-in-time.** Use the data's actual availability (publication
   and revision lag), not when it was convenient to pull. Use original
   vintage, not the latest revision, unless the workflow explicitly wants
   restated data and says so. See `instructions/point_in_time.md`.
5. **Validate on load; don't trust the payload's shape.** Declare an explicit
   schema and fail loudly on a violation — a type mismatch, an unexpected
   null, a broken key — rather than silently coercing or dropping bad rows.
6. **Make the pull idempotent and bounded.** Re-running a pull must not
   duplicate or corrupt data; bound volume (partitioning, paging, chunking)
   rather than pulling unbounded ranges by default.
7. **Emit a data contract.** Every ingestion path ends in
   `templates/data/data_contract.md` (schema, keys, point-in-time rules,
   missingness) naming the `source_id` it traces to, feeding `data_quality`
   and the `data-contract-check` gate.

## Checklist

- [ ] The source is checked against `sources/` before a new connection is
      wired (or registered there if new).
- [ ] Credentials are resolved via `credential_access`, never inlined or
      logged.
- [ ] The pull captures a reproducible snapshot (identifier/hash, as-of
      timestamp, exact query/params/endpoint).
- [ ] Point-in-time is respected: original vintage, actual availability, no
      look-ahead.
- [ ] The load validates schema/types/keys and fails loudly on violation.
- [ ] The pull is idempotent and bounded (chunked/paged/partitioned as
      needed).
- [ ] A `data_contract.md` is emitted, naming the source's `source_id`.

## Runtime & Spec

- Agents: `agents/data_ingestion/database_connectivity/` (SQL/warehouse),
  `agents/data_ingestion/file_ingestion/` (file formats),
  `agents/data_ingestion/api_ingestion/` (REST/streaming/vendor APIs) — each
  adds its own format-specific rules on top of this shared standard.
- Backed by: `instructions/data_source_catalog.md` (the registry these
  agents check first), `instructions/point_in_time.md` (leakage/PIT
  detail), and `agents/secrets_management/credential_access` (credential
  resolution).
- Feeds: `templates/data/data_contract.md`, `agents/data_quality/`, and
  `instructions/reproducibility.md` (the snapshot/reproducibility
  requirement this standard states for ingestion specifically).
