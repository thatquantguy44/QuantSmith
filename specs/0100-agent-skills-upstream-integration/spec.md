# Spec: agent-skills as a Pinned, Offline Upstream for Coding Tasks

- **ID:** 0100-agent-skills-upstream-integration
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-07

> WHAT and WHY only. HOW (sync mechanics, plugin wiring, gate logic) is in `plan.md`.

## Problem & Context

QuantSmith's agents cover quant research and model development well, but its general software-engineering practice (test-driven
development, incremental implementation, debugging, code review, simplification, security hardening) is thin and scattered across
agent `instructions.md` files. [`agent-skills`](https://github.com/thatquantguy44/agent-skills) — our fork of
`addyosmani/agent-skills`, MIT-licensed — is a maintained catalog of exactly those practices as `SKILL.md` files, slash commands and
reviewer personas.

Today the only way to use it is to reach it through GitHub (a plugin marketplace whose manifest points at
`addyosmani/agent-skills` on GitHub, or a session that has the repository attached). That fails offline, in containers whose network
policy blocks GitHub, and in consuming quant repos that copy QuantSmith and have no GitHub access to the fork. It also means whatever
the default branch says *today* is what an agent follows: there is no pin, no review of upstream changes, and no record of which
version produced a piece of work.

agent-skills also overlaps QuantSmith in ways that will cause harm if adopted wholesale: its `spec-driven-development` skill and
`/spec`, `/plan`, `/ship` commands produce a root `SPEC.md` and a different ID scheme than `specs/NNNN-slug/` with `REQ-*`/`AC-*`/`T-*`;
its session-start hook injects a meta-skill that routes work to those commands; and its git guidance does not know QuantSmith's rule
against attribution footers.

This spec makes agent-skills an **upstream**: pinned, vendored, verified, used from the local filesystem or a local install, refreshed
only by a deliberate, reviewed sync — and subordinate to QuantSmith's constitution where the two disagree.

## Goals

- Use agent-skills for coding tasks with **no network access at use time**: from a vendored copy inside the repo, or from a local
  clone/installed plugin on the developer's machine.
- Pin the upstream to an exact commit and make any local edit, missing file or unreviewed upstream change visible.
- Refresh from a local source (a clone, a mirror, or an archive) by one command that shows what changed before it is accepted.
- Say, for each QuantSmith stage, which agent-skills skill applies, and which upstream skills, commands and hooks are excluded or
  overridden because they conflict with QuantSmith.
- Carry the integration into consuming quant repos through the existing copy-and-own adoption model.

## Non-Goals

- No runtime fetch from GitHub or any URL; no auto-update; no Git submodule (it needs a remote at clone time).
- No edits to upstream skill content inside QuantSmith. Changes we want upstream go to the fork as PRs; QuantSmith re-syncs.
- No replacement of QuantSmith's own SDD flow, ID scheme, gates or agents by agent-skills equivalents.
- No support for agent hosts other than Claude Code beyond plain file paths (Codex, Cursor, Gemini setups are out of scope; they can
  read the vendored `SKILL.md` files directly).
- No vendoring of upstream `evals/`, `docs/`, `scripts/` or hooks (not needed to use the skills; hooks conflict — see REQ-007).

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | QuantSmith shall vendor an allowlisted subset of agent-skills at an exact upstream commit under `vendor/agent-skills/`, together with the upstream `LICENSE`, so the skills are usable from a plain checkout with no network. | must |
| REQ-002 | A lock file shall record the upstream identity (canonical repo name and fork), the commit SHA, the upstream plugin version, the source the sync read from, the sync date, the allowlist in force, and a SHA-256 for every vendored file. | must |
| REQ-003 | A sync command shall populate `vendor/agent-skills/` from a **local** source only — a directory, a ref in a local Git clone, or a `git archive` tarball — refusing any URL, and shall print a change summary (added, removed, modified files per skill) against the current lock before writing. | must |
| REQ-004 | A verify command and a stage gate shall report, without network: a vendored file whose hash differs from the lock, a file missing or unlisted, an allowlisted skill absent or with invalid `name`/`description` frontmatter, a vendored item outside the allowlist, a missing `LICENSE`, and any plugin/marketplace manifest in the integration whose source is a URL rather than a local path. | must |
| REQ-005 | Claude Code sessions in QuantSmith shall load the vendored skills and allowlisted commands from the local path, namespaced so they cannot shadow QuantSmith agents or commands, and enabled or disabled by one project setting. | must |
| REQ-006 | A developer shall be able to point the integration at a different local copy (a working clone of the fork, or a user-level installed plugin) via one environment variable or a user-level install command, without editing tracked files; `status` shall report which copy is in effect and whether it matches the lock. | must |
| REQ-007 | Upstream skills, commands and hooks that conflict with QuantSmith shall be excluded or overridden by default: `spec-driven-development`, `planning-and-task-breakdown`, `using-agent-skills`, the `/spec`, `/plan`, `/build`, `/ship` commands (`/build` commits after every task and generates its own plan) and all upstream hooks. Excluded items may be re-enabled only by editing the allowlist, which the gate reports. | must |
| REQ-008 | A usage standard (`instructions/agent_skills.md`) shall define precedence (constitution > QuantSmith instructions and agents > agent-skills), map each SDD stage to the applicable skills, state each exclusion and override with its reason, and state that QuantSmith rules on commits, PRs and attribution win over upstream git guidance. | must |
| REQ-009 | The coding-stage agents (`implementation`, `testing_validation`, `git_release`, `test_engineering/*`, and the review path) shall cite the agent-skills skills they use by vendored path, and `agents/README.md` shall note the integration. | should |
| REQ-010 | The adoption guide shall describe carrying `vendor/agent-skills/`, the lock, the allowlist and the settings into a consuming repo, and `vendor/agent-skills` shall be a supported `QF_UPSTREAM_SURFACES` entry for the existing upstream-drift gate. | should |
| REQ-011 | Web-only skills (`frontend-ui-engineering`, `browser-testing-with-devtools`, `/webperf`) shall be available as an opt-in allowlist group for work under `web/` and `apps/`, off by default. | could |
| REQ-012 | The `quantsmith` package shall bundle the vendored tree and lock as read-only defaults, so `pip install quantsmith` followed by `quantsmith-agent-skills install --scope user` makes the skills available on a machine with no QuantSmith checkout and no network; a repo-local `vendor/agent-skills/` shall take precedence over the bundled copy, and `status` shall say which is in effect. | must |
| REQ-013 | All three upstream reviewer personas (`code-reviewer`, `test-engineer`, `security-auditor`) shall be available as Claude Code subagents. `test-engineer` shall be subordinate to the QuantSmith `test_engineering` agents: the usage standard routes test work to `test_engineering_orchestrator` first, and any test the persona writes must name the `AC-*` it proves. | must |
| REQ-014 | Refresh shall be on demand, plus a quarterly review: `status` shall flag a lock older than 92 days as due for review, and the review (run `diff` against the local clone, then sync or record "no change") shall be recorded with its date in `docs/handoff.md`. | should |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Offline | `sync`, `verify`, `status`, the gate and skill use make zero network calls; proven by a test with network disabled. |
| NFR-002 | Determinism | The same source commit and allowlist produce a byte-identical vendored tree and lock (sorted entries, no timestamps except the recorded sync date, LF endings preserved as upstream). |
| NFR-003 | Supply-chain safety | Sync refuses symlinks, files outside the allowlisted paths, executable files, and any file over 256 KiB; vendored content is never executed by QuantSmith tooling. Every refresh is a reviewed diff in a PR. |
| NFR-004 | Dependencies | Tooling is Python standard library plus POSIX `sh`; no `jq`, no new package dependency. |
| NFR-005 | Footprint | Vendored tree under 1 MiB at the current upstream size (skills ~0.5 MiB). |
| NFR-006 | Reversibility | Disabling is one setting; removal is deleting `vendor/agent-skills/`, the lock and the settings entries, with no other code depending on them. |
| NFR-007 | Licensing | Upstream `LICENSE` (MIT, copyright Addy Osmani) is vendored verbatim and the README credits the upstream. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a fresh clone with the network disabled, when a Claude Code session starts before the one-time opt-in, then no agent-skills component loads; after `quantsmith-agent-skills install --scope project`, the allowlisted skills, commands and personas load under the `agent-skills:` namespace and none of the excluded ones do. | REQ-001, REQ-005, REQ-007, NFR-001 |
| AC-002 | Given a local clone of the fork at commit `X`, when `sync --source <clone> --ref X` runs, then `vendor/agent-skills/` holds exactly the allowlisted files at `X`, the lock records `X`, the plugin version and a hash per file, and a second run produces no diff. | REQ-001, REQ-002, REQ-003, NFR-002 |
| AC-003 | Given `--source https://…` or `git@…`, when `sync` runs, then it exits non-zero without writing and says only local sources are accepted. | REQ-003, NFR-001 |
| AC-004 | Given a vendored `SKILL.md` edited by hand, when the gate runs, then it reports that file as modified against the lock (advisory; blocking under `QF_STAGE_ENFORCE=1`). | REQ-004 |
| AC-005 | Given a source tree containing a symlink, an executable, or a file over the size cap inside an allowlisted skill, when `sync` runs, then it refuses and names the file. | NFR-003 |
| AC-006 | Given an allowlist that re-enables `spec-driven-development`, when the gate runs, then it reports the re-enabled conflicting item. | REQ-007, REQ-004 |
| AC-007 | Given a marketplace or plugin manifest in the integration with a `github` or URL source, when the gate runs, then it reports it. | REQ-004, NFR-001 |
| AC-008 | Given `QS_AGENT_SKILLS_PATH` pointing at a local clone, when `status` runs, then it reports that path as in effect, its commit, and whether it matches the lock; with the variable unset it reports the vendored copy. | REQ-006 |
| AC-009 | Given a new upstream commit with one changed skill, when `sync` runs, then it prints that skill as modified with its changed files before writing, and the resulting diff is limited to that skill and the lock. | REQ-003 |
| AC-010 | Given `instructions/agent_skills.md`, then it contains the precedence order, a stage-to-skill table covering Implement, Verify, Review and Ship, and an exclusion table naming every item in REQ-007 with its reason. | REQ-008 |
| AC-011 | Given the project setting disabled, when a session starts, then no agent-skills skill is loaded and no QuantSmith gate fails. | REQ-005, NFR-006 |
| AC-012 | Given the coding-stage agents, then each cites at least one vendored skill path that exists, checked by the gate. | REQ-009 |
| AC-013 | Given a consumer repo with `QF_UPSTREAM_SURFACES` including `vendor/agent-skills`, when the upstream-drift gate runs, then local divergence from QuantSmith's copy is reported. | REQ-010 |
| AC-014 | Given the `web` allowlist group off, then `frontend-ui-engineering`, `browser-testing-with-devtools` and `/webperf` are not vendored; turned on, they are, and the lock records the group. | REQ-011 |
| AC-015 | Given the vendored tree, then `LICENSE` matches upstream byte for byte, and the tree is under 1 MiB. | NFR-005, NFR-007 |
| AC-016 | Given a wheel built from the repo, when it is installed into a clean virtualenv with no network and `install --scope user` runs, then the user settings register the bundled copy, and its hashes match the repo lock. Given a repo with its own `vendor/agent-skills/`, then `status` reports the repo copy as in effect. | REQ-012 |
| AC-017 | Given the default allowlist, then `code-reviewer`, `test-engineer` and `security-auditor` are vendored and loaded as subagents, and `instructions/agent_skills.md` routes test work to `test_engineering_orchestrator` before `test-engineer`. | REQ-013 |
| AC-018 | Given a lock with `synced_on` 93 days before today, when `status` runs, then it reports the review as due; at 91 days it does not. | REQ-014 |

## Data & Dependencies

- **Upstream chain:** `addyosmani/agent-skills` (canonical) → `thatquantguy44/agent-skills` (fork; where our changes land as PRs) →
  a local clone or archive on the maintainer's machine → `vendor/agent-skills/` in QuantSmith → consuming quant repos by copy.
  GitHub is touched only when a maintainer chooses to update their local clone; QuantSmith tooling never touches it.
- **Pinned at authoring time:** fork `main` at `f63ec56a3cc936408d792956ae583c3c96a825bd`, plugin version `0.6.7`.
- **Claude Code:** project-level `.claude/settings.json` (already holds a SessionStart hook) and a local plugin marketplace. The exact
  local-marketplace settings keys are an assumption to confirm in `plan.md` T-001.
- **Existing QuantSmith surfaces reused:** `hooks/stages/common.sh`, `run-stage.sh`, `upstream-drift-check.sh`, `quantsmith.conf`,
  `docs/adoption_guide.md`.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Upstream skills contradict QuantSmith (SDD artifacts, ID scheme, attribution footers, commit style) and an agent follows the upstream one. | Untraceable work; gate failures; policy breach. | REQ-007 exclusions, REQ-008 precedence, override notes in the stage table; gate flags re-enabled conflicts. |
| RISK-002 | A malicious or careless upstream change rides in on a sync (prompt injection in a `SKILL.md`, a script). | Agents follow hostile instructions. | Local-only, manual sync; change summary; reviewed PR per refresh; no executables or hooks vendored (NFR-003). |
| RISK-003 | Vendored copy is edited in place and silently diverges from upstream. | Fork and QuantSmith disagree; fixes lost on next sync. | Per-file hashes; gate reports modified files; policy: fix in the fork, then re-sync. |
| RISK-004 | Claude Code's local plugin/marketplace configuration changes or drops directory sources. | Skills not loaded. | Confirmed working on 2.1.292 (T-001); `status` reports when the plugin is registered but not loading; fallback is project skills materialized under `.claude/skills/` (plan). |
| RISK-005 | Namespace collision: an upstream skill or command has the same name as a QuantSmith agent or command. | Wrong guidance invoked. | Plugin namespacing (`agent-skills:<name>`); gate checks collisions against `agents/agent_registry.yaml`. |
| RISK-006 | Context bloat: too many skills loaded into every session. | Worse routing, higher cost. | Allowlist of coding-relevant skills only; web group opt-in; no meta-skill injection. |
| RISK-007 | Consumer repos get stale copies. | Old guidance used for years. | Upstream-drift gate surface (REQ-010) and lock date shown by `status`. |
| RISK-008 | A developer also has agent-skills installed at user level from the GitHub marketplace, so two versions load. | Unpinned guidance wins unpredictably. | `status` detects a second installed copy and says which to remove (REQ-006). |

## Assumptions & Open Questions

- Resolved (T-001): Claude Code loads the vendored plugin from a local-directory marketplace offline, but only after a **one-time
  per-machine opt-in**. Plugins enabled only by repo-authored settings are never activated on their own. This is accepted: it is
  also a supply-chain safeguard (RISK-002). See `plan.md` Settings and `validation.md`.
- Assumption: the fork remains MIT and tracks `addyosmani/agent-skills`; QuantSmith pins the fork, not the canonical repo, so our
  fixes are available without waiting for upstream.
### Decisions (2026-10-07)

- **Bundle in the wheel: yes** (REQ-012). This makes the "installed" connection work without a checkout. The analytics packs set the precedent (spec `0081`): copied at build time and overridden by a local copy.
- **Personas: all three** (REQ-013). `test-engineer` is included but ranks below the QuantSmith `test_engineering` agents, so test routing stays unambiguous.
- **Refresh: on demand + quarterly review** (REQ-014). The fork's skills last changed 2026-08-27, so a fixed sync schedule would mostly produce empty updates.

## Exceptions

None.
