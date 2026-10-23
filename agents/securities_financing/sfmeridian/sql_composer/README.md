# SQL Composer Agent

## Purpose

The SQL Composer handles only questions already recorded as outside the
governed `0080` vocabulary. It retrieves reviewed evidence, composes by
`reuse` → `adapt` → `generate`, and returns a cited composition only after
`sql.verify` issues an exact-context token.

## Use When

- `ask` has produced the typed route `no_governed_match`.
- A reviewed query may answer a lookup or aggregate question.
- A catalog-constrained adaptation or generation needs independent verification.

## Inputs

- Question, ISO as-of, database profile, exact parameters, and PIT columns.
- The recorded route `no_governed_match`.

## Outputs

- Retrieval observations and source citations.
- Composition path, catalog objects, limitations, and content hash.
- A verification record and short-lived token; never query results.

## Runtime

Tested loop agent (`0116`): `sfmeridian.composer_agent.run_composer`. Manifest:
`plugins/sfmeridian/src/sfmeridian/data/agents/sql_composer.json`.
