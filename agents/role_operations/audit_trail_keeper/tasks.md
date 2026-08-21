# Audit Trail Keeper Tasks

## Log A Decision

Input: a decision, its rationale, alternatives considered, and its
consequences.

Output: a new, append-only `templates/docs/decision_log.md` entry.

## Log A Superseding Decision

Input: a decision that revisits or reverses an earlier logged decision.

Output: a new entry marked "supersedes" the earlier entry's ID; the
earlier entry is left unedited.

## Summarize The Trail

Input: the log's accumulated entries.

Output: a summary of every decision recorded, noting which are current and
which have been superseded and by what.
