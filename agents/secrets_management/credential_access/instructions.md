# Credential Access Instructions

## Operating Rules

- Read secrets from the environment or the secret store; never hard-code them.
- Never read secrets from tracked files; `.env` is for local dev only and gitignored.
- Use the narrowest identity/role that the task requires.
- Never log, print, echo, or include a secret in an exception or error message.
- Do not serialize secrets into objects, caches on disk, or debug dumps.
- Cache in memory only, with a TTL; refetch rather than persist.
- Fail closed: if a secret is missing, stop with a clear (secret-free) error.
- Keep the retrieval pattern consistent across dev, staging, and prod.

## Checks

- Is every secret read from env/store, with none hard-coded or in tracked files?
- Is the consumer's identity least privilege?
- Could a secret reach a log, exception, trace, or serialized output?
- Is caching in-memory only, with a TTL and nothing on disk?
- Does a missing secret fail closed with a secret-free message?
- Is the pattern the same across environments?

## Output Contract

Use clear Markdown. Put code in fenced blocks with placeholder secret names only.
Include an `Access Path` section and a `Leak Guards` section (how logging and
serialization are prevented). Never include real secret values.

## Spec-Driven Role

"No secret in logs", "least-privilege identity", and "read from store, not repo"
are testable `AC-*`. The `secret_scanning` agent and the implementation-stage
secret check verify them; encode them in the spec so they are enforced.
When resolving a registered data source's connection, the store/env key to
read is named by that source's `connection.credential_ref` in `sources/*.yml`
(see `instructions/data_source_catalog.md`) — this agent's job is retrieving
what that pointer names, never storing the value back into the catalog.
