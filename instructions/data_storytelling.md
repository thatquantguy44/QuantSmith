# Data Storytelling & Dashboard Standard

How to communicate governed analysis — as narrative and as dashboards — without
overclaiming. This is the standard behind the `analytics/data_storytelling` and
`analytics/dashboard_design` agents (`specs/0014-data-analyst-storytelling/`), and it
applies to the `reporting-agent` and the tool-specific dashboard agents too.

## Why This Standard

Trustworthy numbers can still mislead if they are framed carelessly: a headline that
overclaims, a chart with a distorting axis, a metric described differently from its
definition, an A/B "win" that was never significant. This standard keeps
communication tied to the governed evidence.

## The Communication Contract

1. **Numbers come from the governed source.** Every figure traces to the analytics
   `Report` (`0010`) or a governed metric definition (`0008`); nothing is recomputed
   or invented in the narrative or dashboard. If a governed source is unavailable and
   synthetic/illustrative data is used instead, that use is disclosed per
   `instructions/data_provenance.md` — never blended into a chart indistinguishably
   from governed data.
2. **Describe metrics as defined.** Use the metric's canonical definition and grain;
   do not silently redefine it.
3. **Respect experiment verdicts.** Communicate an experiment (`0009`) with its
   verdict and caveats — inconclusive or underpowered is never a "win".
4. **No claim beyond the evidence.** The recommended action follows from the data,
   with its risks stated; correlation is not called causation.
5. **Lead with one key message.** Structure a story situation → insight → action;
   structure a dashboard so the key message reads first.
6. **Honest charts.** Choose chart types that fit the question (per the `dataviz`
   skill); avoid distorting truncation, false dual-axis correlation, and rainbow
   scales.
7. **Accessible by default.** Sufficient contrast, labels, and encodings that do not
   rely on color alone.
8. **Provenance travels.** Source, period, and definitions accompany the narrative and
   the dashboard spec.
9. **Communicate, don't rebuild.** Storytelling and design compose existing outputs
   and hand off to `reporting-agent` and the tool-specific dashboard agents; they do
   not reimplement metrics, reporting, or tool payloads.

## Checklist

- [ ] Every number traces to a governed `Report`/definition.
- [ ] Metrics described per their definitions; experiments per their verdicts.
- [ ] One clear key message; a defensible, risk-stated action.
- [ ] Chart types fit; no misleading encodings.
- [ ] Accessibility (contrast, labels, non-color encodings) met.
- [ ] Provenance carried with the output.
- [ ] Rendering handed to the reporting / tool-specific agents.

## Roles & Handoffs

- `analytics/data_storytelling` — the narrative (situation → insight → action).
- `analytics/dashboard_design` — the tool-agnostic dashboard spec.
- Renderers: `reporting-agent`, `tableau-dashboard-agent`,
  `powerbi-dashboard-agent`, `tooling/tableau`, `tooling/power_bi`, and the planned
  Looker/Qlik/Superset/Streamlit profiles.
- Inputs: `analytics_pipeline` `Report` (`0010`), `metrics_semantic_layer` (`0008`),
  `experimentation` (`0009`); chart standards from the `dataviz` skill.
