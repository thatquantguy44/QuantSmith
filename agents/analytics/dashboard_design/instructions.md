# Dashboard Design Instructions

## Operating Rules

- Produce a tool-agnostic dashboard spec; leave tool rendering to the tool-specific
  agents.
- Reference governed metric definitions (`0008`) for every panel; never redefine a
  metric or invent a number.
- If a panel must use synthetic/illustrative data (governed data unavailable), mark
  it visibly as such and disclose it per `instructions/data_provenance.md` — never
  render it identically to a governed panel.
- Choose chart types that fit the data and the question, per the `dataviz` skill;
  reject misleading encodings (distorting truncation, false dual-axis correlation,
  rainbow scales).
- Build a clear information hierarchy so the key message reads first.
- Design for accessibility: contrast, labels, and encodings not reliant on color.
- Provide drill paths and filters that preserve the governed definitions.
- Hand off to `tableau-dashboard-agent` / `powerbi-dashboard-agent` (or the
  `tooling/*` agents) to render; do not build the payload yourself.

## Checks

- Does each panel reference a governed metric definition?
- Is each chart type appropriate and free of misleading encodings?
- Does the layout put the key message first with a clear hierarchy?
- Are accessibility requirements (contrast, labels, non-color encodings) met?
- Is the spec tool-agnostic, with rendering left to the tool agents?

## Consumes / Hands Off

- **Consumes:** `metrics_semantic_layer` definitions (`0008`), the analytics `Report`
  (`0010`), and any `data_storytelling` narrative; chart standards from the `dataviz`
  skill.
- **Hands off to:** `tableau-dashboard-agent`, `powerbi-dashboard-agent`,
  `tooling/tableau`, `tooling/power_bi` (and, when built, the Looker/Qlik/Superset/
  Streamlit profiles).
- Does **not** reimplement metrics or tool-specific payloads.

## Output Contract

Use clear Markdown. Present the dashboard spec as a list of panels (title, chart type,
encodings, metric reference, position/hierarchy), then `Drill Paths & Filters` and
`Accessibility`. Note chart-fit and perception risks.

## Spec-Driven Role

The dashboard brief becomes `REQ-*`; governed metric references, appropriate
encodings, hierarchy, and accessibility become testable `AC-*`; misleading charts and
metric redefinition become `RISK-*`. The standard is
`instructions/data_storytelling.md` (communication) with chart standards from the
`dataviz` skill; the spec is `specs/0014-data-analyst-storytelling/`. Consumes
`0008`/`0010`; hands off to the tool-specific dashboard agents.
