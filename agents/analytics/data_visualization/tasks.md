# Data Visualization Tasks

## Choose A Chart For A Metric Result

Input: a computed metric result (value, declared dimensions, and/or a per-period
series) and the question or intent behind it.

Output: a chart-type decision and the form rule that produced it, encodings
(axes, series, sort, zero-baseline, units/labels), a finding-first title, footnote
and alt text as warranted, and a minimal Vega-Lite spec and/or Markdown table.

## Review An Existing Single Chart

Input: a chart's type, encodings, and the metric result it renders.

Output: a review flagging any misleading encoding, chart-type mismatch, or
accessibility gap, with concrete fixes.

## Hand A Chart Into A Dashboard

Input: a chart spec that belongs inside a larger, multi-panel dashboard.

Output: the chart promoted to a `0015` panel and handed to `dashboard_design` for
layout, hierarchy, and drill paths — this agent does not build the layout itself.

## Disclose A Synthetic-Data Chart

Input: a chart request where governed data is unavailable.

Output: a chart built from synthetic/illustrative data, visibly marked as such and
disclosed per `instructions/data_provenance.md`, never rendered identically to a
governed chart.
