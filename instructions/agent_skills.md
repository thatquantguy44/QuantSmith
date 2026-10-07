# agent-skills Instructions

## Purpose

Use this instruction set when a coding task (implementing, testing, debugging, reviewing, shipping) can draw on the
vendored [agent-skills](https://github.com/addyosmani/agent-skills) subset in `vendor/agent-skills/`, and when
maintaining that subset. Spec: `specs/0100-agent-skills-upstream-integration/`.

agent-skills is a catalog of general software-engineering practice (`SKILL.md` files, three slash commands, three
reviewer personas). QuantSmith uses it as a **pinned, offline upstream**: an allowlisted copy, hashed in
`vendor/agent-skills.lock.json`, read from the local filesystem. Nothing is fetched from GitHub at use time.

## Required Inputs

- The task and its SDD stage (Specify, Implement, Verify, Review, Ship).
- The spec directory the work traces to (`specs/NNNN-slug/`).
- For maintenance: a local clone, mirror or `git archive` of the fork `thatquantguy44/agent-skills`.

## Expected Output

- Work that follows the applicable skill's process and still meets every QuantSmith rule below.
- For maintenance: a sync PR containing only `vendor/agent-skills/` and the lock, with the change summary in the PR body.

## Precedence

When guidance conflicts, the higher item wins:

1. `instructions/engineering_principles.md` (the constitution).
2. QuantSmith instructions, agents and `CLAUDE.md` (including `instructions/git_workflow.md` and
   `instructions/spec_driven_development.md`).
3. agent-skills.

agent-skills supplies *technique*: how to write the failing test first, how to bisect a bug, what a five-axis review
covers. It never decides *where artifacts go*, *how work is traced*, or *when to commit*.

## Stage Map

| SDD stage | QuantSmith owner | agent-skills (by vendored path) | QuantSmith override |
| --- | --- | --- | --- |
| Specify | `planning_requirements` | `vendor/agent-skills/skills/interview-me/SKILL.md`, `vendor/agent-skills/skills/idea-refine/SKILL.md` | Output goes only into `specs/NNNN-slug/spec.md` with `REQ-`/`NFR-`/`AC-` IDs; never `docs/ideas/` (its script is not vendored). |
| Implement | `implementation` | `vendor/agent-skills/skills/incremental-implementation/SKILL.md`, `vendor/agent-skills/skills/test-driven-development/SKILL.md`, `vendor/agent-skills/skills/source-driven-development/SKILL.md`, `vendor/agent-skills/skills/api-and-interface-design/SKILL.md`, `vendor/agent-skills/skills/context-engineering/SKILL.md` | Tasks come from `tasks.md`; tests name the `AC-*` they prove; point-in-time and leakage rules are never relaxed. |
| Verify | `testing_validation`, `test_engineering/*` | `vendor/agent-skills/skills/test-driven-development/SKILL.md`, `vendor/agent-skills/skills/debugging-and-error-recovery/SKILL.md`, `vendor/agent-skills/skills/doubt-driven-development/SKILL.md`; persona `test-engineer` | Route test work to `test_engineering_orchestrator` first. Use `test-engineer` only for generic test design; its tests must name `AC-*`. Quant validation (`backtest_review`, leakage) is still required. |
| Review | `quality-guard-agent`, review path | `vendor/agent-skills/skills/code-review-and-quality/SKILL.md`, `vendor/agent-skills/skills/code-simplification/SKILL.md`, `vendor/agent-skills/skills/security-and-hardening/SKILL.md`, `vendor/agent-skills/skills/performance-optimization/SKILL.md`; personas `code-reviewer`, `security-auditor`; commands `/agent-skills:review`, `/agent-skills:code-simplify` | Findings are also checked against the constitution. |
| Ship / Operate | `git_release`, `deployment_release`, `maintenance_monitoring` | `vendor/agent-skills/skills/git-workflow-and-versioning/SKILL.md`, `vendor/agent-skills/skills/ci-cd-and-automation/SKILL.md`, `vendor/agent-skills/skills/documentation-and-adrs/SKILL.md`, `vendor/agent-skills/skills/observability-and-instrumentation/SKILL.md`, `vendor/agent-skills/skills/deprecation-and-migration/SKILL.md`, `vendor/agent-skills/skills/shipping-and-launch/SKILL.md` | Conventional Commits; commit and push only when asked; **no attribution footers or AI co-author trailers** (`CLAUDE.md`, `agent-attribution` gate); release gates stay `deployment_release` and `deployment-check`. |

Shared checklists live in `vendor/agent-skills/references/` (definition of done, testing patterns, security,
performance, observability, orchestration patterns).

## Exclusions

These upstream items are kept out by `config/agent_skills.json`. The `agent-skills` gate reports any of them that gets
re-enabled or vendored.

| Item | Reason |
| --- | --- |
| `spec-driven-development`, `planning-and-task-breakdown` | Write a root `SPEC.md` and plan artifacts with their own ID scheme, bypassing `specs/NNNN-slug/` and the `spec-check` gate (P1, P2). |
| `using-agent-skills` | Meta-router that sends work to the excluded commands. QuantSmith routing is `workflow_orchestrator` plus this file. |
| `/spec`, `/plan`, `/ship` | Same reasons as above; `/ship` would make a go/no-go outside QuantSmith's release gates. |
| `/build` | Commits after every task and may generate its own plan. QuantSmith commits only when asked and takes tasks from `tasks.md`. |
| `idea-refine/scripts/` | Executable that creates `docs/ideas/`; vendored content is never executed (NFR-003). |
| Upstream hooks | The session-start hook injects the excluded meta-router and needs `jq`; the others run shell from vendored content. |
| Web group (`frontend-ui-engineering`, `browser-testing-with-devtools`, `/webperf`, `web-performance-auditor`) | Off by default. Enable the `web` group for work under `web/` or `apps/`. |

### References to excluded items inside vendored files

Some vendored files still name excluded items. Map them; never go looking for the upstream originals:

| Vendored text says | Do this in QuantSmith |
| --- | --- |
| `interview-me`: hand off to `spec-driven-development` / `planning-and-task-breakdown` | Write the confirmed intent into `specs/NNNN-slug/spec.md` (`planning_requirements`), then `plan.md` and `tasks.md` per `instructions/spec_driven_development.md`. |
| `idea-refine`: run `scripts/idea-refine.sh`, save to `docs/ideas/` | Skip the script (not vendored); record the refined idea in the spec's Problem & Context. |
| `references/orchestration-patterns.md`: `/spec`, `/plan`, `/build`, `/ship` | Those commands are not available; route through `workflow_orchestrator` and the stage agents. |
| `definition-of-done.md` / `using-agent-skills` mentions | QuantSmith's Definition of Done is in each spec's `tasks.md` and the constitution (P3). |

## Connecting

All three routes are offline. Run `quantsmith-agent-skills status` to see which copy is in effect.

1. **This checkout (default).** One time per machine: `quantsmith-agent-skills install --scope project`. It runs
   `claude plugin marketplace add <repo> --scope local`, which writes the gitignored `.claude/settings.local.json`.
   Claude Code never activates a plugin that only repo-authored settings enable, so a fresh clone does nothing until
   you opt in.
2. **Installed (user level).** `quantsmith-agent-skills install --scope user` registers the copy bundled in the
   `quantsmith` package (or `--path <marketplace dir>`), for use outside a QuantSmith checkout.
3. **Override (developing skills).** `export QS_AGENT_SKILLS_PATH=<your clone of the fork>`, then
   `claude --plugin-dir "$QS_AGENT_SKILLS_PATH"` for that session only. `status` reports it as unpinned.

**Kill switch.** Set `"agent-skills@quantsmith-local": false` under `enabledPlugins` in `.claude/settings.json`. Never
run `claude plugin install` for this plugin at project or local scope: that writes a local `true`, which overrides the
committed switch. If `status` reports another agent-skills install (for example one from the GitHub marketplace),
uninstall it so only the pinned copy loads.

**Removal.** Delete `vendor/agent-skills/`, `vendor/agent-skills.lock.json`, `.claude-plugin/marketplace.json`,
`config/agent_skills.json` and the `enabledPlugins` entry. Nothing else depends on them.

## Maintenance

- **Never edit `vendor/agent-skills/` by hand.** Sessions read it live, so an edit takes effect at once, and the gate
  reports it as modified. Fix the skill in the fork, then re-sync.
- **Refresh runbook:** update your local clone of the fork, then
  `quantsmith-agent-skills diff --source <clone> --ref <sha>`. Review every changed item: this is third-party prompt
  text that agents will follow. Then run `quantsmith-agent-skills sync --source <clone> --ref <sha>`. Open a PR with
  only `vendor/` and the lock, and paste the change summary into it.
- **Quarterly review:** when `status` says the review is due (last sync more than 92 days ago), run the runbook. If
  nothing is worth taking, add a dated "reviewed, no change" line to the agent-skills pin entry in `docs/handoff.md`.
- **Scope changes:** edit groups or exclusions in `config/agent_skills.json`, then re-sync. Re-enabling a conflicting
  item is reported by the gate and needs an exception entry under the constitution.

## Standards

- Cite skills by vendored path (`vendor/agent-skills/skills/<name>/SKILL.md`) so any agent host can read them as files.
- Treat every upstream change as a supply-chain change: it gets a reviewed PR.
- Keep the gate green: `QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh agent-skills`.

## Review Checklist

- Does the work trace to a spec, whichever skill guided it?
- Were QuantSmith overrides (traceability, commit policy, attribution) applied where a skill says otherwise?
- For a sync PR: does the diff contain only `vendor/` and the lock, and were the changed skills read?
