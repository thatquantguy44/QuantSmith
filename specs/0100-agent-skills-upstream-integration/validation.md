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
