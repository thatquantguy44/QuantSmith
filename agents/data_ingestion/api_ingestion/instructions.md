# API Ingestion Instructions

## Operating Rules

- Check `sources/<source-id>.yml` first for the registered endpoint, quality
  notes, and `credential_ref` before wiring a new pull.
- Source tokens/keys from environment or a secrets manager; never commit or log them.
- Paginate to completion; detect and fail on truncated or missing pages.
- Respect rate limits; back off and retry only transient (5xx / 429) failures.
- Make pulls idempotent; re-running must not duplicate or corrupt data.
- Record an as-of timestamp and archive raw payloads for reproducibility.
- Validate the response schema before mapping it into typed data.
- Design incremental loads with a durable cursor; document full-refresh behavior.
- Handle timezones and vendor revision semantics point-in-time correctly.

## Checks

- Are credentials outside the repo and outside logs?
- Is pagination complete, with truncation detected?
- Are rate limits respected and only transient failures retried?
- Is the pull idempotent and safe to re-run?
- Is it reproducible: as-of timestamp recorded, raw payloads archived?
- Is the response schema validated before use?

## Output Contract

Use clear Markdown. Put client code in fenced blocks. Always include a `Auth &
Secrets` note and a `Reproducibility` note (as-of timestamp, archived payloads).
When loading incrementally, include a `Cursor & Idempotency` note.

## Spec-Driven Role

Encode ingestion guarantees as spec criteria: "complete pagination", "idempotent
re-run", and "as-of captured" become `AC-*`/`NFR-*`, and raw-payload archival
plus secret handling make the P4 and P9 checks explicit. Emit
`templates/data/data_contract.md` for downstream stages. Backed by the shared
`instructions/data_ingestion.md` standard.
