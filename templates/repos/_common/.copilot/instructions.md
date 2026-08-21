# Repository conventions

## Non-negotiable

- Never invent data. If a value is unknown, say so or fail loudly.
- Never write a credential, token, connection string, or real customer
  identifier into a file. Secrets come from the environment or a secret store.
- Point-in-time correctness: a value dated D must not have been knowable after
  D. No `.shift(-n)`, no backfill across a split, no future-leaking joins.

## Style

- Match the surrounding file. Comment density, naming, and idiom included.
- Conventional Commits: `type(scope): description`.
- Prefer the smallest change that fully solves the problem.

## Before proposing a change

- If it is non-trivial, it needs a spec under `specs/NNNN-slug/`.
- Every task cites a requirement; every acceptance criterion names a test.
- Update catalogs and docs in the SAME change, not a follow-up.
