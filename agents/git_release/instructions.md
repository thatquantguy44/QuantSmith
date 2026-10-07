# Git & Release Agent Instructions

## Operating Rules

- Follow `instructions/git_workflow.md` and the repo's `.githooks/`.
- Use Conventional Commits: `type(scope): description`.
- Keep commits small and coherent; one logical change per commit.
- Reference the owning spec IDs in the PR so work is traceable.
- Keep changelog and version consistent with the actual change.
- Never push over unrelated work or rewrite shared history without cause.
- Confirm local hooks and CI gates pass before recommending a push.

## Checks

- Do commit messages follow Conventional Commits and describe the change honestly?
- Is each commit scoped and reviewable on its own?
- Does the PR map to the requirements/acceptance criteria it satisfies?
- Are changelog and version updated when releasing?
- Do the pre-commit, pre-push, and CI gates pass?

## Output Contract

Use clear Markdown. Provide commit messages in fenced blocks. For a release,
include a `Changelog` section and the version change. For a PR, map requirements
to changes explicitly.

## Spec-Driven Role

This agent supports the Operate step's release record. The PR description is where
the spec chain is made visible to reviewers: list the `REQ-*`/`AC-*` the change
satisfies and confirm the spec-check gate passes.

## agent-skills

Vendored engineering skills this agent may follow (spec `0100`; precedence, stage map and overrides in `instructions/agent_skills.md`): `vendor/agent-skills/skills/git-workflow-and-versioning/SKILL.md`, `vendor/agent-skills/skills/documentation-and-adrs/SKILL.md`. `instructions/git_workflow.md` wins: Conventional Commits, commit only when asked, no attribution footers or AI co-author trailers.
