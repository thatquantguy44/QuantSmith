# Contributing

1. `./scripts/setup-hooks.sh` once after cloning.
2. Branch from `main`. Never push to `main` directly.
3. Read [docs/working_agreement.md](docs/working_agreement.md) — it decides
   whether your change needs a spec.
4. `./scripts/check.sh` before opening a PR. Paste the output into the PR.

## Commits

Conventional Commits, enforced by the `commit-msg` hook:

```
type(scope): description
```

Commits are authored by the human accountable for them. The `agent-attribution`
gate rejects AI identities and AI co-author trailers — AI-assisted work is fine,
AI-attributed work is not.

## What will block your PR

| Gate | Why |
| --- | --- |
| `secret-scan` | A credential in history cannot be un-leaked |
| `spec` | Untraceable work cannot be reviewed or reverted with confidence |
| `handoff-sync` | A spec nobody can find on the roadmap is a spec nobody maintains |

The full list is in `quantsmith.conf`.
