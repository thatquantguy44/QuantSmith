# Spec: Economists Agent Expansion

- **ID:** 0033-economists-agents
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`agents/trading_strategies/macro_multi_asset/` reviews macro and allocation
*strategies* — regime dependence, macro-data vintage risk, correlation
instability, leverage — but it assumes the macro read driving that strategy
already exists somewhere. Nothing in the SDK actually tracks economic
indicators, reads policy, classifies the macro regime, or writes a macro
backdrop a quant or portfolio-management workflow can start from. The data
foundation for this is already in place and unused for this purpose:
`sources/{fred,bls,bea,census,eia}.yml` (spec `0027`) covers growth,
inflation, labor, housing, and energy data as public, cataloged, point-in-
time-aware sources.

A placeholder for this work already exists at `agents/economists/` — a
stray, unwired directory from an earlier parallel merge
(`agent/portfolio-management-agents`, PR `#35`) containing only a literal
`"placeholder"` `README.md`, not listed in `agents/README.md`'s catalog and
not referenced anywhere else in the repository. This spec reclaims that
directory as the real group.

## Goals

- Add a real `agents/economists/` category folder (replacing the stray
  placeholder) with seven agents across four pillars:
  - **Indicators:** `macro_indicator_analyst` — tracks and interprets core
    releases (CPI/PCE, NFP, GDP, PMI, retail sales, housing) from the
    source catalog, point-in-time/vintage-aware, surprise-vs-consensus.
  - **Policy & Regime:** `monetary_policy_analyst` (central bank stance,
    rate path, balance sheet, FOMC statement/minutes interpretation) and
    `macro_regime_classifier` (synthesizes indicators + policy into a
    regime label — growth/inflation quadrant, cycle phase,
    tightening/easing).
  - **Cross-Asset & Scenario:** `cross_asset_macro_linkages` (maps the
    macro backdrop to rates/FX/credit/equity/commodity behavior — backdrop
    translation, not strategy design) and `macro_scenario_analyst`
    (forward stress narratives with quantified macro paths).
  - **Synthesis & Reporting:** `macro_backdrop_summarizer` (a concise,
    recurring macro brief) and `economic_outlook_report_writer` (a longer
    periodic outlook report).
- Add `instructions/macro_economic_analysis.md`, the shared backing
  standard: point-in-time/vintage discipline, real-data-first grounding
  (no fabricated indicator values, policy statements, or forecasts), and
  the group's explicit boundaries against `trading_strategies/
  macro_multi_asset` (strategy design) and `monitoring/
  model_signal_monitoring` (live-model regime-change detection — a
  different job from classifying what the current macro regime *is*).
- Add `templates/docs/macro_backdrop_report.md`, shared by the two
  reporting agents (a `Cadence` field distinguishes a short recurring
  brief from a longer periodic outlook; the longer cadence fills
  additional sections the short one may leave as "not this cycle").
- Update the agent catalog, spec index, and top-level README so the group
  is discoverable and routable, matching every other category-group spec's
  wiring (`0022`, `0024`).

## Non-Goals

- No runtime code, executable pipeline, or live data/forecasting service in
  this slice — agent contracts, a backing standard, and a report template
  only, consistent with `0022`'s own precedent (a future implementation
  spec may add a runtime indicator-vintage helper if a concrete workflow
  needs one).
- No strategy design or allocation sizing — that remains
  `trading_strategies/macro_multi_asset` and `agents/portfolio_management/`'s
  job; this group hands off a macro read, it does not act on it.
- No duplication of `monitoring/model_signal_monitoring`'s regime-change
  detection (a live model's behavior diverging from its training regime);
  `macro_regime_classifier` produces the economic regime *label* that
  gives that detection meaning, it does not itself monitor a model.
- No new gate. The group's outputs are advisory Markdown briefs/reports,
  matching `asset_classes/` and `trading_strategies/`'s own precedent of
  no dedicated gate; existing `agent-catalog`/`docs-link`/`spec`/
  `spec-index` gates cover this slice.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide a `agents/economists/` category folder with a group README describing the four pillars, scope, and routing, replacing the stray placeholder. | must |
| REQ-002 | The system shall provide seven four-file agents (`macro_indicator_analyst`, `monetary_policy_analyst`, `macro_regime_classifier`, `cross_asset_macro_linkages`, `macro_scenario_analyst`, `macro_backdrop_summarizer`, `economic_outlook_report_writer`), each usable with no configuration. | must |
| REQ-003 | The system shall provide `instructions/macro_economic_analysis.md`, covering point-in-time/vintage discipline, real-data-first grounding, and explicit scope boundaries against `macro_multi_asset` and `model_signal_monitoring`. | must |
| REQ-004 | The system shall provide `templates/docs/macro_backdrop_report.md`, shared by `macro_backdrop_summarizer` and `economic_outlook_report_writer`, scaling by a stated cadence. | must |
| REQ-005 | Every agent's `instructions.md` shall state a named downstream handoff (`macro_multi_asset`, `portfolio_management/*`, `risk`, `backtest_review`, or `research_analyst`) rather than presenting itself as the final word on a trading or allocation decision. | must |
| REQ-006 | The agent catalog (`agents/README.md`), spec index (`specs/README.md`), and top-level `README.md` shall list the new group and its agents. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Agent contract consistency | Every new public agent has `README.md`, `prompt.md`, `instructions.md`, `tasks.md`, each with a `Spec-Driven Role` section. |
| NFR-002 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index` gates and the full pytest suite pass. |
| NFR-003 | No fabrication | Every agent's `instructions.md` states explicitly that an indicator value, policy statement, or forecast absent from the input/source is flagged as a gap, never invented, per `instructions/data_provenance.md`. |
| NFR-004 | Scope boundary | Agent docs state explicitly what stays owned by `macro_multi_asset`, `portfolio_management/*`, and `model_signal_monitoring`, so a reader never assumes duplication. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `agents/economists/README.md`, when inspected, then it describes the four pillars, lists all seven agents, and no longer contains the placeholder stub text. | REQ-001 |
| AC-002 | Given each of the seven agents' `instructions.md`, when inspected, then each explicitly states it must work without configuration and never fabricates an indicator/policy/forecast value absent from its input. | REQ-002, NFR-001, NFR-003 |
| AC-003 | Given `instructions/macro_economic_analysis.md`, when inspected, then it covers point-in-time/vintage discipline and states the group's boundary against `macro_multi_asset` and `model_signal_monitoring`. | REQ-003, NFR-004 |
| AC-004 | Given `templates/docs/macro_backdrop_report.md`, when inspected, then it defines a `Cadence` field and sections usable by both a short recurring brief and a longer periodic outlook. | REQ-004 |
| AC-005 | Given each agent's `instructions.md`, when inspected, then each names at least one downstream handoff agent. | REQ-005 |
| AC-006 | Given `agents/README.md`, `specs/README.md`, and root `README.md`, when inspected, then each lists the `economists/` group and its seven agents. | REQ-006 |
| AC-007 | Given the full gate suite, when run, then `spec`, `agent-catalog`, `docs-link`, `spec-index` all pass. | NFR-002 |

## Data & Dependencies

No data dependencies, no runtime code. Agents reference `sources/
{fred,bls,bea,census,eia}.yml` (spec `0027`) as their data foundation and
`instructions/point_in_time.md` / `instructions/data_ingestion.md` for
vintage discipline, but this slice adds no new source entries or ingestion
code — those catalog entries already exist and are already public/active.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The new group's scope overlaps with `trading_strategies/macro_multi_asset` (strategy review) or `monitoring/model_signal_monitoring` (regime-change detection), causing duplicated or conflicting guidance. | Confusing routing; two agents give inconsistent answers to the same question. | Each agent's `instructions.md` and the group README state the boundary explicitly and name the downstream handoff instead of making a strategy or model-health call (AC-005, NFR-004) — the same pattern already proven for `asset_classes/` against `trading_strategies/`/`securities_financing/`. |
| RISK-002 | An agent states an indicator value, policy stance, or forecast that sounds authoritative but isn't grounded in anything actually supplied or cataloged. | A quant/PM workflow makes a decision on a fabricated macro fact. | `instructions/macro_economic_analysis.md` and every agent's operating rules require flagging a gap rather than inventing a value, per `instructions/data_provenance.md`'s existing real-data-first standard (NFR-003). |
| RISK-003 | A recurring macro brief becomes stale and is read as current. | A workflow acts on an outdated regime read. | `templates/docs/macro_backdrop_report.md` requires an as-of date and cadence on every instance; `macro_backdrop_summarizer`'s `instructions.md` states the brief is only as current as its stated as-of date, matching the staleness caveat already used in `instructions/data_source_catalog.md`. |

## Assumptions & Open Questions

- Assumption: seven agents across four pillars is the right first slice —
  enough to cover indicators through synthesis without building a
  per-country or per-central-bank agent before any of this has been used.
- Assumption: reclaiming the existing `agents/economists/` placeholder
  (rather than creating a differently-named group) is correct, since it is
  unwired and contains no real content to preserve.
- Open question: does a per-region variant (e.g. a Europe/UK-specific
  `monetary_policy_analyst` counterpart) become worth splitting out once
  this group sees real cross-region use, versus handling region as an
  input to the existing agents?

## Exceptions

None.
