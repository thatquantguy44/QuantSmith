# QuantSmith Twitter Visual Style Presets

These presets are the approved visual system for ThatQuantGuy Twitter content. The controlling workflow in `SKILL.md` must resolve a `visual_style` before any publication-ready visual is drafted, generated, or handed off for design.

## Brand identity contract

The account avatar/logo supplied by the account owner — the circular black-and-white illustrated quant holding the mug reading **MORE DATA / LESS EMOTION** — is the canonical visual brand mark.

- Use the supplied logo image as the branding mark on publication-ready custom visuals whenever the image asset is available to the renderer.
- Do **not** use the words `QuantSmith`, `QUANTSMITH`, or a QuantSmith wordmark as public-facing visual branding unless the user explicitly asks for it.
- Do not redraw, reinterpret, recolor, restyle, regenerate, or alter the logo. Preserve the supplied artwork and its aspect ratio.
- Prefer one small logo placement, normally top-left. A second placement is allowed only when the layout specifically needs a branded Quant Take/callout panel; avoid repetitive logo stamping.
- Keep the logo subordinate to the thesis and data. It should identify the account, not become the visual subject.
- Preserve clear space around the logo and enough size for the mug/avatar silhouette to remain recognizable on mobile.
- Never place chart labels, annotations, or decorative elements over the logo.
- If the canonical logo asset is unavailable during rendering, reserve a clean logo-safe area and explicitly flag `Logo asset required`; do not substitute a generated approximation or text wordmark.

Recommended repository asset path: `twitter_workflow/thatquantguy-evening-quant-content/assets/account-logo.png` (or `.jpeg` if the source is retained as JPEG). Visual generators should reference that asset when available.

## Selection contract

Allowed style IDs:

- `terminal`
- `institutional-research`
- `minimalist-quant`
- `user-specified` — only when the user explicitly requests another visual treatment.

If a visual does not materially improve the content, return **No visual**. Never silently invent a fourth house style or blend presets into an inconsistent hybrid.

## `terminal`

**Intent:** A sober institutional quant terminal or research console. It should feel like a production analytics surface, not science fiction.

**Canvas:** Near-black, charcoal, or another dark neutral. Subtle grid or panel structure is acceptable only when it helps organize information.

**Typography:** Monospace-first. Compact hierarchy. Use small caps/status labels sparingly. Avoid oversized marketing headlines.

**Charts and data:** Thin axes and line geometry, exact labels, concise legends, and source/date footer for data-driven work. Dense information is acceptable when it remains immediately legible.

**Accent:** One restrained highlight accent. Do not create rainbow encoding unless the data genuinely requires categorical separation.

**Layout:** Modular panels, terminal-like labels, analytical tables, system diagrams, or compact charts. Prioritize information architecture over decoration.

**Best for:** AI infrastructure and compute, optimization, model internals, production ML, systems, market plumbing, securities finance mechanics, dense analytical tables, technical diagrams, routing, collateral/cash/inventory problems, and operational research.

**Avoid:** Cyberpunk neon, Matrix motifs, fake code, hacker clichés, excessive glow, decorative command prompts, sci-fi HUD elements, gratuitous grids, and illegible density.

**Prompt seed:**

> Design as a sober institutional quant terminal/research console, not sci-fi. Use a near-black neutral canvas, monospace-first typography, compact analytical hierarchy, thin chart geometry, restrained single accent, exact labels, and high information density without clutter. Include the canonical account logo as a small unmodified brand mark when the asset is available. Do not use a QuantSmith wordmark. Avoid cyberpunk neon, fake code, Matrix motifs, glossy HUD styling, and decorative noise.

## `institutional-research`

**Intent:** A publishable institutional research chart or research-note visual that could sit naturally in a rigorous macro, equity, rates, or cross-asset report.

**Canvas:** White, off-white, or another light neutral background.

**Typography:** Clean sans-serif. Establish hierarchy through size and weight rather than ornamentation.

**Charts and data:** Precise axes, units, periods, labels, and scales. Annotate only turning points or comparisons that advance the thesis. Include source and as-of/release date in the footer for empirical visuals.

**Layout:** Analytical headline, concise subtitle when useful, primary chart or comparison, limited annotations, source/date footer, and one small canonical account logo. Prefer one dominant chart over a dashboard of small panels unless the thesis requires multiple views.

**Best for:** Macro, rates, inflation, labor, earnings, valuation, company comparisons, capital allocation, AI capex/ROIC, factor evidence, empirical market structure, time series, cross-sectional comparisons, and sourced quantitative claims.

**Avoid:** Glossy marketing visuals, ornamental illustrations, decorative gradients, 3D bars, oversized logos, text wordmarks, chartjunk, unnecessary icons, vague axes, and unsupported callouts.

**Prompt seed:**

> Design as a polished institutional research chart. Use a light neutral canvas, restrained sans-serif typography, a clear analytical headline, precise chart axes and units, only decision-useful annotations, and a source/date footer. Include the supplied circular MORE DATA / LESS EMOTION account logo as a small, unmodified brand mark, preferably top-left. Do not display QuantSmith as a wordmark. Favor evidence and hierarchy over decoration. Avoid glossy marketing treatment, gradients, 3D effects, clip-art, and chartjunk.

## `minimalist-quant`

**Intent:** Communicate one quantitative idea with maximum signal-to-ink. The viewer should understand the thesis within roughly three seconds.

**Canvas:** Plain light or dark neutral with substantial whitespace.

**Typography:** Clean and sharp. A single equation, key metric, short phrase, or comparison may dominate the composition.

**Charts and data:** Prefer one relationship, one series, one distribution, or one comparison. Remove labels that are not necessary to interpret the thesis.

**Layout:** One claim, one visual anchor, optional short annotation, and one small canonical account logo. No competing panels unless the comparison itself is the point.

**Best for:** Equations, optimization intuition, probability/statistics concepts, one surprising comparison, one relationship, one key number, portfolio intuition, educational quant content, and concise conceptual posts.

**Avoid:** Dashboards, dense legends, multiple competing panels, decorative illustration, excessive annotation, badges, text wordmarks, repeated metrics, and anything that dilutes the single quantitative idea.

**Prompt seed:**

> Design a minimalist quant card: one thesis, one visual anchor, high whitespace, extremely restrained labels, no decorative elements, and a clean quantitative hierarchy. Include the supplied circular MORE DATA / LESS EMOTION account logo as a small, unmodified brand mark. Do not display QuantSmith as a wordmark. Make the equation, relationship, or key comparison visually dominant. Remove anything that does not improve comprehension.

## Routing guidance

Use `terminal` when the content is primarily about a system, process, optimizer, technical mechanism, infrastructure stack, production model, market plumbing, or dense operational state.

Use `institutional-research` when the visual's credibility depends on sourced empirical evidence such as market data, macro releases, earnings, valuation, rates, company comparisons, time series, or cross-sectional results.

Use `minimalist-quant` when the thesis can be reduced to one equation, concept, relationship, distribution, key number, or surprising comparison.

If two presets are plausible, choose based on the *job of the visual*, not merely the topic. For example, an AI infrastructure post showing a sourced capex time series should generally use `institutional-research`; a schematic of the compute/power/network constraint stack should use `terminal`; a single marginal-ROIC equation should use `minimalist-quant`.

An explicit user request for another treatment takes precedence and must be labeled `user-specified` in the brief. The canonical logo rule still applies unless the user explicitly overrides branding for that visual.

## Shared visual rules

Across all presets:

- The quantitative thesis must be obvious before secondary detail.
- Use the canonical account logo for public-facing branding; do not substitute a QuantSmith wordmark.
- Preserve the logo unchanged and subordinate to the content.
- Use exact units, periods, and labels.
- Do not visually overstate precision or causality.
- For current/data-driven visuals, include the source and as-of/release date when feasible.
- Label conceptual or illustrative charts clearly.
- Never fabricate observations, estimates, or missing chart points.
- Prefer annotations that explain mechanism or surprise, not annotations that merely restate values.
- Maintain enough contrast and font size for mobile viewing on X.
- Do not imitate Bloomberg or another vendor's proprietary branding/trade dress.
- Avoid generic AI gradients, chartjunk, glossy 3D effects, clip-art, ornamental icons, decorative noise, and unnecessary dashboards.
- Provide concise alt text for every publication-ready visual.

## Visual brief template

Use this contract whenever a visual is recommended:

```text
Visual style: <terminal | institutional-research | minimalist-quant | user-specified>
Branding: canonical account logo (MORE DATA / LESS EMOTION); no QuantSmith wordmark
Logo asset: <asset path | Logo asset required>
Logo placement: <normally top-left; small and unobtrusive>
Format: <chart | infographic | diagram | meme | quant card>
Thesis: <one sentence>
Canvas/layout: <preset-compliant description>
Data/source: <source + as-of/release date, or Conceptual>
Axes/variables: <when applicable>
Annotations: <only thesis-relevant callouts>
Caveat: <when applicable>
Alt text: <concise accessible description>
```

## Pre-publication validation

A visual is not publication-ready until all of the following are true:

- A valid style ID is stated, or the workflow explicitly returns **No visual**.
- Branding uses the canonical account logo rather than a QuantSmith text wordmark, unless the user explicitly requested otherwise.
- The logo is the supplied artwork, unmodified, correctly proportioned, legible, and not visually dominant.
- If the logo asset was unavailable, the brief explicitly says `Logo asset required` rather than inventing a substitute.
- The thesis is understandable within roughly three seconds.
- Canvas, typography, hierarchy, density, chart treatment, and annotations match the selected preset.
- Numeric labels, signs, units, denominators, periods, and scales are correct.
- Source/date is shown when the visual is data-based and it is feasible to include it.
- Conceptual visuals are labeled as conceptual.
- No visual element introduces an unsupported factual or causal claim.
- Alt text is included.
- None of the selected preset's anti-patterns are present.
