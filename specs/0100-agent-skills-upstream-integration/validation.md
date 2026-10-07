# Validation: agent-skills as a Pinned, Offline Upstream

- **Spec:** 0100-agent-skills-upstream-integration
- **Last updated:** 2026-10-07

## T-001: Claude Code local-directory marketplace (2026-10-07)

**Question.** Can Claude Code load the vendored subset from a marketplace inside the repo, with no network, and how is it switched
on and off?

**Setup.** Claude Code `2.1.292` on Linux. A throwaway `HOME` per run, so no prior user state. A fixture repo holds
`vendor/agent-skills/` (3 skills, the `/review` and `/test` commands, the `code-reviewer` and `test-engineer` agents, LICENSE, and an
overlay `plugin.json`) plus a root `.claude-plugin/marketplace.json` with `source: "./vendor/agent-skills"`. CLI steps ran under
`unshare -n` (no network interface). Session starts used `claude -p` with a dummy API key: the model call fails, but plugin loading
runs first and is visible in `--debug-file`.

| # | Check | Result |
| --- | --- | --- |
| 1 | `claude plugin validate` on the marketplace and on the plugin, offline | Pass (one warning: marketplace has no description) |
| 2 | Committed `extraKnownMarketplaces` (`directory`, relative `./` or absolute path) + `enabledPlugins: true`, fresh `HOME`, session start | **Not loaded.** Log: `Skipped auto-recording agent-skills@quantsmith-local — enabled only by repo-authored settings` and `Skipping orphaned enabledPlugins entry … marketplace not registered` |
| 3 | Hand-written `.claude/settings.local.json` declaring the marketplace + committed `enabledPlugins: true` | Not loaded (marketplace not registered) |
| 4 | `claude plugin marketplace add <abs repo> --scope local` (offline) + committed `enabledPlugins: true`, no `plugin install` | **Loaded**: 3 skills, 2 commands, 2 agents, read from `<repo>/vendor/agent-skills/` |
| 5 | `claude plugin marketplace add --scope project` | Writes an **absolute** path into the committed `.claude/settings.json`, so it is unsuitable for a tracked file |
| 6 | Settings precedence: project `false`, local `{marketplace, enabled: true}` (what `plugin install --scope local` writes) | Loaded: the local `true` overrides the committed kill switch |
| 7 | Project `true` / `false`, local `{marketplace only}` | Loaded / not loaded: the committed switch works |
| 8 | Overlay `plugin.json` with `agents: ["./agents/a.md", …]` | Validates, but **0 agents** load |
| 9 | Overlay with `agents: "./agents"` | Validation error: `must end with ".md"` |
| 10 | Overlay with no `agents` key | 2 agents load (default discovery) |
| 11 | Edit a vendored `SKILL.md` without changing `version`, then `plugin update` | Cache copy unchanged ("already at the latest version"); sessions still read the live vendored file (check 4 log) |
| 12 | `claude --plugin-dir vendor/agent-skills` with a fresh `HOME` | Loaded inline for that session; no registration needed |

**Outcome.** The plugin route works offline and stays the primary design. These adjustments are recorded in `plan.md` (Settings):

- One-time per-machine opt-in via `marketplace add --scope local`. Never `plugin install` at project/local scope (check 6).
- The committed settings carry only `enabledPlugins`, the kill switch (check 7). No committed marketplace path (checks 2, 5).
- The overlay `plugin.json` omits `agents` (checks 8–10).
- Sync stamps a content-derived `version`, so the CLI's cached inventory shows the pin in use (check 11).
- The developer override uses `--plugin-dir` (check 12).

**Not covered here.** The interactive (TTY) session start, which may prompt to install repo-declared plugins; macOS and Windows; the
user-scope install of the bundled copy. All three are checked under AC-001 and AC-016 once built.

## Build verification (2026-10-07)

Run against the real fork (`/home/user/agent-skills`, `f63ec56`, plugin `0.6.7`) in scratch locations. Nothing was
vendored into the repository; the first sync is T-006, in its own PR.

| # | Check | Result |
| --- | --- | --- |
| B1 | `sync --source <fork clone> --ref f63ec56` | 35 files, 366,512 bytes (budget 1 MiB). Version stamp `0.6.7+f63ec56.53469383`; no problems, no warnings |
| B2 | Same sync again | Change summary `{}`; vendored tree and lock byte-identical (`cmp`) (AC-002, NFR-002) |
| B3 | `claude plugin validate` on the generated plugin, offline | Pass |
| B4 | `install --scope project` (fresh `HOME`), then a session start | Marketplace registered at local scope only. **19 skills, 3 commands, 3 agents** loaded from `vendor/agent-skills/`; 0 hooks; none of the excluded items |
| B5 | `uv build --wheel`, then install into a clean venv (`--no-deps --no-index`) and run from a directory with no checkout and no config | Wheel carries 39 bundle files (35 vendored, 2 generated, lock, marketplace manifest). `status` reports `bundled`, `matches_lock: true`. `install --scope user` registers and installs it; a session loads 19 skills, 3 agents, 3 commands (AC-016). This check found a real gap: without a checkout, `status`/`install` had no config. It was fixed by bundling `config/agent_skills.json` (plan: Deviations) |
| B6 | Mutation check of the safety rules: disable the executable refusal, then the hash comparison | `test_sync_refuses_unsafe_files_ac005[executable]` and `test_tampered_skill_reported_ac004` fail respectively; both pass again when restored |

Suite: `tests/test_agent_skills.py` has 32 tests; the full suite (`uv run --frozen --all-extras pytest tests/`, as CI
runs it) passes with 1410 tests. Gates: `QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh` passes, including the new
`agent-skills` gate. `ruff` is clean on the changed Python files.

## T-006: first vendored sync (2026-10-07)

`quantsmith-agent-skills diff`, then `sync --source <fork clone> --ref f63ec56`. 32 items added (35 files,
366,512 bytes), with no problems and no warnings. `verify` is clean and `status` reports `repo`, `matches_lock: true`,
`pinned: true`. Version stamp `0.6.7+f63ec56.53469383`, identical to the build checks above.

**Content review** of every vendored file at `f63ec56`, as third-party prompt text that agents will follow:

| Check | Result |
| --- | --- |
| Piped installs, destructive shell, injection directives, exfiltration | None. The only hit is `source-driven-development` warning agents *against* "ignore previous instructions" in fetched content |
| Attribution, co-author trailers, `--no-verify`, force-push advice | None that conflicts. Upstream advises against force-pushing shared branches; the "attribution" hits are web-vitals API names |
| References to excluded items | `interview-me` hands off to `spec-driven-development` / `planning-and-task-breakdown`; `idea-refine` points at its unvendored script and `docs/ideas/`; `references/orchestration-patterns.md` describes `/spec`, `/plan`, `/build`, `/ship`. All are mapped to QuantSmith equivalents in `instructions/agent_skills.md` |
| Reference docs linked by vendored files | Every vendored reference is linked by at least one vendored skill (`orchestration-patterns` by `doubt-driven-development`), so none was dropped |
