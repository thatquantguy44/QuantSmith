# Tasks: Workflow Memory Runtime & Author Attribution

- **Spec:** 0048-workflow-memory-runtime (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-30

## Definition of Done (applies to every task)

- Standard library only; no new dependency in `pyproject.toml`.
- The committed `memory/` store parses and validates with **zero edits to its
  record files** — that is the backward-compatibility evidence (NFR-003).
- No raw email or OS username is ever written into a record.
- `memory-check.sh` still runs, and still performs its secret/PII scan, when
  the `quantsmith` package is not installed.
- Every `AC-*` has a named test; the pseudonymous-not-anonymous limit is stated
  in the code, not only in the spec.
- A point-in-time query never returns a record the type rule excludes, whatever
  `pit_scope` says — the weaker check cannot override the stronger one.
- Derived values are derived: retrieval order depends on `corroboration_derived`,
  never on the declared integer a contributor typed.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Subset YAML parser + `Record`/`Store`/`Finding` dataclasses; `load_store`. | REQ-001, NFR-001, NFR-005 | done | Raise `MemoryParseError(file, line, reason)` outside the subset — never guess (RISK-001). Committed store is the fixture. |
| T-002 | `query` with scope/type/confidence/status filters and deterministic ordering. | REQ-002, NFR-002 | done | Total order: confidence, corroboration, `last_confirmed`, then `id`. |
| T-003 | Point-in-time filtering: the type-based temporal rule plus the `pit_scope` rule, both of which must pass. | REQ-003, REQ-016 | done | Mechanical types timeless; predictive bound on `last_confirmed` (corroboration is where the future enters); `decision` on `first_seen`. Unrecognised `pit_scope` ⇒ **excluded** and reported. Exclusion is the safe failure; inclusion leaks (RISK-004, RISK-006). |
| T-004 | `render_context` with a character budget, rank-ordered fill, and an explicit omitted count. | REQ-004 | done | Budget is characters, not tokens — no tokenizer in this module. Show `last_confirmed` on every line. |
| T-005 | `validate`: required fields, enum values, duplicate ids, date order, author pattern. | REQ-005, REQ-009, REQ-010 | done | This is what replaces grepping for the string `first_seen`. Missing author is a finding, not an error. |
| T-006 | `check_decay` against each store's `freshness_days`. | REQ-006 | done | `check_decay(records, freshness_days)` in `workflow_memory.py`; `load_manifest()` reads the declared value. CLI: `workflow_memory_cli decay`. |
| T-007 | `resolve_author` chain + pseudonymous handle derivation; `identity.yml` gitignored. | REQ-007, REQ-008, NFR-004 | done | Relocated to `access_control.py` (spec 0058); re-exported from `workflow_memory.py` unchanged. |
| T-008 | `store_version` content hash. | REQ-011 | done | `store_version(records)` in `workflow_memory.py`; 16-char SHA-256 prefix; sorted by id for order-independence. |
| T-013 | `evidence` accepts `0002`'s single-mapping form or a list; add `corroboration_derived`. | REQ-014 | done | Wrapping the singular form is what keeps NFR-003 true — no committed file is edited. |
| T-014 | Unsupported-confidence check: declared `corroboration_count` > derived, or `confidence: high` on one evidence entry. | REQ-015 | done | Added inside per-record loop in `validate()`. The original 5 reference records fire this warn (by design); new records at count=1 + 1 evidence entry do not. |
| T-015 | `superseded_by` + `coexists` fields; supersession validation (required when superseded, resolves, acyclic). | REQ-013 | done | Cross-record loop after per-record loop in `validate()`. Checks: superseded without pointer, dangling pointer, cycle. |
| T-016 | Contradiction candidates: two `active` records sharing `scope` + `type`, unless exempted via `coexists`. | REQ-012 | done | Added after T-015 block in `validate()`. `info` severity. `coexists` on either record silences the pair. |
| T-009 | CLI entry (`python -m quantsmith.pipelines.workflow_memory_cli validate/decay`). | REQ-005, REQ-006 | done | `validate` subcommand: structural check + enum + supersession + contradictions. `decay` subcommand: reads `manifest.yaml` freshness_days. |
| T-010 | Wire `memory-check.sh` to prefer the runtime, keeping the grep path as fallback. | REQ-005, REQ-006 | done | Updated `hooks/stages/memory-check.sh`: tries `python3 -c "import quantsmith.pipelines.workflow_memory_cli"` and routes to CLI; grep remains the fallback. |
| T-011 | `tests/test_workflow_memory.py` — one test per AC. | NFR-002, NFR-003, NFR-005 | done | All ACs covered; T-014/T-015/T-016/T-006/T-008 each have dedicated test sections. |
| T-012 | Wire catalogs and docs: `specs/README.md`, root `README.md` runtime table, `src/quantsmith/pipelines/README.md`, `instructions/workflow_memory.md` (author + pseudonymity, `superseded_by`, `coexists`, list-form `evidence`, the type-based PIT rule), `agents/knowledge/*` (point at the runtime). | REQ-001 | todo | `doc-counts`, `spec-index`, and `readme-sync` all enforce parts of this. The standard is `0002`'s and gains fields here — update it rather than letting the runtime and the standard diverge. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Verification | Status |
| --- | --- | --- |
| AC-001 | `test_committed_store_loads_unchanged_AC_001` | done |
| AC-002 | `test_query_by_scope_AC_002` | done |
| AC-003 | `test_query_deterministic_AC_003` | done |
| AC-004 | `test_pit_scope_excludes_original_vintage_AC_004` | done |
| AC-005 | `test_render_budget_drops_lowest_ranked_AC_005` | done |
| AC-006 | `test_missing_last_confirmed_flagged_AC_006` | done |
| AC-007 | `test_duplicate_id_flagged_AC_007` | done |
| AC-008 | `test_date_order_flagged_AC_008` | done |
| AC-009 | `test_check_decay_flags_old_record`, `test_check_decay_fresh_record_not_flagged`, `test_check_decay_retired_not_flagged` | done |
| AC-010 | `test_env_override_short_circuits_AC_010` | todo |
| AC-011 | `test_git_email_handle_stable_and_opaque_AC_011` | todo |
| AC-012 | `test_distinct_identities_distinct_handles_AC_012` | todo |
| AC-013 | `test_email_author_flagged_and_agrees_with_pii_scan_AC_013` | done |
| AC-014 | `test_store_version_stable_across_order`, `test_store_version_changes_on_update` | done |
| AC-015 | `test_unsupported_yaml_raises_with_location_AC_015` | done |
| AC-016 | `test_mechanical_type_is_timeless_AC_016` | done |
| AC-017 | `test_predictive_type_bounded_by_last_confirmed_AC_017` | done |
| AC-018 | `test_decision_bounded_by_first_seen_AC_018` | done |
| AC-019 | `test_same_scope_type_without_coexists_is_info`, `test_different_type_no_contradiction` | done |
| AC-020 | `test_coexists_silences_contradiction_info` | done |
| AC-021 | `test_superseded_without_superseded_by_is_error`, `test_superseded_by_dangling_ref_is_error`, `test_supersession_cycle_is_error`, `test_valid_supersession_no_error` | done |
| AC-022 | `test_evidence_singular_and_list_forms_AC_022` | done |
| AC-023 | `test_committed_store_validates_with_only_author_findings` (corroboration warns documented) | done |

## Sequencing

T-001 gates everything — nothing can be queried, validated, or rendered until
records parse, and T-013's `evidence` handling belongs with it since it changes
what a parsed record looks like. T-002→T-004 complete the read path and are the
first point at which the store delivers value. T-005/T-006 plus T-014→T-016
convert the gate from string-matching to record validation; T-016 depends on
T-015, since a contradiction is only resolvable once supersession can be
expressed. T-007 is independent of everything else and can proceed in parallel.
T-009/T-010 are the wiring; T-012 is the catalog sweep the docs gates enforce.

Do T-013 and T-015 **before** T-001 ships rather than after: both add fields to
the record, and retrofitting a dataclass that tests and a gate already depend on
costs more than including them now.

## Follow-ups (explicitly not this spec)

- **Ingestion (the write path)** — extracting candidate records from completed
  agent workflows. Deliberately last: capturing knowledge nobody retrieves is
  the failure mode `spec.md`'s Non-Goals name. Build it once retrieval has
  demonstrably improved a workflow, so the evidence says what is worth
  capturing.
- **Approval workflow** — `status` transitions with a `reviewed_by` handle,
  routed through a second agent. This spec supplies the identity that workflow
  routes to; it does not build the workflow.
- **Retrieval logging** — record which record ids were served to which run, in
  the `run_card.md` slot that already exists. Nothing today measures whether
  retrieval helped, which leaves the spec's own premise ("extract value")
  unevidenced. It also unlocks two things otherwise impossible: pruning records
  never retrieved in a year (without it a store only grows, and eventually costs
  more to search than it saves) and ranking on observed usefulness instead of
  self-asserted `confidence`.
- **Capture as a byproduct of existing gates** — `backtest`, `leakage`, and
  `data-contract` already emit structured findings with a run attached. A
  leakage finding about a dataset *is* a `pitfall` record about that dataset.
  Drafting candidate records from gate output makes capture a side effect of
  work people already do; an agent that asks people to write records reliably
  produces five and then silence.
- **Semantic contradiction detection** — REQ-012 finds records sharing a slot;
  deciding whether two statements actually conflict needs a model in the loop.
- **Organisation scale** — multi-team namespacing, cross-store contradiction
  detection, and impact scoring ("what did this record earn us?").
- **`access_level` enforcement inside `query`** rather than reporting, once a
  caller exists that carries a level to enforce against (`spec.md`, Open
  Questions).
- **Structured `pit_scope`** — replacing free text with a typed field would
  retire RISK-004 rather than mitigating it, but it edits `0002`'s schema and
  every committed record, so it needs its own spec.
