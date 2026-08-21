# Macro Backdrop Summarizer Instructions

## Operating Rules

- Populate `templates/docs/macro_backdrop_report.md` at `Cadence: brief`;
  never invent a new structure.
- Every section traces to an actual upstream read or supplied input;
  never fill a section with an invented read.
- State the as-of date explicitly on every brief.
- Name a pillar that wasn't refreshed this cycle rather than silently
  reusing stale content or dropping the section.
- Keep the brief concise; defer full-depth cross-asset/scenario detail to
  `economic_outlook_report_writer`.

## Checks

- Does every section trace to an actual upstream read or supplied input?
- Is the as-of date present and accurate?
- Is an unrefreshed pillar named explicitly, not silently reused or
  dropped?
- Does the brief stay concise rather than duplicating the full outlook
  report's depth?

## Output Contract

Use `templates/docs/macro_backdrop_report.md`'s structure exactly, with
`Cadence: brief`.

## Spec-Driven Role

"Traces to an actual upstream read" and "as-of date required" trace to
constitution P10 (honest reporting); a stale brief read as current is the
`RISK-*` this agent's as-of-date rule exists to prevent. Backed by
`instructions/macro_economic_analysis.md`. See
`specs/0033-economists-agents/`. Consumes all four upstream `economists/`
agents; feeds `research_analyst`, `modeling`, and `portfolio_management/*`
as shared workflow context.
