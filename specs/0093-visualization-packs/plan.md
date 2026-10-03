# Plan: Domain Visualization Packs and Executive Storytelling

- **Spec:** 0093-visualization-packs (`spec.md`)
- **Status:** Approved scope; implementation plan
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-02

## Approach

Add an opt-in `quantsmith.visualization_packs` package. JSON packs reference
0081 metrics and dimensions; they cannot redefine units or aggregation.
Catalog selection uses 0081 source tags plus an explicit intent. Stories
consume evidence collected through 0080 authorization, plan validation,
execution, and chart selection with additional domain checks before execution.
Existing 0080 answers and all existing dashboard contracts remain unchanged.
This is a separately validated composition boundary: it does not complete
0080 T-021/T-022 or approve any domain pack for write-back.

## Architecture & Components

- `catalog.py`: versioned shape, references, review metadata, coverage, selection.
- `evidence.py`: authorized, governed execution; snapshot and rate restrictions;
  finite complete measures; provenance; immutable evidence and claim bindings.
- `story.py`: recipe assembly, chart selection, claim validation, supplied policy
  assessment, bounded executive findings, analyst evidence and traceable actions.
- `render.py`: portable JSON, Markdown, self-contained HTML with accessible SVG
  and tables, and a DashboardSpec handoff bundled with mandatory story metadata.
- `cli.py`: catalog validation, coverage, and deterministic fixture demonstration.

## Interfaces & Data Contracts

A pack has schema 0093.1, identity, linked analytics pack IDs, existing reviewers,
review status, and at least two recipes. Each recipe declares audience, intent,
decision, ordered sections (metric, dimensions, view, interpretation, caveats),
and an investigation prompt. Units and semantic restrictions come only from 0081.

Evidence collection accepts an evidence ID, analytics pack ID, QueryPlan, view,
SemanticLayer, Reader, source citation, fixed as-of, provenance caveats, clearance,
and AccessPolicy. Every requested dimension and filter is authorized before
reading. Denied inputs return an empty typed refusal without exposing the plan.
The caller's Reader is responsible for point-in-time release/vintage availability;
Fact only carries an observation period, so the SDK cannot infer publication time.

For `trend`, compute each observed period through existing `execute`; retain
period results and the latest observation, never aggregate snapshots over time.
For other views reject multi-period non-additive or semi-additive requests. A
non-additive measure registered as sum/count is rejected. Ratios retain the
semantic layer's governed numerator/denominator calculation. Missing measures,
missing dimensions, empty groups, or non-finite inputs/results fail closed.
This conservative boundary may refuse valid specialized models rather than infer
weights, currencies, quote directions, maturity order, or definitions.

Claims bind evidence ID and content digest, metric, unit, population, period,
as-of, value, and source. Rendering formats these bound values, never free-form
numeric prose. Comparisons show independently bound observations with comparable
scope; no invented variance calculation. Policy assessments require a supplied
policy ID and an exact evidence digest. Numeric thresholds retain that policy
reference. Narrative interpretation remains a labelled investigation prompt.

Unknown chart conventions are explicitly disclosed with a supported table
fallback. DashboardSpec cannot carry caveats itself: `dashboard_handoff` returns
it with the full story metadata; exporting the bare spec is not a complete story.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Authorize before read; inherit semantics; bind each claim to its own result; never sum a snapshot over time. |
| P5 Reversibility | yes | Opt-in package; no existing schemas changed; no writes or network in story construction. |
| P6 Observability | yes | Typed refusals, chosen recipes/rules, caveats, coverage, and evidence fingerprints travel in artifacts. |
| P9 Security & data | yes | Mask denied evidence, escape Markdown/HTML, carry provenance; examples are explicitly synthetic. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Catalog schema and references | T-001 |
| REQ-002 | Domain checks before evidence execution | T-002 |
| REQ-003 | Deterministic selection and missing-input reports | T-001, T-003 |
| REQ-004 | Bounded executive summary and analyst details | T-003 |
| REQ-005 | Existing chart form rules and explicit fallback | T-003, T-004 |
| REQ-006 | Exact claim-to-evidence binding | T-002, T-003 |
| REQ-007 | Separate observations, interpretation prompts, and linked actions | T-003 |
| REQ-008 | Identified caller-supplied policies | T-003 |
| REQ-009 | JSON/Markdown/HTML and dashboard handoff | T-004 |
| REQ-010 | Seven packs, fourteen recipes, explicit coverage register | T-001 |
| REQ-011 | Catalog and evidence validation | T-001, T-002 |
| REQ-012 | Refusal propagation, access checks and caveats | T-002, T-003, T-004 |
| REQ-013 | Executable three-domain demonstration | T-005 |
| NFR-001 | Stable sorting/hashes and fixed fixture inputs | T-002, T-005 |
| NFR-002 | Isolated opt-in package, existing regression suites | T-006 |
| NFR-003 | Accessible rendering and complete metadata | T-004, T-006 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Domain integration | New explicit collector composes existing primitives | Modify 0080 global answer path | Avoid claiming its review-dependent tasks are complete or changing default answers. |
| Narrative | Deterministic bound observations and investigation prompts | Open-ended LLM claims | Exact scope binding is inspectable; future narrators must preserve it. |
| Unsupported domain charts | Declared table fallback | Invent maturity order or model values | Metric values remain honest even when renderer capabilities are limited. |
| Example renderer | Local HTML/SVG and tables | New web framework/dependencies | Actual portable visual output without a new BI application. |
| Comparison | Current and baseline observations | Recompute arbitrary deltas in prose | Domain-specific arithmetic stays governed upstream. |

## Validation Strategy

Acceptance tests explicitly name AC-001 through AC-014. Mutations exercise bad
schemas, cross-metric bindings, suppressed attribution, invalid aggregation,
missing measures, restricted filters, stale/empty results, unsupported charts,
non-finite values, unsafe HTML, and conflicting selection. Positive fixtures cover
all fourteen recipes and chart shapes. The example renders finance, credit, and
macro stories twice and checks deterministic output. Run existing analytics-pack,
NL analytics, and dashboard tests, then the repository suite and relevant gates.

## Rollout, Observability & Rollback

Use the package explicitly; callers retain their readers, registry, clearance,
and review process. Catalog/coverage commands and story refusal reasons expose
readiness. Existing analytics reviewers plus the visualization/storytelling agents
own content review. Roll back by removing the opt-in caller integration; no stored
analytics catalogs or production database records are migrated.
