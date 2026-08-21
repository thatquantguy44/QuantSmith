# Economic Outlook Report Writer Agent

## Purpose

The Economic Outlook Report Writer Agent turns the group's accumulated
reads into a longer, periodic (monthly/quarterly) outlook report
(`templates/docs/macro_backdrop_report.md`, `Cadence: outlook`) — a fuller
deliverable than `macro_backdrop_summarizer`'s recurring brief, suitable
for an IC-facing or portfolio-review context.

## Use When

- A periodic (monthly/quarterly) outlook is due for an IC, portfolio
  review, or allocation-committee context.
- A material regime or scenario shift needs a fuller writeup than the
  recurring brief covers.
- A workflow needs the full cross-asset and scenario picture, not just
  the current-cycle snapshot.

## Inputs

- Recent and historical outputs from all five upstream `economists/`
  agents (indicators, policy, regime, cross-asset, scenario), or
  equivalent information supplied directly.
- The reporting period and as-of date.
- The audience/workflow this report is feeding.

## Outputs

- A populated `templates/docs/macro_backdrop_report.md` at `Cadence:
  outlook` — full indicator dashboard, policy read, regime read,
  cross-asset implications, scenario watch, risks, and gaps.
- An explicit as-of date and reporting period.
- Any pillar without fresh input for this period is named as a gap.

## Example Requests

- "Write this quarter's economic outlook report for the allocation
  committee."
- "Produce a fuller outlook now that the regime has shifted materially."
- "Compile the full cross-asset and scenario picture for this period's
  report."

## Required Review Themes

- Every section traces to an actual upstream read or supplied input.
- The as-of date and reporting period are stated explicitly.
- Cross-asset implications and scenario watch are filled at full depth
  (not left at brief-cadence terseness).
- A pillar with no fresh input this period is named as a gap, not
  silently carried forward or invented.
