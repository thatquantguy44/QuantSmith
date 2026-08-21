# Data Provenance Instructions

## Purpose

Use this instruction set whenever an agent produces content backed by data or
visuals — a report, a chart, a demo, a dashboard, a drafted narrative. The rule
is simple and non-negotiable: **every data point and every visual must be
traceable to its source.** Actual, sourced data is used whenever it's
available; synthetic data is a documented last resort, never a silent
default, and every place it's used gets disclosed in a companion report — not
buried in a caveat sentence.

## The Priority Stack

In order, always prefer the option higher on this list:

1. **Actual, sourced data** — cited at the point of use (system/dataset name,
   as-of date or vintage). This is the default and the expectation.
2. **A clearly labeled subset or sample of actual data** — still real, cited
   the same way, with the sampling method stated.
3. **Synthetic or simulated data** — only when (1) and (2) are genuinely
   unavailable (no access, not yet collected, restricted). Every use is
   disclosed (see below); it is never chosen for convenience.

## Required Output

- A source citation at the point of use for every data-backed claim, table,
  or visual — real data cited by system/dataset and as-of date; synthetic
  data cited as synthetic, with a pointer to its disclosure entry.
- When any synthetic data is used anywhere in the artifact, a companion
  **Synthetic Data Disclosure** report (`templates/docs/synthetic_data_disclosure.md`)
  listing every occurrence — not a summary, every row.
- The disclosure report ships alongside the artifact, not as an afterthought
  requested later.

## Standards

- **Real data first, always.** Reach for actual data before synthetic;
  synthetic is justified by genuine unavailability, stated explicitly, not
  assumed as a default for speed or convenience.
- **Visuals are not exempt.** A chart, a table, a dashboard tile carries the
  same sourcing obligation as a sentence of prose — a visual with no source
  is exactly as unacceptable as an uncited claim.
- **Disclosure is complete, not representative.** "Some series in this chart
  are synthetic" is not a disclosure; naming which series, and why, is.
- **No silent blending.** Real and synthetic data in the same artifact are
  visually and textually distinguishable (labeled series, a footnote per
  table, a marked column) — a reader should never have to guess which is
  which.
- **The disclosure travels with the artifact.** If the artifact changes
  (real data replaces a synthetic series), the disclosure report is updated
  in the same change, not left stale.

## Checks

- Does every data point, table, and visual in the artifact carry a source
  citation at the point of use?
- Was actual data considered and ruled out (not just skipped) before any
  synthetic data was used?
- Does a Synthetic Data Disclosure report exist for the artifact whenever
  synthetic data appears anywhere in it?
- Does the disclosure list every occurrence, not a representative sample?
- Are real and synthetic data visually/textually distinguishable within the
  artifact itself?

## Common Failure Modes

- Generating a demo or report with synthetic data by default because it's
  faster, without checking whether real data was actually available.
- A visual (chart, dashboard tile) with no source note, real or synthetic.
- A disclosure that says "some data is illustrative" instead of naming every
  location.
- Real and synthetic series plotted identically, indistinguishable to the
  reader.
- A disclosure report written once and never updated as the artifact
  changes.

## Spec-Driven Alignment

This standard backs any agent that produces data- or visual-backed content,
starting with `agents/role_operations/` (spec
`0025-data-provenance-guardrail`) and extending to `agents/analytics/`
(`dashboard_design`, `data_storytelling`) and any future dashboard/reporting
runtime. "Every data point sourced" and "synthetic data disclosed
completely" become testable `AC-*`/`NFR-*`; an undisclosed synthetic use is a
`RISK-*`. Backed operationally by the `data-provenance` gate
(`hooks/stages/data-provenance-check.sh`), which validates a disclosure
report's required fields when one exists and advisorially flags likely
synthetic-data language in generated artifacts with no matching disclosure.
See `instructions/point_in_time.md` (a related but distinct concern: point-in-time
correctness of real data) and `instructions/engineering_principles.md` P10
(honest reporting).
