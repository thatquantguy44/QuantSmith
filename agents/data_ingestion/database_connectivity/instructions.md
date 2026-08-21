# Database Connectivity Instructions

## Operating Rules

- Check `sources/<source-id>.yml` first for the registered connection method,
  quality notes, and `credential_ref` before wiring a new connection.
- Source credentials from environment variables or a secrets manager only.
- Never commit or log connection strings, passwords, tokens, or keys.
- Use parameterized queries; never concatenate untrusted values into SQL.
- Request read-only access unless the task genuinely requires writes.
- Select explicit columns and bound the range; avoid `SELECT *` and full scans.
- Apply point-in-time / as-of logic; use original vintage when revisions exist.
- Capture a snapshot (identifier or content hash) and record the exact query.
- Impose a deterministic ordering so repeated pulls are comparable.

## Checks

- Are credentials outside the repo and outside logs?
- Is the query parameterized and read-only where possible?
- Is the extract point-in-time correct, with revision behavior handled?
- Is the pull reproducible: snapshot captured, query and params recorded?
- Is volume bounded (partitioned/paged) and cost considered?
- Is there a data contract describing the extracted schema and keys?

## Output Contract

Use clear Markdown. Put SQL in fenced blocks. Always include a `Credentials &
Access` note (how secrets are sourced) and a `Reproducibility` note (snapshot id,
query, params). When the data is time-series, include a `Point-in-Time` note.

## Spec-Driven Role

Ingestion requirements belong in the spec: encode "point-in-time correct",
"read-only", and "snapshot captured" as `AC-*`/`NFR-*`, and record credential
handling so the constitution P9 check is explicit. Emit
`templates/data/data_contract.md` for downstream stages. Backed by the
shared `instructions/data_ingestion.md` standard.
