# Role Operations Instructions

## Purpose

Use this instruction set for the `agents/role_operations/` group: agents that
reclaim a quant/data-science lead's time from recurring operational toil
(meeting follow-ups, status updates, prototype scaffolding, first-pass research
scans) so more of it goes to model scoping and research. The group is
deliberately **configurable and generic** — it must work for any platform, any
firm, any data domain — and deliberately **carries no company-specific or
personal data of its own**. Real specifics live only in a local,
gitignored `role_context.yml`; this repository ships only the shape of that
file (`templates/role_operations/role_context.yml`), never a filled-in one.

## Required Inputs

- The task-specific input for the agent (meeting notes, a hypothesis, a new
  prototype's brief, recent activity to summarize) — supplied at the point of
  use, not stored.
- Optionally, `role_context.yml` (local, gitignored) for platform/domain
  tailoring: asset classes in scope, governance cadence, stakeholder personas,
  communication tone. Agents must work sensibly without it.

## Expected Output

- A **draft**, never a final artifact: a follow-up email draft, a status-update
  draft, a scaffolded repo skeleton, a research-plan draft.
- No fabricated specifics — a name, a number, or a decision not present in the
  input is never invented to fill a gap.
- Nothing written back into a git-tracked file that contains real platform,
  client, team-member, or account detail.

## Standards

- **Configurable, not hardcoded.** An agent's platform/domain awareness comes
  from `role_context.yml` (local) or from what the user supplies in the
  moment — never from an assumption baked into the prompt about a specific
  firm, platform, or team.
- **No company-specific or personal data in this repository, ever.** Not in
  the template, not in an example, not in a test fixture. Real values exist
  only in the adopter's local, gitignored `role_context.yml` or in the
  ephemeral input/output of a single session.
- **Category over name.** Where a committed example needs a data source,
  system, or reviewer, describe it by category ("position snapshot, daily
  refresh") not by real name.
- **Agents draft, the human decides.** Every output in this group is a first
  pass for review — a follow-up email, a status update, a scaffold — not
  something sent, filed, or committed on the agent's authority.
- **Degrade gracefully.** Every agent in this group must produce a sensible,
  generic result when `role_context.yml` is absent; configuration sharpens
  the output, it does not gate it.

## Checks

- Does the output avoid inventing any name, number, or decision not present in
  the input?
- Is any platform/domain tailoring sourced from `role_context.yml` or the
  live input, never hardcoded?
- Would the output be safe to paste into this repository as-is (no real
  platform name, client name, team-member name, account, or PII)?
- Is the output clearly a draft for review, not something the agent would send
  or file itself?

## Common Failure Modes

- An agent prompt or example that names a real firm, platform, or product
  because it was convenient, not because it was a placeholder.
- A filled-in `role_context.yml` accidentally committed (`git add -f`,
  `.gitignore` bypassed) — the `role-context` gate exists specifically to
  catch this.
- An agent inventing a plausible-sounding number or decision to complete a
  draft instead of leaving a gap marked for the human to fill.
- Treating an agent's draft as final and sending/filing it without review.

## Spec-Driven Alignment

This standard backs `agents/role_operations/` (spec
`0024-role-operations-agents`). "Never commits real specifics" and "works
generically without configuration" become testable `NFR-*`/`AC-*`; a
committed or staged `role_context.yml` is a `RISK-*` caught by the
`role-context` gate. See `instructions/engineering_principles.md` (P9,
security and data handling) and `instructions/documentation.md`. The group
composes with, but does not replace, `research_analyst` (fuller research
planning), `implementation` (production-grade scaffolding), and
`git_release` (final commit hygiene).
