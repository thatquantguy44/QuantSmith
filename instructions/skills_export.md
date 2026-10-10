# Skills Export Instructions

## Purpose

Every QuantSmith agent is also published as a Claude skill, so the same role is
available wherever people work: in Claude Code sessions in this repository, in
other repositories through a plugin, and in Claude.ai. The skills are **generated**
from `agents/`, which stays the single source of truth, and tracked in a registry
so every change is versioned and every distribution target can be brought up to
date. Spec: `specs/0110-skills-export-registry/`.

## Where Things Live

| Path | What | Edited by |
| --- | --- | --- |
| `agents/<path>/` | The agent (README, prompt, instructions, tasks, optional SKILL.md). | People |
| `config/skills_export.json` | `name_overrides` (agent path → skill name), `exclude` (not exported anywhere), and `project` (which skills load as project skills here). Gitignored (local-only) agent folders are never exported. | People |
| `.claude/skills/<name>/SKILL.md` | The generated skill. Claude Code loads it for anyone who clones the repo. | `quantsmith-skills build` only |
| `.claude/skills/registry.json` | The lifecycle registry. | `build` and `mark-published` only |

## Who Sees The Skills

| Audience | How |
| --- | --- |
| Anyone running Claude Code in a clone of QuantSmith | Automatic: the project selection (53 core skills) committed in `.claude/skills/`. Install the plugin for the rest. |
| Claude Code in another repository, or user-wide | `quantsmith-skills package --format plugin --out DIR`, then `claude plugin marketplace add DIR` and `claude plugin install quantsmith-skills@quantsmith-skills-local`. |
| Claude.ai (personal or organization skills) | `quantsmith-skills package --format zip --out DIR --pending-for claude_ai`, upload the zips, delete the listed removed skills, then `quantsmith-skills mark-published --target claude_ai`. |

## The Registry

One entry per skill ever exported, sorted by name:

- `name`, `agent`, `category`, `description`, `path`.
- `project` / `path` — whether the skill is materialized in `.claude/skills/` for this
  repository, and where (`path` is null otherwise). Every active skill is packaged.
- `status` — `active` or `removed` (removed entries are kept as tombstones so
  targets know what to delete).
- `revision` — starts at 1 and increments only when the rendered skill changes.
- `introduced`, `updated`, `removed` — dates of first export, last change, retirement.
- `updated_generation` — the registry `generation` in which the skill last changed.
- `source_hash` (the agent's files) and `skill_hash` (the rendered `SKILL.md`).

Top level: `generation` increments once per build that changes anything; `targets`
records, per distribution target, the generation it was last published at.
`pending --target T` lists exactly the skills to upload and delete for `T`.

## Operating Rules

- Never edit `.claude/skills/` by hand. Change the agent, then rebuild:
  `PYTHONPATH=src python3 -m quantsmith.skills_export build` (or `quantsmith-skills build`).
- Commit the agent change and the rebuilt export together. The pre-commit hook,
  the `skills-export` gate, CI, and `tests/test_skills_export.py` fail otherwise.
- A build with no agent change rewrites nothing, so rebuilding is always safe.
- Keep a published name stable. When an agent is renamed or moved, add a
  `name_overrides` entry with the old skill name unless retiring it is intended.
- Skill names must be lowercase letters, digits, and hyphens, at most 64
  characters, unique, and free of the reserved words `claude` and `anthropic`;
  override names that violate this.
- After publishing to a target, run `mark-published --target <target>`; it refuses
  while the export is stale.
- Hand-written project skills may live in `.claude/skills/` under names the
  export does not use; the build leaves them alone and refuses to overwrite them.

## Context Budget And Project Selection

Claude Code lists every project skill's description at session start, within a
fixed budget. With all 204 skills loaded only about 70 were listed with
descriptions; the rest were bare names that Claude rarely picks. So only a
selection is materialized here, set in `config/skills_export.json` → `project`:

- `categories` — top-level `agents/` folders (`root` for agents directly under it);
- `agents` — individual agent paths added on top.

The default keeps about 53 skills (about 16,500 description characters): the lifecycle
roles, data engineering, ingestion, provenance, test engineering, monitoring,
alerts, secrets management, and `tooling/dag_orchestration`. Every other skill is
still registered, versioned, and included in the plugin and Claude.ai packages —
install the plugin to use them in this repository too. Changing the selection is
placement, not content: it never bumps a revision or the generation. Keep the
selection's description total well under the budget, since account-level and
plugin skills share it.

## Checks

- Does `quantsmith-skills check` report no findings?
- Did every agent change ship with its rebuilt skill and registry entry?
- Is every distribution target's `pending` list empty after publishing?
- Are renamed agents mapped to their published names?
