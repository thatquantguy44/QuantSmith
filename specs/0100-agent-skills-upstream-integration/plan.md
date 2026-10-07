# Plan: agent-skills as a Pinned, Offline Upstream for Coding Tasks

- **Spec:** 0100-agent-skills-upstream-integration (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-07

> HOW. Every requirement in the spec appears in the traceability matrix below.

## Approach

Treat agent-skills the way a quant repo treats QuantSmith: **copy, pin, verify, and report drift** — never fetch at use time. A
standard-library Python tool copies an allowlisted subset of the upstream from a local source into `vendor/agent-skills/`, writes a lock
with a hash per file, and refuses anything that is not local, not allowlisted, or not plain text. The vendored directory is itself a
valid Claude Code plugin named `agent-skills` (the name upstream commands already reference, e.g. `agent-skills:test-driven-development`),
registered through a project-local marketplace whose source is a relative path. A shell gate re-checks the tree against the lock on
every run. A usage standard decides precedence and routing, and the coding-stage agents cite the skills by path so any agent host —
not just Claude Code — can read them as plain files.

Three ways to "connect", in resolution order:

1. **Override** — `QS_AGENT_SKILLS_PATH=/path/to/local/agent-skills` (a working clone of the fork), loaded for one session with
   `claude --plugin-dir "$QS_AGENT_SKILLS_PATH"` (verified in T-001). For developing skills. Not pinned; `status` says so.
2. **Installed (user level)** — `quantsmith-agent-skills install --scope user` registers the *vendored* copy (or the override) as a
   local-directory marketplace in the user's Claude Code settings, for use outside the QuantSmith checkout.
3. **Vendored (default)** — `vendor/agent-skills/` in the repo. Works in any clone, offline, after a **one-time per-machine opt-in**
   (`quantsmith-agent-skills install --scope project`). Claude Code never activates a plugin enabled only by repo-authored settings
   (T-001), so a fresh clone cannot install third-party prompts silently.
4. **Bundled** — the same tree shipped read-only inside the `quantsmith` wheel (`quantsmith/_bundled/agent_skills/`), used by
   `install --scope user` when there is no checkout (REQ-012). A repo-local `vendor/agent-skills/` always wins over it.

## Architecture & Components

```
 local clone / mirror / tarball of the fork        (maintainer machine; only place GitHub is ever involved)
            │  quantsmith-agent-skills sync --source <path> --ref <sha>
            ▼
 config/agent_skills.json ──► sync (allowlist, safety checks, change summary)
                                  │
                                  ▼
 vendor/agent-skills/                                  vendor/agent-skills.lock.json
   .claude-plugin/plugin.json   (QuantSmith-owned overlay)   upstream, fork, commit, version,
   LICENSE                      (verbatim)                   source, synced_on, allowlist, files{path: sha256}
   README.md                    (QuantSmith-owned: provenance + credit)
   skills/<allowlisted>/…       (verbatim)
   .claude/commands/<allowlisted>.md (verbatim)
   agents/<allowlisted>.md      (verbatim)
   references/*.md              (verbatim; skills link to them)
            │
            ├──► .claude-plugin/marketplace.json  (repo root; plugin source "./vendor/agent-skills")
            │         └──► .claude/settings.json  extraKnownMarketplaces + enabledPlugins  (REQ-005)
            ├──► hooks/stages/agent-skills-check.sh  (verify vs lock; conflicts; URL sources; agent citations)
            ├──► instructions/agent_skills.md        (precedence, stage map, exclusions)
            └──► agents/*/instructions.md             (cite vendor/agent-skills/skills/<name>/SKILL.md)
```

### Components

| Component | Responsibility |
| --- | --- |
| `config/agent_skills.json` | Allowlist by group (`core`, `review`, `ship`, `personas`, `web`), enabled groups, explicit exclusions with reasons, size cap. Tracked; the single place a human changes scope. |
| `src/quantsmith/agent_skills/` (`sync.py`, `lock.py`, `cli.py`) | `sync`, `verify`, `status`, `diff`, `install` subcommands; console script `quantsmith-agent-skills`. Stdlib only. Never executes vendored content. |
| `vendor/agent-skills/` | The pinned subset plus two QuantSmith-owned files (`.claude-plugin/plugin.json`, `README.md`), marked `owned: quantsmith` in the lock and excluded from upstream hash comparison. |
| `vendor/agent-skills.lock.json` | Provenance and integrity record (REQ-002). Sorted keys, two-space indent, trailing newline (NFR-002). |
| `setup.py` bundling | Copies `vendor/agent-skills/` and the lock into `quantsmith/_bundled/agent_skills/` at build time, as it already does for analytics packs; the build fails if the copy does not match the lock. |
| `.claude-plugin/marketplace.json` (root) | Local marketplace `quantsmith-local` with one plugin `agent-skills`, source `./vendor/agent-skills`. No URL sources anywhere. |
| `.claude/settings.json` (committed) | Only `enabledPlugins: {"agent-skills@quantsmith-local": true}`; `false` is the kill switch (NFR-006). No `extraKnownMarketplaces` (see Settings). Existing SessionStart hook untouched. |
| `.claude/settings.local.json` (per machine, gitignored) | Written by the opt-in: the marketplace registration with this checkout's absolute path. Never `enabledPlugins`. |
| `hooks/stages/agent-skills-check.sh` | Gate (REQ-004, AC-004/006/007/012). Runs `python3 -m quantsmith.agent_skills verify`, so there is one implementation of the checks (hashes vs lock, frontmatter, allowlist/exclusions, URL sources, agent citations, names against `agents/agent_registry.yaml`), and prints each finding. Wired into `run-stage.sh` and CI. |
| `src/quantsmith/agent_skills/bundle.py` | Builds the wheel bundle (REQ-012). Stdlib-only with no package imports, so `setup.py` can load it by file path during the build. |
| `instructions/agent_skills.md` | Usage standard (REQ-008). |

### Default allowlist

| Group | Items | Default |
| --- | --- | --- |
| `core` | `test-driven-development`, `incremental-implementation`, `debugging-and-error-recovery`, `source-driven-development`, `doubt-driven-development`, `context-engineering`, `api-and-interface-design` | on |
| `review` | `code-review-and-quality`, `code-simplification`, `security-and-hardening`, `performance-optimization`; commands `/review`, `/code-simplify`, `/test` | on |
| `ship` | `git-workflow-and-versioning`, `ci-cd-and-automation`, `documentation-and-adrs`, `observability-and-instrumentation`, `deprecation-and-migration`, `shipping-and-launch` | on |
| `define` | `interview-me`, `idea-refine` (technique only; output goes into `specs/NNNN-*/spec.md`) | on |
| `personas` | agents `code-reviewer`, `test-engineer`, `security-auditor` (`test-engineer` ranks below `test_engineering/*`; see stage map) | on |
| `references` | `references/*.md` except `accessibility-checklist.md` (with `web`) | on |
| `web` | `frontend-ui-engineering`, `browser-testing-with-devtools`, command `/webperf`, agent `web-performance-auditor`, `accessibility-checklist.md` | off (REQ-011) |

### Exclusions (REQ-007)

| Item | Reason |
| --- | --- |
| `spec-driven-development`, `planning-and-task-breakdown` | Produce root `SPEC.md`/plan artifacts and an ID scheme that bypass `specs/NNNN-slug/` and the `spec-check` gate (P1, P2). |
| `using-agent-skills` | Meta-router that sends work to the excluded commands; QuantSmith routing is `workflow_orchestrator` + `instructions/agent_skills.md`. |
| `/spec`, `/plan`, `/ship` | Same as above. |
| `/build` | Commits after every task and can generate its own plan; QuantSmith commits only when asked and tasks come from `tasks.md`. Follow-up: a QuantSmith-owned `/qs-build` wrapper. |
| upstream `hooks/` | Session-start injects the meta-router and needs `jq`; `sdd-cache` and `simplify-ignore` hooks run shell from vendored content (NFR-003). |
| `commands/*.toml`, `evals/`, `docs/`, `scripts/` | Other hosts or upstream maintenance; not needed to use the skills. |

### Stage map (core of `instructions/agent_skills.md`)

| SDD stage | QuantSmith owner | agent-skills skill(s) | Override |
| --- | --- | --- | --- |
| Specify | `planning_requirements` | `interview-me`, `idea-refine` | Output only into `spec.md` with QuantSmith IDs. |
| Implement | `implementation` | `incremental-implementation`, `test-driven-development`, `source-driven-development`, `api-and-interface-design`, `context-engineering` | Tests must name `AC-*` IDs; no leakage rules relaxed. |
| Verify | `testing_validation`, `test_engineering/*` | `test-driven-development`, `debugging-and-error-recovery`, `doubt-driven-development`; persona `test-engineer` | Route to `test_engineering_orchestrator` first; `test-engineer` only for generic test design, and its tests must name `AC-*`. Quant validation (`backtest_review`, leakage) still required. |
| Review | `quality-guard-agent`, review path | `code-review-and-quality`, `code-simplification`, `security-and-hardening`, `performance-optimization`; personas `code-reviewer`, `security-auditor` | Findings also checked against the constitution. |
| Ship / Operate | `git_release`, `deployment_release`, `maintenance_monitoring` | `git-workflow-and-versioning`, `ci-cd-and-automation`, `documentation-and-adrs`, `observability-and-instrumentation`, `deprecation-and-migration`, `shipping-and-launch` | `instructions/git_workflow.md`, Conventional Commits, commit only when asked, **no attribution footers** (CLAUDE.md) win. |

## Interfaces & Data Contracts

**CLI** (exit `0` ok, `1` findings, `2` could not run; JSON on stdout with `--json`):

```
quantsmith-agent-skills sync   --source <dir|clone|tarball> [--ref <sha|tag>] [--dry-run] [--root .]
quantsmith-agent-skills verify                       # same checks as the gate, from Python
quantsmith-agent-skills status                       # copy in effect (override/repo/bundled), commit, matches-lock, duplicate installs, review due
quantsmith-agent-skills diff   --source <...> [--ref ...]   # change summary only
quantsmith-agent-skills install --scope user|project [--path <dir>]
```

- `--source` is rejected if it matches `^[a-z]+://` or `^[^/]+@[^:]+:` (AC-003). A clone is read with `git -C <src> archive <ref>`
  piped into a temp dir — local object store only; `git fetch` is never run.
- `--ref` is required for a clone and resolved to a full SHA; a plain directory records `commit` from `git rev-parse HEAD` if it is a
  repo, else `null` with `source_kind: "directory"` and a warning that it is unpinned.

**Lock schema** (`vendor/agent-skills.lock.json`):

```json
{
  "schema": 1,
  "upstream": "addyosmani/agent-skills",
  "fork": "thatquantguy44/agent-skills",
  "commit": "f63ec56a3cc936408d792956ae583c3c96a825bd",
  "plugin_version": "0.6.7",
  "source_kind": "git-clone",
  "synced_on": "2026-10-07",
  "groups": ["core", "define", "personas", "references", "review", "ship"],
  "excluded": ["skills/spec-driven-development", "..."],
  "files": {"LICENSE": "sha256:…", "skills/test-driven-development/SKILL.md": "sha256:…"},
  "owned": [".claude-plugin/plugin.json", "README.md"]
}
```

The source path is deliberately not stored (it is a machine-local path); `source_kind` is.

**Settings** (confirmed in T-001 on Claude Code 2.1.292; evidence in `validation.md`):

Committed `.claude/settings.json` holds only the switch:

```json
{ "enabledPlugins": { "agent-skills@quantsmith-local": true } }
```

The per-machine opt-in (`quantsmith-agent-skills install --scope project`) runs, from the repo root:

```sh
claude plugin marketplace add "$(git rev-parse --show-toplevel)" --scope local
```

That registers the marketplace and writes `.claude/settings.local.json`
(`{"extraKnownMarketplaces": {"quantsmith-local": {"source": {"source": "directory", "path": "<absolute repo path>"}}}}`).
It deliberately does **not** run `claude plugin install`: that writes `enabledPlugins: true` at local scope, which overrides a
committed `false` and would defeat the kill switch.

Rules the implementation must follow, each observed in T-001:

- Repo-declared marketplaces and plugins are not activated on their own (`Skipped auto-recording … enabled only by repo-authored
  settings`). The opt-in is required, and hand-writing `settings.local.json` is not enough: the CLI must register the marketplace.
- Sessions read a directory marketplace's plugin **live from `vendor/agent-skills/`**; the plugin cache only feeds
  `claude plugin details`. A hand edit therefore reaches sessions immediately, so the integrity gate (T-007) is the control that
  catches it.
- The cache is keyed by `version`, so sync stamps the overlay `plugin.json` version as `<upstream>+<sha7>.<tree-hash8>`. Then
  `claude plugin details` shows the pin actually in use.
- The overlay `plugin.json` must **not** declare `agents`: an explicit `.md` list validated but loaded 0 agents; a directory value
  fails validation (`must end with ".md"`); default discovery of `agents/` loads them. `commands: ["./.claude/commands"]` works.
- `claude plugin validate`, `marketplace add`, `install` and `details` all succeed with networking disabled (`unshare -n`).

**User scope (bundled or vendored copy):** `install --scope user` runs `claude plugin marketplace add <copy> --scope user` followed by
`claude plugin install agent-skills@quantsmith-local --scope user`. The bundled copy therefore ships with its own
`.claude-plugin/marketplace.json` wrapper.

**Fallback** (kept in case a future Claude Code release removes directory marketplaces): `install --scope project --mode skills`
materializes the allowlisted skills as `.claude/skills/agent-skills-<name>/SKILL.md` (gitignored, generated from the vendored copy,
verified by the same hashes).

## Deviations Recorded During the Build

| Planned | Built | Why |
| --- | --- | --- |
| `config/agent_skills.yml` | `config/agent_skills.json` | The core package is standard-library only (NFR-004); a YAML parser would add a dependency. |
| Gate hashes with `sha256sum`, parses with `sed` | Gate calls `quantsmith.agent_skills verify` | One implementation of the checks instead of two that can disagree. Same pattern as `orchestration-check.sh`. |
| `define` group vendors `idea-refine` whole | `skills/idea-refine/scripts/` excluded; the rest kept | Upstream ships an executable that creates `docs/ideas/` (NFR-003, and Specify output belongs in `specs/`). |
| Bundle = tree + lock | Bundle also carries `config/agent_skills.json` | Found while testing AC-016: with no checkout there is no config, so `status`/`install` could not run. `load_config` falls back to the bundled copy. |
| Diff on a one-skill change is "that skill and the lock" (AC-009) | Also the two generated files | The overlay `plugin.json` version and the README carry the commit. AC-009 amended. |
| `install --scope project --mode skills` fallback | Not built | T-001 confirmed the plugin route; the fallback stays a design note until a Claude Code release needs it. |

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P1/P2 Spec is truth; traceability | yes | Conflicting SDD skills excluded; stage map routes all artifacts into `specs/`. |
| P4 Correct by construction | yes | Integrity by hash; only local sources representable in the CLI; no executable content. |
| P5 Reversibility | yes | One-setting kill switch; removal is deleting three paths. |
| P6 Observability | yes | `status` and the gate state which copy, which commit, and every divergence. |
| P8 No silent trade-offs | yes | Exclusions and overrides are listed with reasons; re-enabling is reported. |
| P9 Security & data | yes | Third-party prompts treated as supply chain: allowlist, size/type limits, reviewed sync PRs, no hooks. |
| P10 Honest reporting | yes | An override or unpinned directory source is reported as unpinned, never as matching. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `vendor/agent-skills/`, initial sync at `f63ec56` | T-003, T-006 |
| REQ-002 | `lock.py`, lock schema | T-003 |
| REQ-003 | `sync.py` (local-only sources, change summary) | T-003, T-004 |
| REQ-004 | `agent-skills-check.sh`, `verify` | T-007 |
| REQ-005 | root marketplace, `.claude/settings.json`, overlay `plugin.json` | T-001, T-008 |
| REQ-006 | `QS_AGENT_SKILLS_PATH`, `status`, `install --scope user` | T-005 |
| REQ-007 | `config/agent_skills.json` exclusions; gate conflict check | T-002, T-007 |
| REQ-008 | `instructions/agent_skills.md` | T-009 |
| REQ-009 | agent `instructions.md` citations; `agents/README.md` | T-010 |
| REQ-010 | `docs/adoption_guide.md`; drift surface | T-011 |
| REQ-011 | `web` group | T-002, T-004 |
| REQ-012 | `setup.py` bundling; resolution order in `status`/`install` | T-005, T-014 |
| REQ-013 | `personas` group; stage-map routing | T-002, T-009 |
| REQ-014 | review-due check in `status`; handoff record | T-015 |
| NFR-001 | no-network test; URL rejection | T-004, T-012 |
| NFR-002 | deterministic writer; idempotence test | T-003, T-012 |
| NFR-003 | sync safety checks | T-004 |
| NFR-004 | stdlib + POSIX sh only | T-003, T-007 |
| NFR-005 | size check in gate | T-007 |
| NFR-006 | kill switch; removal note | T-008, T-009 |
| NFR-007 | verbatim LICENSE; README credit | T-006 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| How to bring upstream in | Copy subset + hash lock | Git submodule | Submodule needs the remote at clone time (fails offline and in consumers without GitHub); consumers copying files lose it. |
| | | Git subtree | Imports upstream history into QuantSmith; noisy merges; still unverifiable after a hand edit; consumer copies lose subtree metadata. |
| | | GitHub marketplace install | Network at install, unpinned, upstream manifest points at `addyosmani` not the fork. |
| Scope | Allowlist | Vendor everything | Conflicting skills/hooks would be loaded; context bloat (RISK-001, RISK-006). |
| Loading | Local plugin (namespaced) | Copy skills into `.claude/skills/` | Namespacing avoids collisions and upstream commands already call `agent-skills:<skill>`; kept as fallback. |
| Edits | Fix in fork, re-sync | Patch vendored files | Patches are lost on next sync and invisible without the hash check. |
| Tooling | Python stdlib CLI + sh gate | Shell-only sync | Tar/archive handling, JSON lock and per-file hashing are clearer and testable in Python; the gate stays sh like the others. |

## Validation Strategy

- Unit tests in `tests/test_agent_skills.py` build a fake upstream repo in a temp dir (`git init`, two commits, a symlink, an
  executable, an oversized file, a conflicting skill) and name the `AC-*` they prove: sync/idempotence (AC-002, AC-009), URL rejection
  (AC-003), safety refusals (AC-005), status/override (AC-008), web group (AC-014), license and size (AC-015).
- Network-off proof (NFR-001, AC-001 part): run `sync`/`verify`/`status` with `socket.socket` patched to raise.
- Gate tests drive `agent-skills-check.sh` against tampered copies (AC-004, AC-006, AC-007, AC-012) and a consumer fixture with
  `QF_UPSTREAM_SURFACES` (AC-013).
- AC-001 and AC-011 are checked manually in a Claude Code session with networking off; evidence recorded in `validation.md`
  (skill listing before/after toggling the setting).
- `QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh spec` and the full test suite pass.

## Rollout, Observability & Rollback

- **Rollout:** one PR with tooling, config, gate and docs; a second PR with the first vendored sync, so the vendored diff is reviewed on
  its own. Gate advisory first; CI enforcing once the second PR lands.
- **Observability:** `status` output and gate findings; lock `synced_on` and `commit` shown in `docs/handoff.md`.
- **Refresh runbook:** update local clone of the fork → `diff` → review → `sync` → PR containing only `vendor/` and the lock.
- **Quarterly review:** when `status` says the review is due (lock older than 92 days), run the runbook; if nothing is worth taking,
  record "reviewed, no change" with the date in `docs/handoff.md` (REQ-014).
- **Rollback:** set `enabledPlugins` entry to `false` (instant); revert the sync PR to return to the previous pin; full removal per
  NFR-006.

## Open Questions

- Resolved by T-001: settings keys, opt-in, live loading, kill-switch precedence (see Settings and `validation.md`).
- Not yet verified: the interactive (TTY) session start, which may offer to install the repo-declared plugin; macOS and Windows path
  handling for the absolute local registration. Both are checked manually under AC-001.
