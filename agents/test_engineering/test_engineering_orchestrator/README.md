# Test Engineering Orchestrator

## Purpose

Routes a testing request to the right language specialist(s) — 
`python_test_engineer`, `cpp_test_fuzz_engineer`, `javascript_test_engineer`,
`typescript_test_engineer` — by detecting the stack involved, and
consolidates their output into one handoff to `testing_validation` and/or
`quality-guard-agent`. Use it when the language isn't obvious, a repo spans
more than one language, or you just want one entry point.

## Use When

- The request doesn't name a language, or the codebase mixes several.
- Multiple language agents' output needs consolidating into one summary.
- A requester wants a single entry point rather than picking an agent
  themselves.

## Inputs

- The code, file paths, or repo section that needs tests.
- Any existing test tooling already in use (config files, CI scripts,
  `package.json`/`pyproject.toml`/`CMakeLists.txt`, etc.).
- The downstream need: AC coverage (→ `testing_validation`), a release
  decision (→ `quality-guard-agent`), or both.

## Outputs

- The language(s) detected and which specialist(s) were routed to.
- Each specialist's output, consolidated (not merely concatenated) with
  overlaps and gaps between languages called out.
- A single handoff line naming `testing_validation` and/or
  `quality-guard-agent`.

## Example Requests

- "I have a Python backend and a TypeScript frontend — get both tested."
- "Not sure what language this is or what tests it needs — take a look."
- "Combine the pytest and Vitest results into one summary for review."

## Required Review Themes

- Correct stack detection before routing — never guess a language from a
  file extension alone when the content contradicts it (e.g. a `.js` file
  that is actually generated output).
- No specialist's finding dropped or contradicted in the consolidated
  summary.
- Exactly one clear downstream handoff, not a decision made by the
  orchestrator itself.
