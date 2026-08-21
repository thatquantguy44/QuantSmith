# File Ingestion Instructions

## Operating Rules

- Check `sources/<source-id>.yml` first if the file originates from a
  registered source (a vendor export or file feed), for its quality notes
  and access level.
- Declare an explicit schema and dtypes; do not rely on silent inference.
- Set encoding, delimiter, quoting, and header handling explicitly per format.
- Parse dates with an explicit format and timezone; never guess ambiguous dates.
- Define missing-value sentinels; do not let empty strings become silent NaN/0.
- Validate on load (types, keys, ranges) and fail loudly on violations.
- Capture the source file's checksum and record the loader parameters.
- Chunk or stream files too large to hold in memory.
- Reconcile schemas explicitly when combining multiple files/partitions.

## Checks

- Is the schema explicit, with types that match the data?
- Are encoding, delimiter, and header handled correctly for this format?
- Are dates and timezones parsed unambiguously?
- Are missing values defined and handled, not silently coerced?
- Does the loader validate and reject bad data instead of absorbing it?
- Is the load reproducible (checksum captured, parameters recorded)?
- Are large files chunked/streamed?

## Output Contract

Use clear Markdown. Put loader code in fenced blocks. Always include a `Schema &
Types` section and a `Validation` section. When files are large, include a
`Memory & Chunking` note.

## Spec-Driven Role

The file's expected schema and quality thresholds are acceptance criteria: encode
them as `AC-*` and emit `templates/data/data_contract.md` so the
`data-contract-check` hook and the testing stage can enforce them. Backed by
the shared `instructions/data_ingestion.md` standard.
