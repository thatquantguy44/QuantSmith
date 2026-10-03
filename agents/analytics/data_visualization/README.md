# Data Visualization Agent

## Purpose

The Data Visualization Agent owns single-chart encoding: chart-type choice, axis and
series encoding, color, sorting, units/labels, and accessibility for one chart at a
time. It is the narrow counterpart to `dashboard_design/`, split out because
`specs/0080-nl-analytics-insights/` needs a single-chart form rule that runs
deterministically per natural-language answer, not a multi-panel layout. It never
redefines a metric, computes a number, or lays out a dashboard — it takes a metric
result (already computed against `0008`) and turns it into one honest chart.

Runtime: `src/quantsmith/nl_analytics/chart.py` (`choose_chart`, `to_vega_lite`,
`to_markdown_table`, `to_panel`) implements this agent's rules as a deterministic
form rule (spec `0080`, REQ-006/AC-007/AC-008). `to_panel` hands a chart to
`dashboard_design`'s panel model (`0015`) when it belongs inside a multi-panel
dashboard rather than standing alone.

## Use When

- One metric result (a computed value, a small group-by, or a short time series)
  needs a single chart, independent of any surrounding dashboard.
- A natural-language analytics answer (`nl_analytics`) needs its result rendered.
- An existing single chart needs a review for chart-type fit, misleading encoding,
  or accessibility.

## Inputs

- A computed metric result: value(s), declared dimensions, and/or a per-period
  series — already governed by `0008`; never raw rows or a SQL query.
- The question or intent behind the chart (what it must answer).
- Units, and whether a comparison (delta, prior-period, or a second metric for a
  scatter) is present.

## Outputs

- A chart-type decision (kpi / bar / line / scatter / table) with the rule that
  produced it.
- Encodings: axes, series, sort order, zero-baseline decision, units/labels.
- A finding-first title, a footnote for anything caveated, and alt text.
- A minimal Vega-Lite spec and a Markdown table rendering of the same chart.

## Example Requests

- "What chart should this metric result use?"
- "Render this natural-language answer's result as a chart."
- "Review this single chart for a misleading encoding or an accessibility gap."

## Required Review Themes

- Chart-type follows a declared, deterministic form rule — not a stylistic pick.
- No misleading encoding: truncated axes that distort, dual axes implying false
  correlation, rainbow scales, unlabeled units.
- Title states the finding, not just the metric name; footnote and alt text present
  when either is warranted.
- Accessibility: sufficient contrast, labels, and encodings that do not rely on
  color alone.
- The chart references a governed metric result; it never invents or recomputes one.
