# Workflow Memory Instructions

## Purpose

Use this instruction set when a workflow reads from or writes to persistent memory —
the durable store where a workflow accumulates what it learns about databases,
datasets, schemas, fields, and their quirks over time. It is the standard behind the
`memory/` store and is served by the `knowledge/` agents. The goal is a memory that
lets a workflow arrive already knowing the kinks of a dataset, without being misled
by stale or leaked knowledge.

## Layout (two-axis)

```
memory/
  manifest.yaml                    # where memory lives, access levels, committed/external
  _shared/datasets/<ds>/           # facts about a source, reused by any workflow
    schema.md quirks.md pitfalls.md provenance.yaml
  <workflow>/                      # one per workflow in docs/workflows.md
    index.yaml lessons.md
    datasets/<ds>/ patterns.md decisions.md
```

`_shared/` holds what is true about a source; `<workflow>/` holds how a workflow uses
it. This prevents every workflow re-learning the same database.

## Record Schema

Every learning is a record with: `id`; `scope` (dataset/table/field); `type`
(schema | quirk | pattern | pitfall | decision | metric | performance); `statement`;
`evidence` — a single mapping or a list of mappings, each citing a source run with an
optional sample query but never raw data; `confidence` and `corroboration_count`
(derived from the evidence list length — the committed value is advisory and validated
against the derived count); `first_seen`, `last_confirmed`; `status`
(active | stale | superseded | retired); `access_level`; `pit_scope` (the data window
the learning came from); `author` (a pseudonymous `u-<24 hex>` handle produced by
`derive_handle()` — the raw email or OS username is never written); and, when
applicable, `superseded_by` (the id of the record that replaces this one) and
`coexists` (marks a pair of same-scope/same-type records as intentionally
non-contradictory — no `coexists` means the pair is flagged as a candidate
contradiction).

## Lifecycle

- **Prime (read):** load relevant records before a run so the workflow already knows
  the dataset. Use `knowledge/knowledge_retrieval`.
- **Learn (write):** after a run, append new observations as candidate records with
  provenance and low confidence. Use `knowledge/knowledge_ingestion`.
- **Confirm:** repeated corroboration raises confidence; a contradiction flags it.
- **Curate:** consolidate, dedupe, resolve conflicts, flag stale/superseded. Use
  `knowledge/knowledge_curation`.
- **Persist decisions:** durable decisions via `knowledge/institutional_memory`.

## Standards (guardrails)

- **Provenance always.** Every record cites its source run and carries `first_seen`,
  `last_confirmed`, `confidence`, and `access_level`. No provenance, no record.
- **Point-in-time firewall.** Two independent rules, both must pass. (1) Type-based:
  mechanical facts (`schema`/`quirk`/`pitfall`) are timeless and always eligible;
  performance claims (`pattern`/`metric`/`performance`) are bounded by `last_confirmed`
  because corroboration is where the future enters a record; a `decision` is bounded by
  `first_seen`. An unknown type is excluded. (2) Scope-based: the record's `pit_scope`
  must be on or before the decision date. Exclusion is the safe failure — inclusion
  leaks future knowledge. See `instructions/point_in_time.md` (constitution P4).
- **Metadata only.** Never store credentials, connection strings, raw data rows, or
  PII in memory. See `agents/secrets_management/` (P9).
- **Freshness.** Treat old records as hypotheses; re-validate schema memory before
  trusting it, and mark drift-invalidated records `stale`.
- **Access inheritance.** Memory about a restricted dataset inherits its access level;
  retrieval enforces it (information barriers).
- **Honest confidence.** State confidence; low-confidence memory is not fact.
- **Reproducible.** Version memory; record the memory version a run used in its run card.
- **No silent overwrite.** Contradictions are resolved to `superseded`, not deleted.

## Checks

- Does every record carry provenance and an access level?
- Are research/backtest runs bounded to `pit_scope` ≤ decision date?
- Is the store free of secrets, connection strings, and PII?
- Are stale/superseded records flagged rather than served as current?
- Is the memory version recorded in the run card?

## Common Failure Modes

- Serving stale schema memory after the schema changed.
- Using a learning derived from future data in a backtest (leakage).
- Storing a connection string, credential, or PII "for convenience".
- Silently overwriting a record instead of superseding it.
- Treating a low-confidence, single-observation record as established fact.

## Author Attribution

Every record carries an `author` field whose value is a pseudonymous handle produced
by `derive_handle(identity)` in `access_control.py`. The handle is `u-<24 hex chars>`
— 26 characters, stable across calls, case-insensitive with respect to the raw input,
and structurally incapable of containing an email address or a recognisable username.
The resolution chain for the identity to hash is: explicit override argument →
`QF_MEMORY_AUTHOR` environment variable → `identity.yml` (local-only, gitignored) →
git author email for the working tree → OS username → None. Override and env values
are returned as-is; everything else goes through `derive_handle()`. Pseudonymous is
not anonymous: the same identity always produces the same handle, so records from one
person can be attributed, but the handle cannot be reversed to the raw identity without
the SHA-256 pre-image.

## Supersession and Coexistence

When a record is replaced: mark the old record `status: superseded` and add a
`superseded_by: <new-id>` field pointing to the replacement. A superseded record is
excluded from active retrieval but preserved in the store — no silent overwrite.

When two records share the same `scope` and `type` but are intentionally not
contradictory (e.g., two patterns that both hold under different conditions), add
`coexists: true` on at least one of the pair. Without `coexists`, the `validate`
command flags the pair as an info-level contradiction candidate.

## Spec-Driven Alignment

The record standard is `specs/0002-workflow-memory/`. The machine-readable runtime is
`src/quantsmith/pipelines/workflow_memory.py` (spec `0048`): use `load_store()` to
parse the committed `memory/` store into typed `Record` objects, `query()` /
`render_context()` to retrieve records at run time, and `validate()` to replace the
`memory-check` gate's grep-based checks. The `memory-check` gate (`hooks/stages/
memory-check.sh`) routes to the runtime when the package is installed and falls back
to grep when it is not. Guarantees become testable: "provenance present",
"no secrets/PII", and "pit_scope-bounded" are `AC-*`; staleness, leakage, secrets,
and irreproducibility are the spec's `RISK-*`.
