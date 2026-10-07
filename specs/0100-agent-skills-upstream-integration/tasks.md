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
| T-001 | Spike: confirm Claude Code project-local directory marketplace + `enabledPlugins` keys against current docs, offline; choose plugin route or `.claude/skills` fallback and record it in `plan.md` | REQ-005 | todo | Gates T-008; resolves RISK-004 |
| T-002 | `config/agent_skills.yml`: groups, defaults (incl. all three personas), exclusions with reasons, size cap | REQ-007, REQ-011, REQ-013 | todo | |
| T-003 | `src/quantsmith/agent_skills/` `sync` + `lock`: read local dir / clone ref (`git archive`) / tarball, copy allowlist, deterministic lock; console script | REQ-001, REQ-002, REQ-003, NFR-002, NFR-004 | todo | |
| T-004 | Sync safety and reporting: reject URL sources, symlinks, executables, oversize, out-of-allowlist; change summary; `diff` and `--dry-run` | REQ-003, REQ-011, NFR-001, NFR-003 | todo | |
| T-005 | `status` and `install --scope user|project`; `QS_AGENT_SKILLS_PATH`; detect duplicate user-level installs | REQ-006 | todo | RISK-008 |
| T-006 | First sync at fork `f63ec56` (v0.6.7); QuantSmith-owned `README.md` (provenance, credit) and overlay `plugin.json`; verbatim `LICENSE` | REQ-001, NFR-007 | todo | Separate PR (plan: Rollout) |
| T-007 | `hooks/stages/agent-skills-check.sh`: hashes vs lock, frontmatter, allowlist/exclusions, URL sources, agent citations, registry name collisions, size; wire into `run-stage.sh` and CI | REQ-004, REQ-007, NFR-004, NFR-005 | todo | |
| T-008 | Root `.claude-plugin/marketplace.json` and `.claude/settings.json` entries (keep existing SessionStart hook) | REQ-005, NFR-006 | todo | Depends on T-001 |
| T-009 | `instructions/agent_skills.md`: precedence, stage map (incl. persona routing), exclusions, overrides, refresh runbook, kill switch and removal | REQ-008, REQ-013, NFR-006 | todo | |
| T-010 | Cite skills in `implementation`, `testing_validation`, `git_release`, `test_engineering/*`, `quality-guard-agent` instructions; note in `agents/README.md`; regenerate registry | REQ-009 | todo | |
| T-011 | `docs/adoption_guide.md` section; `vendor/agent-skills` as a `QF_UPSTREAM_SURFACES` example; `docs/handoff.md` pin line | REQ-010 | todo | |
| T-012 | Tests (`tests/test_agent_skills.py`, gate fixtures) incl. network-off proof; manual Claude Code check for AC-001/AC-011 into `validation.md` | NFR-001, NFR-002, REQ-004 | todo | |
| T-013 | Indexes and changelog: `specs/README.md`, `CHANGELOG.md`, `README.md` spec count, `CLAUDE.md` pointer | REQ-008 | todo | |
| T-014 | Bundle the vendored tree and lock into the wheel via `setup.py` (`quantsmith/_bundled/agent_skills/`); build fails on lock mismatch; `install --scope user` falls back to it | REQ-012 | todo | Same mechanism as analytics packs |
| T-015 | Quarterly review: review-due flag in `status`; handoff record line; runbook step in `instructions/agent_skills.md` | REQ-014 | todo | |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | manual session check, `validation.md` (names AC-001); `test_no_network_ac001` | todo |
| AC-002 | `test_sync_pins_and_is_idempotent_ac002` | todo |
| AC-003 | `test_sync_rejects_url_sources_ac003` | todo |
| AC-004 | gate fixture `tampered_skill` (AC-004) | todo |
| AC-005 | `test_sync_refuses_unsafe_files_ac005` | todo |
| AC-006 | gate fixture `reenabled_conflict` (AC-006) | todo |
| AC-007 | gate fixture `url_marketplace` (AC-007) | todo |
| AC-008 | `test_status_reports_override_ac008` | todo |
| AC-009 | `test_sync_change_summary_ac009` | todo |
| AC-010 | `test_usage_standard_sections_ac010` | todo |
| AC-011 | manual session check with plugin disabled, `validation.md` (names AC-011) | todo |
| AC-012 | gate fixture `dangling_citation` (AC-012) | todo |
| AC-013 | gate fixture `consumer_drift` (AC-013) | todo |
| AC-014 | `test_web_group_opt_in_ac014` | todo |
| AC-015 | `test_license_verbatim_and_size_ac015` | todo |
| AC-016 | `test_bundled_copy_installs_offline_ac016` | todo |
| AC-017 | `test_personas_and_routing_ac017` | todo |
| AC-018 | `test_review_due_after_92_days_ac018` | todo |

## Follow-ups

- QuantSmith-owned `/qs-build` command wrapping `incremental-implementation` + TDD against `tasks.md`, committing only when asked.
- Upstream PR to the fork: make `git-workflow-and-versioning` defer to repo attribution rules, so the override can be dropped.
