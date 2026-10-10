# Spec: Skills export and registry

- **ID:** 0110-skills-export-registry
- **Status:** Draft
- **Author:** QuantSmith
- **Approver:** (pending)
- **Last updated:** 2026-10-10

> WHAT and WHY only. Implementation lives in `plan.md`.

## Problem & Context

QuantSmith's 204 shared agents are Markdown roles under `agents/`. They are usable by an
agent that reads this repository, but not as Claude skills: Claude Code discovers
project skills only in `.claude/skills/`, other repositories need a plugin, and
Claude.ai needs uploaded skills. Copies of some agents were exported to Claude.ai
by hand; they already lag the repository (agents added in `0101` and `0102` are
missing), and nothing records which copy is current. A hand-maintained root
`skills/` folder would repeat the drift `agent_registry.yaml` was generated to end.

## Goals

- Generate one self-contained Claude skill per agent from `agents/`, committed in
  `.claude/skills/` so everyone who clones the repository gets them.
- Keep a registry that records each skill's revision, lifecycle dates, hashes, and
  status, and that only changes when a skill actually changes.
- Fail fast — gate, pre-commit, CI, tests — when the export is stale or hand-edited.
- Track publication per distribution target and list exactly what to upload and
  delete; package a plugin and upload archives from the same files.

## Non-Goals

- Uploading to Claude.ai or running `claude plugin` commands (no network, no
  credentials; the tool prints the commands).
- Changing the agent contract or `agents/agent_registry.yaml`.
- Managing third-party skills (owned by `0100`).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall generate, for every public agent that is neither excluded by configuration nor gitignored (local-only), a `SKILL.md` under `.claude/skills/<name>/` containing the agent's role, use cases, inputs, outputs, review themes, instructions, tasks, and any hand-authored skill procedure. | must |
| REQ-002 | The system shall give each skill a valid, unique, stable name (lowercase, hyphenated, at most 64 characters, no reserved words) and a description of at most 1024 characters stating what it does and when to use it; configuration may override names. | must |
| REQ-003 | The system shall maintain a registry entry per skill with status, revision, introduced/updated/removed dates, the generation of its last change, and source and skill hashes; a build with no change shall rewrite nothing. | must |
| REQ-004 | The system shall retire skills whose agent is removed (tombstone kept, directory deleted) and reactivate them with a new revision if the agent returns. | must |
| REQ-005 | The system shall report, without dates or network, every stale, missing, hand-edited, or retired-but-present skill, and invalid configuration; and enforce it in a gate, pre-commit, CI, and tests. | must |
| REQ-006 | The system shall record per-target publication generations and list the skills to upload and delete for a target since its last publication. | must |
| REQ-007 | The system shall package the active skills as a local plugin marketplace and as one deterministic archive per skill. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Single source of truth | No skill content is authored outside `agents/` and `config/skills_export.json`. |
| NFR-002 | Determinism | The same agents produce byte-identical skills, registry, and archives. |
| NFR-003 | Safety | The build never overwrites a hand-written skill directory it did not generate. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given this repository, when checked, then the export is fresh and every non-excluded agent has an active entry and a skill file. | REQ-001, REQ-005 |
| AC-002 | Given every agent, when rendered, then names and descriptions satisfy the limits, the body contains the agent's prompt, instructions, and tasks, and authored names and procedures are kept; a gitignored agent produces no skill and no registry entry. | REQ-001, REQ-002 |
| AC-003 | Given a build, when rebuilt unchanged, then nothing is rewritten; when one agent changes, only it gets a new revision and date in a new generation; when an agent is removed and restored, it is tombstoned then reactivated with a higher revision. | REQ-003, REQ-004, NFR-002 |
| AC-004 | Given a fresh export, when a skill is hand-edited or an agent changes, then check reports it; a rebuild repairs the edit without a revision bump; unrelated hand-made skill directories are ignored. | REQ-005 |
| AC-005 | Given an over-long or colliding name, an override or exclusion for an unknown agent, or a hand-made directory with a generated name, then build or check rejects it. | REQ-002, NFR-003 |
| AC-006 | Given a published target, when one skill changes and one is removed, then pending lists exactly that upload and that delete; marking is refused while stale. | REQ-006 |
| AC-007 | Given a fresh export, when packaged, then the plugin manifest, marketplace, and skills are complete, and per-skill archives are deterministic. | REQ-007, NFR-002 |
| AC-008 | Given the CLI and the gate, when run on stale and fresh exports, then they fail and pass respectively. | REQ-005 |

## Data & Dependencies

- Runtime: `src/quantsmith/skills_export/` (CLI `quantsmith-skills`), stdlib only.
- Config: `config/skills_export.json`. Output: `.claude/skills/`.
- Gate: `hooks/stages/skills-export-check.sh`; pre-commit; CI step.
- Standard: `instructions/skills_export.md`. Related: `0100` (third-party skills),
  `agents/agent_registry.yaml` (agent index).

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Hand edits to generated skills. | Drift from agents. | Hash check in gate/pre-commit/CI; rebuild repairs (AC-004). |
| RISK-002 | A rename silently retires a published skill. | Users lose a skill name. | `name_overrides`; removal is explicit in `pending` (AC-006). |
| RISK-003 | 204 project skills exceed Claude Code's skill-listing budget. | Some skills hidden in sessions here. | `exclude` configuration; documented in the standard. |
| RISK-004 | Claude.ai copies fall behind. | Users run outdated roles. | Per-target generations and `pending` (AC-006). |
| RISK-005 | Generated files overwrite a hand-written skill. | Lost work. | Build refuses non-generated directories (AC-005). |
| RISK-006 | Local-only (gitignored) agents are exported and pushed. | Material the owner kept out of the repository is published. | Gitignored agent folders are skipped before rendering; no tombstone is written (AC-002). |

## Assumptions & Open Questions

- Assumption: frontmatter keys `name`, `description`, and `metadata` are accepted by
  Claude Code and Claude.ai skill upload.
- Open question: automate Claude.ai publication once an API for organization skills
  is available.

## Exceptions

None.
