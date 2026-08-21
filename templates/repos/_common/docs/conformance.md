# Conformance

What "this repo follows the method" actually means here. Declared in
`quantsmith.conf` as `QF_CONFORMANCE_LEVEL`.

| Level | Means | Requires |
| --- | --- | --- |
| **L1 — Guardrails** | Won't leak secrets or ship broken docs | `secret-scan`, `docs-link`, `CLAUDE.md`, the constitution |
| **L2 — Traceable** | Every non-trivial change traces to a spec | + `specs/`, `spec` gate blocking, Conventional Commits, `docs/roadmap.md` |
| **L3 — Governed** | The full method | + catalogs, `doc-counts`, `handoff-sync`, agent contracts, model/dataset cards |

Levels are cumulative. Declare the level you actually meet, not the one you
intend to — the point is that another repo can read this and know what to
expect.

**This repo is: L<N>** — <one line on why, and what would move it up.>
