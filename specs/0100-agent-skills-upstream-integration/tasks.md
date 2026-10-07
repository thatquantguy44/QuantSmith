# Tasks: agent-skills as a Pinned, Offline Upstream for Coding Tasks

- **Spec:** 0100-agent-skills-upstream-integration (`spec.md`, `plan.md`)
- **Last updated:** 2026-10-07

> Every task cites a requirement and carries a Definition of Done.

## Definition of Done (applies to every task)

- Code matches the plan; deviations noted in `plan.md`.
- Tests exist, name the `AC-*` they prove, and pass deterministically with networking disabled.
- No vendored file is edited by hand; no URL source anywhere in the integration.
- Standard library and POSIX `sh` only; no new dependency.
- Gates pass (`QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh`) and no existing test regresses.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Spike: confirm Claude Code project-local directory marketplace + `enabledPlugins` keys against current docs, offline; choose plugin route or `.claude/skills` fallback and record it in `plan.md` | REQ-005 | done | Confirmed on Claude Code 2.1.292, offline; design adjusted (per-machine opt-in, no committed marketplace path, no `agents` key, version stamp). Evidence: `validation.md` |
| T-002 | `config/agent_skills.json`: groups, defaults (incl. all three personas), exclusions with reasons, size cap | REQ-007, REQ-011, REQ-013 | done | |
| T-003 | `src/quantsmith/agent_skills/` `sync` + `lock`: read local dir / clone ref (`git archive`) / tarball, copy allowlist, deterministic lock, stamp overlay `plugin.json` version `<upstream>+<sha7>.<tree-hash8>`; console script | REQ-001, REQ-002, REQ-003, NFR-002, NFR-004 | done | |
| T-004 | Sync safety and reporting: reject URL sources, symlinks, executables, oversize, out-of-allowlist; change summary; `diff` and `--dry-run` | REQ-003, REQ-011, NFR-001, NFR-003 | done | |
| T-005 | `status` and `install --scope user|project`; `QS_AGENT_SKILLS_PATH` via `--plugin-dir`; detect duplicate user-level installs | REQ-006 | done | RISK-008. Project opt-in = `marketplace add --scope local`, never `plugin install` (plan: Settings) |
| T-006 | First sync at fork `f63ec56` (v0.6.7); QuantSmith-owned `README.md` (provenance, credit) and overlay `plugin.json`; verbatim `LICENSE` | REQ-001, NFR-007 | done | Synced 2026-10-07: 35 files, `0.6.7+f63ec56.53469383`; content reviewed (`validation.md`) |
| T-007 | `hooks/stages/agent-skills-check.sh`: hashes vs lock, frontmatter, allowlist/exclusions, URL sources, agent citations, registry name collisions, size; wire into `run-stage.sh` and CI | REQ-004, REQ-007, NFR-004, NFR-005 | done | |
| T-008 | Root `.claude-plugin/marketplace.json`; `enabledPlugins` only in `.claude/settings.json` (keep existing SessionStart hook); add `.claude/settings.local.json` to `.gitignore` | REQ-005, NFR-006 | done | Shape fixed by T-001 |
| T-009 | `instructions/agent_skills.md`: precedence, stage map (incl. persona routing), exclusions, overrides, refresh runbook, kill switch and removal | REQ-008, REQ-013, NFR-006 | done | |
| T-010 | Cite skills in `implementation`, `testing_validation`, `git_release`, `test_engineering/*`, `quality-guard-agent` instructions; note in `agents/README.md`; regenerate registry | REQ-009 | done | |
| T-011 | `docs/adoption_guide.md` section; `vendor/agent-skills` as a `QF_UPSTREAM_SURFACES` example; `docs/handoff.md` pin line | REQ-010 | done | |
| T-012 | Tests (`tests/test_agent_skills.py`, gate fixtures) incl. network-off proof; manual Claude Code check for AC-001/AC-011 into `validation.md` | NFR-001, NFR-002, REQ-004 | done | Interactive (TTY) session, macOS and Windows remain manual checks (AC-001) |
| T-013 | Indexes and changelog: `specs/README.md`, `CHANGELOG.md`, `README.md` spec count, `CLAUDE.md` pointer | REQ-008 | done | |
| T-014 | Bundle the vendored tree and lock into the wheel via `setup.py` (`quantsmith/_bundled/agent_skills/`); build fails on lock mismatch; `install --scope user` falls back to it | REQ-012 | done | Same mechanism as analytics packs |
| T-015 | Quarterly review: review-due flag in `status`; handoff record line; runbook step in `instructions/agent_skills.md` | REQ-014 | done | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | manual session check (`validation.md`, spike checks 2 and 4; build check B4); `test_offline_and_archive_source_nfr001` | done |
| AC-002 | `test_sync_pins_and_is_idempotent_ac002` | done |
| AC-003 | `test_sync_rejects_url_sources_ac003` | done |
| AC-004 | `test_tampered_skill_reported_ac004` | done |
| AC-005 | `test_sync_refuses_unsafe_files_ac005` | done |
| AC-006 | `test_reenabled_conflict_reported_ac006` | done |
| AC-007 | `test_url_marketplace_reported_ac007` | done |
| AC-008 | `test_status_reports_override_ac008` | done |
| AC-009 | `test_sync_change_summary_ac009` | done |
| AC-010 | `test_usage_standard_sections_ac010` | done |
| AC-011 | `test_project_optin_never_installs_ac011`; `validation.md` spike checks 6-7 | done |
| AC-012 | `test_citations_ac012`; `test_repo_integration_is_clean` | done |
| AC-013 | `test_consumer_drift_reported_ac013` | done |
| AC-014 | `test_web_group_opt_in_ac014` | done |
| AC-015 | `test_license_verbatim_and_size_ac015` | done |
| AC-016 | `test_bundled_copy_installs_offline_ac016`; real wheel + offline load in `validation.md` (build check B5) | done |
| AC-017 | `test_personas_in_default_allowlist_ac017`, `test_persona_routing_ac017` | done |
| AC-018 | `test_review_due_after_92_days_ac018` | done |

## Follow-ups

- QuantSmith-owned `/qs-build` command wrapping `incremental-implementation` + TDD against `tasks.md`, committing only when asked.
- Upstream PR to the fork: make `git-workflow-and-versioning` defer to repo attribution rules, so the override can be dropped.
