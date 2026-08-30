# Knowledge Ingestion Instructions

## Operating Rules

- Capture provenance for every item: source, author, created/modified date, version.
- Preserve each item's access level from the source; never widen it on ingestion.
- Detect and flag PII, secrets, and MNPI/restricted content before indexing.
- Chunk to keep semantic context intact; avoid splitting mid-idea.
- Normalize formats without losing structure (headings, tables, code).
- Make sync incremental and idempotent; de-duplicate re-ingested content.
- Record a content hash and ingestion time so the index is reproducible.
- Do not ingest a source you are not authorized to read.
- Honor the source manifest (`knowledge_sources.yml`): use each source's declared
  domains (subfolders), access level, and include/exclude scope.

## Checks

- Does every item carry source, author, date, version, and access level?
- Is restricted/MNPI content tagged and access-preserved, not flattened?
- Were PII and secrets detected and handled at ingestion?
- Do chunks preserve enough context to be useful in retrieval?
- Is the sync incremental and idempotent (no duplicates on re-run)?
- Is ingestion reproducible (hashes, timestamps recorded)?

## Output Contract

Use clear Markdown. Include a `Provenance & Access` section and a `Sensitive
Content` section (PII/secrets/MNPI handling). When designing a sync, include an
`Incremental Sync` section.

## Spec-Driven Role

Ingestion guarantees are spec criteria: "provenance captured", "access level
preserved", and "PII/secret/MNPI flagged" become `AC-*`/`NFR-*`. Confidentiality
handling defers to `agents/secrets_management/` and constitution P9. Emit the
knowledge base's schema (fields, access model, provenance) as a data-contract-style
artifact so curation and retrieval can rely on it. See
`instructions/knowledge_base.md` for the shared standard. This group also serves the persistent workflow memory store (`memory/`); see `instructions/workflow_memory.md`. The write-path runtime is `workflow_memory.py` (spec `0049`, extended from `0048`): use `propose_records()` to draft candidates and `stage_candidates()` to write them to a local-only `memory/inbox/` staging area for human review before promotion.
