# CLAUDE.md

Guidance for any agent (including Claude Code) working in this repository.

## What this repo is

<!-- One paragraph. What it does, who depends on it, what it is NOT. -->

## Operating model: Spec-Driven Development

Work follows `Specify -> Plan -> Tasks -> Implement -> Verify -> Operate`. The
**spec is the source of truth**; code, tests, and releases trace back to it.

Before non-trivial work:

1. Read `instructions/engineering_principles.md` (the constitution).
2. Read `instructions/spec_driven_development.md` (the flow and ID scheme).
3. Create `specs/NNNN-slug/` from `templates/spec/` and assign IDs
   (`REQ-*`, `NFR-*`, `AC-*`, `RISK-*`, `T-*`).

Use judgement on depth: trivial changes need no spec; standard changes need
`spec.md` + `tasks.md`; significant or risky changes need all three documents.

## Quality gates

```sh
sh hooks/stages/run-stage.sh                       # all gates, advisory
QF_STAGE_ENFORCE=1 sh hooks/stages/run-stage.sh    # blocking, as CI runs it
```

Which gates block is declared in `quantsmith.conf`. Advisory by default;
`QF_STAGE_ENFORCE=1` makes findings blocking.

## Conventions

- Conventional Commits, enforced by the `commit-msg` hook.
- Run `./scripts/setup-hooks.sh` once after cloning.
- Commits are authored by the human accountable for them; the
  `agent-attribution` gate rejects AI identities and co-author trailers.
- Do all work on a feature branch; never push to `main` directly.
- Match the surrounding style of whatever file you edit.

## Key pointers

- `docs/roadmap.md` — where this repo is going and what stands where.
- `docs/conformance.md` — which parts of the method this repo has adopted.
- `specs/README.md` — the spec index.
