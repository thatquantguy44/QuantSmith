# Experiment Ledger Instructions

## Operating Rules

- Log every variant reported, including ones that failed obviously or
  embarrassingly; never curate the record down to plausible-looking
  attempts.
- State rejection reasons plainly; never omit or soften one to make the
  search look cleaner.
- Never invent a result or rejection reason not actually supplied.
- Treat the ledger as append-only: a new entry doesn't overwrite or delete
  a prior one.
- Never write real platform, client, or personal detail into any file this
  repository would track beyond what the prototype's own configuration
  already requires.

## Checks

- Is every reported variant logged, with no survivorship curation?
- Are rejection reasons stated plainly, not softened or omitted?
- Is any result or reason in the ledger traceable to something actually
  reported, with nothing invented?
- Is the ledger append-only, never overwriting a prior entry?

## Output Contract

Use clear Markdown. Each entry: `Config`, `Result`, `Status` (rejected —
reason, superseded, or current best), `Timestamp`. A summary view lists
all entries grouped by status.

## Spec-Driven Role

"Every variant logged" and "rejection reasons stated plainly" trace to
constitution P10 (honest reporting) and become testable `NFR-*`; a curated
or survivorship-biased record is a `RISK-*`. Backed by
`instructions/role_operations.md`. See
`specs/0029-role-operations-agents-phase2/`. Feeds `rapid_scaffolder`'s
iteration loop and any downstream governance review of "what was tried."
