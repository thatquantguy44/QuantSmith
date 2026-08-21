# Working agreement

Not setup. This is what you do when work arrives.

```
New work
  |
  +-- Trivial (typo, comment, one-line fix)?
  |     -> commit it. Conventional Commit. Done.
  |
  +-- Standard (a feature, a fix with design choices)?
  |     -> ./scripts/new-spec.sh <slug>
  |        fill spec.md (REQ/NFR/AC/RISK) + tasks.md (T-*)
  |        add the roadmap entry  <- the commit is blocked without it
  |        implement -> every AC gets passing evidence
  |
  +-- Significant or risky (new dependency, data contract, irreversible)?
        -> the same, plus plan.md: architecture, tradeoffs, what you rejected
```

Always, before opening a PR:

```sh
./scripts/check.sh
```

## The two questions people get stuck on

**"Does this need a spec?"** If you cannot state the acceptance criterion in
one sentence, it needs a spec. If you can, and it is reversible in one commit,
it does not.

**"Who signs off on AC evidence?"** Whoever owns the path in `CODEOWNERS`.
Evidence means a passing test or pasted output — not an assertion that it
works.

## What the gates will not do for you

They catch silence and drift: a missing entry, a stale count, an unpinned
dependency, an AI-authored commit. They cannot tell whether your prose is
true or your model is right. That is review, and review is a person.
