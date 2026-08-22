# Tasks: Viewer Access Control

- **Spec:** 0058-viewer-access-control (`spec.md`, `plan.md`)
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
| T-001 | Create `access_control.py`; relocate `derive_handle`/`resolve_author`/`AUTHOR_HANDLE_RE` from `workflow_memory.py` (re-exported there unchanged); add `ACCESS_LEVELS`, `access_level_allows()`. | REQ-001, REQ-002, REQ-006 | done | |
| T-002 | `RosterEntry`/`Roster` dataclasses, dedicated roster parser, `load_roster()` with opt-in/empty-means-inactive semantics. | REQ-003, REQ-004, REQ-005 | done | |
| T-003 | `resolve_viewer_clearance()`, `validate_roster()`. | REQ-007, REQ-008, REQ-009 | done | |
| T-004 | `workflow_memory.query(..., viewer_clearance=None)`. | REQ-010 | done | |
| T-005 | `build_model`/`build_model_from_root` and `build_research_model`/`build_research_model_from_root` gain `viewer_clearance`/`viewer_override`. | REQ-011, REQ-012 | done | |
| T-006 | CLI: `whoami` on `workflow_memory_cli.py`; `--viewer-override` on `quantsmith.knowledge_console` `print`/`research`/`query`. | REQ-013, REQ-014 | done | |
| T-007 | `hooks/stages/access-check.sh`; wire into `run-stage.sh`, `hooks/README.md`, `ci.yml`. | REQ-015 | done | |
| T-008 | `tests/test_access_control.py` + targeted additions to existing test files; full pre-existing suite re-run unmodified as regression gate. | all AC, NFR-004 | done | |
| T-009 | `access/roster.yml` (zero entries, documented template) + `access/README.md`. | REQ-003 | done | |
| T-010 | Wire catalogs/docs: `specs/README.md`, root `README.md`, `docs/handoff.md`, `PERSISTENT_KNOWLEDGE.md`; run gates + full pytest green. | REQ-015, NFR-004 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_clearance_ordering_AC_001` | done |
| AC-002 | `test_no_roster_is_unfiltered_AC_002` | done |
| AC-003 | `test_empty_roster_is_unfiltered_AC_003` | done |
| AC-004 | `test_one_entry_activates_enforcement_for_everyone_AC_004` | done |
| AC-005 | `test_env_override_resolves_roster_clearance_AC_005` | done |
| AC-006 | `test_unlisted_handle_gets_default_clearance_AC_006` | done |
| AC-007 | `test_unresolvable_identity_gets_default_clearance_AC_007` | done |
| AC-008 | `test_email_shaped_handle_is_rejected_AC_008` | done |
| AC-009 | `test_duplicate_handle_and_bad_clearance_rejected_AC_009` | done |
| AC-010 | `test_query_filters_by_viewer_clearance_AC_010` | done |
| AC-011 | `test_view_model_builders_exclude_restricted_content_AC_011` | done |
| AC-012 | `test_snapshot_build_excludes_restricted_content_AC_012` | done |
| AC-013 | `test_visible_item_still_shows_its_access_level_AC_013` | done |
| AC-014 | `test_whoami_matches_resolve_author_AC_014` | done |
| AC-015 | `test_preview_reports_effective_visibility_AC_015` | done |
| AC-016 | `test_gate_reports_roster_validation_findings_AC_016` | done |
| AC-017 | `test_gate_flags_embedded_email_in_roster_file_AC_017` | done |

## Follow-ups

Tracked work intentionally deferred (no silent "temporary" shortcuts — P8).

- Real authentication for a shared/multi-tenant deployment — explicit
  Non-Goal; only needed if the deployment model stops being local-per-person.
- Composing `0056`'s `entitlement_class` with clearance — separate concept,
  deferred per spec Assumptions.
- Multiple handles per person; time-boxed/expiring roster entries — deferred
  per spec Open Questions, roster-editing-frequency problems, not mechanism
  gaps.
- Write-side authorization (who may `promote`/`discard`) reusing this
  roster — spec is read-side only by design.
