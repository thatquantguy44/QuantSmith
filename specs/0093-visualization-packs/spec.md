# Spec: Domain Visualization Packs and Executive Storytelling

- **ID:** 0093-visualization-packs
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA (approved in conversation, 2026-10-02)
- **Last updated:** 2026-10-02

> WHAT and WHY. This spec captures the owner's request for the
> `visualization-packs` branch: extend `0081` to visualize and interpret
> different domains through visual storytelling and executive-level analysis.
> Scope approved by the owner on 2026-10-02; implementation and verification
> are tracked in `plan.md` and `tasks.md`.

## Problem & Context

[`0081`](../0081-analytics-domain-packs/spec.md) supplies 40 analytics domain
packs across seven families. They define metric vocabulary, units, additivity,
interpretation restrictions, caveats, and chart conventions. They do not define
the sequence of questions, views, and evidence an executive needs to understand
what changed, how material it is, which breakdowns explain the result, and
what decision or investigation should follow.

[`0080`](../0080-nl-analytics-insights/spec.md) provides the question-to-answer
runtime, governed results, deterministic chart choice, computed insights, and
grounded narratives. [`0014`](../0014-data-analyst-storytelling/spec.md) and the
existing dashboard profiles provide communication roles and rendering contracts.
This feature connects those capabilities into reusable domain-specific visual
stories. It extends `0081` through references rather than duplicating metric
definitions or changing what the underlying data is allowed to mean.

Current integration limitation: `0080`'s domain-pack application tasks T-021
and T-022 remain pending, as documented in its tasks and the repository handoff.
The new work must prove that domain restrictions reach its actual output path;
loading an `0081` catalog alone does not establish governed interpretation.

## Goals

- Give executives a concise answer to a decision-relevant question, with an
  inspectable path from the headline to the chart, result, and source.
- Supply reusable visualization and narrative recipes for different domains,
  selected by domain and analytical intent.
- Make stories explain levels, changes, comparisons, composition, and uncertainty
  in ways that respect each domain's metric definitions and restrictions.
- Carry the same meaning, evidence, and caveats into executive summaries,
  detailed analyst views, and supported dashboard/report outputs.
- Prove a complete question-to-visual-story path with representative domains
  before expanding the catalog to every `0081` pack.

## Non-Goals

- Replacing `0081`, redefining its metrics, or creating a second semantic layer.
- Claiming all 40 domains are covered in the first release.
- Building a new general-purpose BI application, renderer suite, or database.
- New data connectors, live data acquisition, forecasting models, or causal
  inference. Existing governed results are inputs, not raw material for new
  undocumented calculations.
- Marking analytics or visualization packs reviewed on a human's behalf.
- Autonomous investment decisions, external publication, or database write-back.
- Silently resolving the separate review dependency of `0080` T-021/T-022.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Define a versioned visualization-pack contract with identity, linked `0081` pack IDs, intended audiences and decisions, analytical questions, ordered story recipes, required evidence, chart rules, interpretation guidance, caveats, review status, and reviewer references. Every linked pack and reviewer must exist. | must |
| REQ-002 | Resolve metric and dimension references through the linked `0081` packs and governed metric definitions. A visualization pack must not override units, additivity, insight suppressions, source access, or domain caveats; ambiguous references require clarification. | must |
| REQ-003 | Select compatible recipes deterministically from the applicable analytics packs, analytical intent, and available evidence. Return an explicit reason for ambiguity, missing evidence, or an unsupported domain; never quietly substitute a different domain story. | must |
| REQ-004 | Each recipe must name its audience, decision question, headline evidence, ordered visual sections, interpretation prompts, and a next action or investigation. Executive output must lead with one principal finding and at most three supporting findings; analyst output must expose the supporting evidence and permitted drill paths. | must |
| REQ-005 | Choose each chart through a declared rule based on the result shape and domain conventions, using supported chart types. Charts must name their metric, unit, period, source, relevant baseline, encoding rule, and accessible text/table alternative. Unsupported conventions must produce a stated fallback or unavailable view. | must |
| REQ-006 | Bind every quantitative claim to its specific evidence: governed metric/result reference, value, unit, population or dimension selection, period, as-of boundary, and comparator where relevant. A matching number elsewhere in the evidence is insufficient. Display formatting must preserve that binding. | must |
| REQ-007 | Separate observations, interpretations, and proposed actions. Contributor analyses must be labelled as arithmetic attribution, not causal proof; recommendations must identify their supporting findings and material caveats. Unsupported claims must be omitted or returned for clarification. | must |
| REQ-008 | Show materiality, direction of improvement, targets, limits, or status colors only when the caller supplies an applicable, identified policy or governed benchmark. Without one, show the observed result and the missing context rather than inventing a target or verdict. | must |
| REQ-009 | Produce a portable story artifact containing ordered chart specifications, the executive narrative, evidence references, an analyst detail view, and provenance. Support existing dashboard/report handoffs plus a Markdown/table fallback without losing warnings or changing metric meaning. | must |
| REQ-010 | Include seven initial domain packs spanning all seven `0081` families, as listed below. Each must contain at least two decision-specific recipes with distinct evidence requirements, relevant domain pitfalls, and independently testable expected behavior. Publish an explicit coverage register for the remaining analytics packs. | must |
| REQ-011 | Validate pack structure, reference integrity, recipe compatibility, evidence bindings, review metadata, and catalog coverage. Reject unsupported schema versions, duplicate identifiers, unknown metrics/dimensions, and malformed recipes with actionable findings. | must |
| REQ-012 | Preserve upstream access decisions, as-of boundaries, data provenance, and review caveats through every output. Masked, empty, stale, or ambiguous results must not become a positive headline or a misleading chart. Draft-pack use must remain visible and cannot be promoted to reviewed output by this feature. | must |
| REQ-013 | Demonstrate the real composition path from authorized governed results through applicable domain restrictions to a rendered visual story and executive narrative. Include positive and negative examples, with reproducible evidence showing that the actual output honors `0081` semantics. | must |

## Initial Domain Coverage

These questions define the intended stories; they are not predetermined findings.
The available governed evidence determines whether a recipe can run.

| Family | Linked `0081` pack | Example executive questions | Domain-specific interpretation requirement |
| --- | --- | --- | --- |
| Business lines | `asset_management` | How did AUM and net flows change? How do fees and performance compare across mandates? | Separate flows from valuation movements; do not infer an AUM bridge without its governed components. |
| Markets | `rates_fixed_income` | Where did yields or spreads move? Which maturity exposures matter for the decision? | Respect rate units, maturity order, as-of dates, and declared sensitivity conventions. |
| Risk | `credit_risk` | Where are exposures concentrated? How do expected loss and credit quality compare across portfolios? | Do not sum PD or LGD; preserve exposure/allowance snapshot timing and declared default/measurement bases. |
| Finance & treasury | `finance_performance` | Which segments differ most from plan? How are revenue, expense, and efficiency changing? | Distinguish currency variance from rate changes; only show an actual-versus-plan view when both exist on comparable bases. |
| Control & compliance | `aml_financial_crime` | Where is the review workload accumulating? How are investigation throughput and timeliness changing? | Operational counts are not evidence of criminality; preserve denominators and distinguish process measures from outcomes. |
| Operations | `operations_settlement` | Where are settlement failures concentrated? Which unresolved breaks need attention? | Separate event flows from outstanding snapshots; do not sum open balances across dates. |
| Cross-cutting | `economics_macro` | Which indicators changed as of this decision date? How does the current reading compare with the declared baseline? | Carry release/vintage context, distinguish levels from growth rates, and avoid causal claims from co-movement. |

Additional `0081` domains, including portfolio management and liquidity risk,
must be named as uncovered or planned until their recipes and evidence exist.
Coverage is not inferred from a shared family or a generic chart template.

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Reproducibility | Fixed pack versions, evidence, policy inputs, and as-of values produce identical story ordering, selections, claims, and validation findings; no hidden clock, live network dependency, or required LLM call. |
| NFR-002 | Compatibility and reversibility | Existing `0081` catalogs, `0080` default answers, and dashboard contracts continue to pass their existing tests. The feature is opt-in and removable without migrating stored analytics packs. |
| NFR-003 | Inspectability and accessibility | Each story records pack/version and recipe choices, exclusions and reasons, source/result references, review status, and visible caveats; charts expose labels and a text/table equivalent and do not rely on color alone. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a valid initial catalog, when validated, then every required field and linked reference resolves; changing a schema version, duplicating an ID, or naming an unknown metric, dimension, or reviewer yields a specific error. | REQ-001, REQ-011 |
| AC-002 | Given PD, VaR, or a balance snapshot, when a recipe requests an invalid summation or suppressed insight, then the story path rejects that operation and explains the domain restriction. A visualization recipe cannot override it. | REQ-002, REQ-012 |
| AC-003 | Given identical domain, intent, and evidence inputs in different input orders, when selected, then recipe ordering and reasons are identical. Unknown domains and conflicting references produce explicit unavailable or clarification outcomes. | REQ-002, REQ-003, NFR-001 |
| AC-004 | Given a complete recipe, when an executive story is emitted, then it names the decision, leads with one finding, includes no more than three supporting findings, and provides a next action or investigation linked to its evidence. The analyst view exposes the same evidence at greater detail. | REQ-004, REQ-007 |
| AC-005 | Given compatible KPI, time-series, category, and two-dimension results, when charts are emitted, then declared rules choose supported chart types and include units, periods, sources, relevant baselines, labels, and text/table alternatives. An unsupported domain view yields an explicit fallback. | REQ-005, NFR-003 |
| AC-006 | Given two metrics with the same numeric value but different units, periods, or populations, when a claim is bound to the wrong result, then validation rejects it even though the number appears elsewhere. Properly bound rounded displays remain valid. | REQ-006 |
| AC-007 | Given an arithmetic contributor analysis without causal evidence, when narrated, then it is labelled attribution and no causal conclusion is emitted. An action without supporting findings is rejected or omitted with a reason. | REQ-007 |
| AC-008 | Given a metric without a target, comparator, or direction policy, when rendered, then no invented red/amber/green verdict, materiality claim, or above-plan statement appears. A supplied compatible policy is identified alongside any verdict. | REQ-008 |
| AC-009 | Given a story and a supported dashboard/report handoff, when exported, then chart order, metric references, evidence links, and caveats survive; the Markdown/table alternative expresses the same findings. | REQ-009, NFR-003 |
| AC-010 | Given the committed catalog, when coverage is checked, then all seven named initial domains have at least two distinct recipes each, all seven families are represented, and every other `0081` pack is explicitly classified as uncovered or planned. | REQ-010, REQ-011 |
| AC-011 | Given masked, stale, empty, draft, or synthetic inputs, when a story is requested, then refusal states remain non-answers and applicable caveats travel with every usable output; draft status and synthetic provenance are never removed. | REQ-012 |
| AC-012 | Given compatible governed results for three initial domains with different semantic constraints, when the full example is run twice, then actual charts and executive narratives are produced deterministically with traceable claims. A deliberately incompatible operation is refused in that same path. | REQ-013, NFR-001 |
| AC-013 | Given incomplete evidence for a recipe, when requested, then missing inputs are listed; no zero, baseline, driver, or benchmark is fabricated to complete the story. | REQ-003, REQ-005, REQ-006 |
| AC-014 | Given the existing analytics-pack, natural-language analytics, and dashboard-contract suites, when the new feature is disabled, then prior behavior and public contracts remain valid without rewriting existing catalogs. | NFR-002 |

## Data & Dependencies

- [`0081` analytics packs](../../knowledge/analytics_packs/README.md): metric
  semantics, dimensions, caveats, source-domain selection, and reviewer routing.
- [`0008` semantic layer](../0008-metrics-semantic-layer/spec.md): authoritative
  metric definitions and governed computation.
- [`0080` natural-language analytics](../0080-nl-analytics-insights/spec.md):
  authorized results, insights, chart specifications, and answer states. Its
  pending domain-pack integration must be addressed explicitly in the plan,
  either through an approved integration or a separately validated composition
  boundary that does not claim those tasks are complete.
- [`0014` storytelling](../0014-data-analyst-storytelling/spec.md), existing
  [`dashboard contracts](../../src/quantsmith/pipelines/dashboard_spec.py), and
  [`render adapters](../../adapters/dashboard_render/README.md): communication
  and rendering interfaces.
- [`0058` access control](../0058-viewer-access-control/spec.md),
  [`data storytelling`](../../instructions/data_storytelling.md), and
  [`data provenance`](../../instructions/data_provenance.md): existing rules
  remain authoritative.
- Examples use public or clearly labelled synthetic fixtures with fixed as-of
  values. No firm data, credentials, or live source access is required.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A compelling narrative overstates evidence. | Misleading executive decisions. | Bind claims to specific evidence, separate interpretation from observation, and test unsupported causal statements. |
| RISK-002 | A visualization bypasses domain arithmetic rules. | Attractive but invalid analysis. | Enforce inherited restrictions on the real composition path; include negative end-to-end examples. |
| RISK-003 | Broad catalog coverage is mostly generic templates. | Superficial domain interpretation. | Start with seven explicit domains, distinct questions and evidence needs, and an honest coverage register. |
| RISK-004 | Export drops caveats or exposes masked detail. | Misleading or unauthorized output. | Test provenance and caveat preservation across each supported output; preserve access decisions before story construction. |
| RISK-005 | Existing rendering contracts cannot express a domain convention. | Incorrect or silently degraded charts. | Use a declared supported fallback or report the view unavailable; do not claim unsupported rendering. |
| RISK-006 | Review dependencies in `0080`/`0081` are mistaken for completed integration. | Governance bypass or blocked delivery. | Keep review status visible and identify the exact composition boundary before implementation. |

## Assumptions & Open Questions

- Approved first release: seven packs and at least fourteen recipes, with a
  working example spanning at least three domains. Expansion to all forty packs
  is a later coverage decision.
- Initial audiences: executive/committee review and analyst investigation.
- Existing chart and dashboard interfaces are the default output boundary;
  any incompatible change requires an explicit compatibility decision.
- Owner approved the initial domain set and executive output: an executive
  summary plus a portable visual storyboard with an analyst detail view, suitable
  for existing renderers. Planning and implementation are authorized.

## Exceptions

None.
