# Plan: Skills export and registry

- **Spec:** 0110-skills-export-registry (`spec.md`)
- **Status:** Draft
- **Author:** QuantSmith
- **Last updated:** 2026-10-10

> HOW. Requires the approved `spec.md`.

## Approach

A generator plus a registry, modelled on `scripts/build_agent_registry.py` (generated
index, staleness test) and `0100` (local plugin marketplace, integrity gate). The
build renders every agent, compares rendered hashes to the registry, and only then
writes — so the registry's revisions and dates move exactly when content moves.
`check` re-renders and compares without touching dates, which makes it safe for a
gate that runs every day.

## Architecture & Components

- `render(root, agent_dir)` → `SkillDoc`: frontmatter (`name`, `description`,
  `metadata.source/category/generator/source-hash`), a generated-file banner, then
  `Role` (prompt), `Procedure` (authored SKILL.md), README `Use When` / `Inputs` /
  `Outputs` / `Required Review Themes`, `Instructions`, `Tasks` (headings demoted).
- Discovery: every `prompt.md` directory under `agents/` minus folders `git check-ignore`
  reports (local-only material), so the export is identical on every machine.
- Names: authored SKILL.md name, else the agent path lower-cased with non-alphanumerics
  as hyphens; `config/skills_export.json` `name_overrides` win; `exclude` skips.
- Description: first sentence of README Purpose + "Use when" the first two Use When
  bullets; backticks/asterisks stripped, angle brackets replaced, capped at 1024.
- `build(root, today)`: validate → refuse non-generated name clashes → add / revise /
  retire entries → write changed files only → bump `generation` only on change.
- `check(root)`: findings for missing registry, missing/stale/hand-edited skills,
  retired-but-active or retired-but-present, sort order, invalid config.
- Project selection: `config/skills_export.json` → `project.categories` / `project.agents`
  decide which skills are written to `.claude/skills/`; each entry records `project`
  and `path` (null when not materialized). Toggling never bumps revision or generation.
- `pending(root, target)`, `mark_published(root, target)`.
- `package_plugin(root, out, version)`: `out/.claude-plugin/marketplace.json` +
  `out/quantsmith-skills/{.claude-plugin/plugin.json, skills/, registry.json}`.
- `package_zips(root, out, names)`: `<name>.zip` holding `<name>/SKILL.md`, fixed
  timestamps.
- CLI `quantsmith-skills` (`build`, `check`, `list`, `pending`, `mark-published`,
  `package`). Gate `skills-export`; pre-commit (when agents/export/config staged); CI.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P1/P2 Spec is the source; traceability | yes | Skills are generated from agents; registry traces each to its agent. |
| P4 Correct by construction | yes | Validation before write; idempotent build; refuses to clobber. |
| P5 Reversibility | yes | Tombstones; reactivation; everything regenerable. |
| P6 Observability | yes | Revisions, generations, per-target pending lists. |
| P9 Security & data | yes | No network or credentials; nothing uploaded automatically. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `render`, `render_all` | T-001 |
| REQ-002 | `skill_name`, `_description`, `validate`, config overrides | T-001 |
| REQ-003 | `build` registry update | T-002 |
| REQ-004 | `build` retire / reactivate | T-002 |
| REQ-005 | `check`, gate, pre-commit, CI, test | T-003 |
| REQ-006 | `pending`, `mark_published` | T-004 |
| REQ-007 | `package_plugin`, `package_zips` (render from agents, verified against registry hashes) | T-004 |
| REQ-008 | `load_config` `project`, `in_project`, build/check placement | T-006 |
| NFR-001..003 | generation-only writes, deterministic output, clash refusal | T-001..T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Location | `.claude/skills/` (committed) | Root `skills/` | Claude Code only discovers `.claude/skills/`; a root folder is a third copy. |
| Plugin | Packaged on demand | Second committed copy | Avoids duplicating 204 files; plugin built from the same files. |
| Content | Self-contained (inlined) | Links into the repo | Claude.ai and other repos cannot follow repo paths. |
| Registry dates | Change only with content | Stamp every build | Stamping every build makes the check fail daily and hides real changes. |
| Distribution | Print commands, track marks | Call APIs / CLI | No credentials or network in the SDK; human publishes. |

## Validation Strategy

AC-001..AC-008 map to `tests/test_skills_export.py`; the gate is exercised directly.

## Rollout, Observability & Rollback

Generation 1 exports all 204 shared agents. Each later agent change ships with its rebuilt
skill. Rollback: revert the commit; the registry returns with it.
