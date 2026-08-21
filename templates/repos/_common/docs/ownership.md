# Ownership and support

The question this file exists to answer: **a gate failed at 6pm and the person
who hit it does not know why — who do they ask, and what do they try first?**

Without an answer, the honest outcome is `--no-verify`, and a bypassed gate is
worse than no gate because everyone still believes it ran.

## Owners

| Surface | Owner | Backup | Notes |
| --- | --- | --- | --- |
| `hooks/` (the gates) | `<@handle>` | `<@handle>` | Tuning a pattern is expected; record deliberate divergence below |
| `specs/` | `<@handle>` | `<@handle>` | Approves AC evidence |
| `src/` | `<@handle>` | `<@handle>` | |
| `pipelines/` or `models/` | `<@handle>` | `<@handle>` | Whoever answers for the numbers |
| `.github/` (CI) | `<@handle>` | `<@handle>` | |
| Upstream pin | `<@handle>` | `<@handle>` | Decides when to take a new upstream version |

Keep this in step with `.github/CODEOWNERS`. CODEOWNERS routes review; this
table says who answers a question, which is a different job.

## Escalation

1. **Check the runbook** — `docs/gate_runbook.md` covers every gate, what it
   actually checks, and the usual cause.
2. **Ask the surface owner** above.
3. **Still stuck and the change is urgent?** `--no-verify` is permitted, on two
   conditions: you say so in the PR description, and you open an issue the same
   day. A silent bypass is the thing this whole system is built to prevent.

## Deliberate divergence from upstream

Gates are copied and tuned; that is the adoption model, not a mistake. The
`upstream-drift` gate will report anything that differs from the pinned ref, so
record intentional changes here and the report becomes readable instead of noise.

| File | Diverged because | Decided by | Date |
| --- | --- | --- | --- |

## What this repo does NOT own

<!-- Naming this prevents the most common support misroute: someone asking the
     wrong team because the boundary was never written down. -->
