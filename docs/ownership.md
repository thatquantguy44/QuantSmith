# Ownership and support

The question this file exists to answer: **a gate failed at 6pm and the person
who hit it does not know why — who do they ask, and what do they try first?**

Without an answer the honest outcome is `--no-verify`, and a bypassed gate is
worse than no gate, because everyone still believes it ran.

## Owners

| Surface | Owner | Backup | Notes |
| --- | --- | --- | --- |
| `hooks/` (29+ gates) | @joshualutkemuller | *unassigned* | Tuning a pattern is expected; record deliberate divergence below |
| `specs/` | @joshualutkemuller | *unassigned* | Approves `AC-*` evidence |
| `src/quantsmith/` | @joshualutkemuller | *unassigned* | Runtimes and adapters |
| `instructions/` | @joshualutkemuller | *unassigned* | The constitution and standards |
| `templates/repos/` | @joshualutkemuller | *unassigned* | Repo shapes and the scaffolder |
| `.github/` (CI) | @joshualutkemuller | *unassigned* | |

**Single-maintainer risk, stated rather than hidden:** every surface has the
same owner and no backup. That is survivable for an SDK with one consumer and
is the first thing that breaks at firm scale — a gate failing while the only
person who understands it is unavailable. Naming a backup per surface is the
cheapest mitigation and is not yet done.

## Escalation

1. **`docs/gate_runbook.md`** — every gate, what it checks, and the usual cause.
2. **The surface owner** above.
3. **Urgent and still stuck?** `--no-verify` is permitted on two conditions:
   say so in the PR description, and open an issue the same day. A silent bypass
   is exactly what this system exists to prevent.

## Deliberate divergence from upstream

Not applicable here — this repository *is* the upstream. Consuming repos record
their intentional divergences in their own copy of this file, and the
`upstream-drift` gate reports anything that differs from their pinned ref.

## What this repository does NOT own

- **An adopter's tuned gate patterns.** Copied gates are theirs; we ship the
  default, they own the fit.
- **Securities-financing optimization logic** — routed to an adopter's own
  models via `agents/optimization/model_plugin_registration/` (spec `0026`).
- **Anyone's data.** No dataset, credential, or company specific ever lands
  here; the `secret-scan`, `role-context`, and `model-plugin` gates enforce it.
