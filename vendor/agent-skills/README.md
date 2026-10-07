# Vendored agent-skills (generated, do not edit)

This directory is a pinned, allowlisted subset of [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), MIT-licensed,
copyright Addy Osmani (see `LICENSE`). QuantSmith takes it from its fork `thatquantguy44/agent-skills`.

- Commit: `f63ec56a3cc936408d792956ae583c3c96a825bd`
- Upstream plugin version: `0.6.7`
- Groups: core, define, personas, references, review, ship
- Lock: `vendor/agent-skills.lock.json`

Every file except this README and `.claude-plugin/plugin.json` is byte-identical to upstream, and its SHA-256 is in the
lock. Do not edit these files. Fix problems in the fork, then re-sync:

    quantsmith-agent-skills diff --source <local clone> --ref <sha>
    quantsmith-agent-skills sync --source <local clone> --ref <sha>

Usage, precedence and exclusions: `instructions/agent_skills.md`. Spec: `specs/0100-agent-skills-upstream-integration/`.
