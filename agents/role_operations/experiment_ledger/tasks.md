# Experiment Ledger Tasks

## Log a Variant

Input: a variant's configuration and result as it happens.

Output: an append-only ledger entry with configuration, result, and status
(rejected — reason, superseded, or current best).

## Record a Rejection

Input: a variant that was tried and ruled out.

Output: the rejection reason stated plainly in the ledger entry.

## Summarize the Search

Input: the ledger's accumulated entries.

Output: a summary grouped by status — what's ruled out and why, what's
currently leading.
