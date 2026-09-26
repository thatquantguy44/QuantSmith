# Data Visualization Instructions

## Operating Rules

- Choose the chart type via a declared, deterministic form rule (spec `0080`'s form
  rule: `compare` given -> scatter; two declared dimensions -> table; one dimension
  -> bar sorted descending; a multi-period series -> line; else -> KPI). State the
  rule that produced the choice.
- Never redefine a metric or compute a new number; the metric result is given,
  already governed by `0008` and `nl_analytics/execute.py`.
- Reject misleading encodings: a truncated axis that distorts the comparison, a dual
  axis implying false correlation, a rainbow color scale, an unlabeled unit.
- Write a finding-first title (states what the chart shows, not just the metric
  name); add a footnote for anything caveated (masked dimension, restricted data,
  synthetic/illustrative values) and alt text describing the chart's content.
- Design for accessibility: sufficient contrast, labels, and encodings that do not
  rely on color alone.
- If governed data is unavailable and synthetic/illustrative data is used instead,
  mark it visibly and disclose it per `instructions/data_provenance.md` — never
  render it identically to a governed chart.
- Produce one chart's spec; leave multi-panel layout, drill paths, and cross-chart
  hierarchy to `dashboard_design`.

## Checks

- Was the chart-type choice produced by the declared form rule, not a stylistic
  pick?
- Does the chart avoid every listed misleading-encoding pattern?
- Does the title state the finding, and are footnote/alt text present when
  warranted?
- Are accessibility requirements (contrast, labels, non-color encodings) met?
- Does every value trace to a governed metric result, with no invented number?

## Consumes / Hands Off

- **Consumes:** a computed metric result (value, dimensions, and/or per-period
  series) from `metrics_semantic_layer` (`0008`) or `nl_analytics/execute.py`
  (`0080`); the question or intent behind the chart.
- **Hands off to:** `dashboard_design` when the chart belongs in a multi-panel
  dashboard; `metrics_semantic_layer` when a metric definition needs clarifying
  before a chart can be chosen.
- Does **not** reimplement metric computation, SQL access (`sql-integration-agent`),
  or dashboard layout.

## Output Contract

Use clear Markdown. State the chart-type decision and rule first, then encodings
(axes, series, sort, zero-baseline, units/labels), then the title/footnote/alt text,
then a minimal Vega-Lite spec and/or Markdown table.

## Spec-Driven Role

The natural-language answer or dashboard request becomes `REQ-*`; the deterministic
form rule, honest encodings, and accessibility become testable `AC-*`; misleading
encodings and metric redefinition become `RISK-*`. The spec is
`specs/0080-nl-analytics-insights/` (REQ-006/AC-007/AC-008), which this agent's rules
promote from the `dataviz` skill and `instructions/data_storytelling.md`; the runtime
is `src/quantsmith/nl_analytics/chart.py`. Consumes `0008`/`nl_analytics/execute.py`;
hands off to `dashboard_design`.
