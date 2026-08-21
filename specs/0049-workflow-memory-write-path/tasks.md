# Tasks: Workflow Memory Write Path

- **Spec:** 0049-workflow-memory-write-path (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-21

> Ordered, testable units of work. Every task cites the requirement(s) it advances
> and carries a Definition of Done. No task without a requirement.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests exist and pass deterministically.
- Reproducibility preserved (pinned inputs, seeded randomness, no hidden state).
- No secrets, credentials, or private data introduced.
- Docs/configs updated alongside the change.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | `resolve_author()` + `derive_handle()` in `workflow_memory.py`: env → `identity.yml` → git → OS user chain; stable salted-hash handle reusing `_AUTHOR_RE`. | REQ-001, REQ-002 | done | |
| T-002 | `CandidateSpec`/`Candidate` dataclasses + `propose_records()`: pure construction, no I/O. | REQ-003, REQ-004 | done | |
| T-003 | `stage_candidates()` deterministic inbox writer + `load_inbox()` reader, reusing `parse_memory_file`. | REQ-005, REQ-006 | done | |
| T-004 | `promote()`: validate-before-write, id assignment, author/date stamping, catalog append preserving sibling records, contradiction warning, inbox-file removal; `MemoryWriteError`. | REQ-007, REQ-008, REQ-009, REQ-010 | done | |
| T-005 | `discard()`: inbox-file removal without promotion. | REQ-011 | done | |
| T-006 | `ingestion_data_contract.candidates_from_validation()`: worked producer integration. | REQ-012 | done | |
| T-007 | `workflow_memory_cli.py`: propose+stage, list-inbox, promote, discard subcommands; `pyproject.toml` entry point. | REQ-013 | done | |
| T-008 | `templates/docs/run_card.md`: add "Memory proposed" line to the existing Workflow Memory section. | REQ-014 | done | |
| T-009 | `hooks/stages/memory-check.sh`: validate staged inbox candidates (parse + required fields), same finding style as live records. | REQ-015 | done | |
| T-010 | `tests/test_workflow_memory_write_path.py`: one test per AC. | REQ-001, REQ-004, REQ-007, REQ-009, REQ-012, REQ-013, NFR-003, NFR-006 | done | |
| T-011 | Wire catalogs/docs: `specs/README.md`, root `README.md` runtime table, `docs/handoff.md`; run gates + full pytest green. | REQ-014, REQ-015 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_env_override_short_circuits_resolution_AC_001` | done |
| AC-002 | `test_git_derived_handle_matches_pattern_and_is_stable_AC_002` | done |
| AC-003 | `test_different_identities_derive_different_handles_AC_003` | done |
| AC-004 | `test_no_identity_resolves_to_none_without_raising_AC_004` | done |
| AC-005 | `test_propose_records_writes_nothing_to_disk_AC_005` | done |
| AC-006 | `test_staged_inbox_file_parses_with_0048_parser_AC_006` | done |
| AC-007 | `test_restaging_identical_batch_is_byte_identical_AC_007` | done |
| AC-008 | `test_inbox_never_leaks_into_live_query_or_pit_filter_AC_008` | done |
| AC-009 | `test_promote_stamps_id_author_dates_preserves_siblings_AC_009` | done |
| AC-010 | `test_promote_removes_only_the_promoted_candidate_AC_010` | done |
| AC-011 | `test_promote_refuses_missing_required_field_AC_011` | done |
| AC-012 | `test_promote_refuses_id_collision_AC_012` | done |
| AC-013 | `test_promote_warns_on_contradiction_but_still_promotes_AC_013` | done |
| AC-014 | `test_discard_removes_one_leaves_rest_AC_014` | done |
| AC-015 | `test_candidates_from_real_validation_result_AC_015` | done |
| AC-016 | `test_cli_propose_list_promote_discard_AC_016` | done |
| AC-017 | `test_run_card_template_has_memory_proposed_field_AC_017` | done |
| AC-018 | `test_gate_reports_malformed_inbox_candidate_AC_018` | done |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- Producer integrations for `0046` (walk-forward performance), `0045` (FRED
  vintage quirks), `0038` (factor risk metrics) — `0039` is this spec's one
  worked example; the others are per-producer follow-ups against the same
  generic `CandidateSpec` contract.
- Batch promotion (one call, many candidates) — deferred per spec's Open
  Questions.
- CLI `--force` past a contradiction warning — deferred per spec's Open
  Questions.
- A reviewer/approver identity model beyond "can merge to `main` / can run
  `promote` locally" — explicit Non-Goal; revisit if adoption shows the gap.
- Wiring the inbox into `0057`'s console as a read-only "pending proposals"
  view — the console stays read-only per its own NFR-003; this would be an
  additive, separate change there, not part of this spec.
