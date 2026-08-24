# Economists Agents

This folder groups agents that give a quant or portfolio-management workflow
a grounded macro backdrop to start from: what the data actually says, what
policy is doing, what regime that adds up to, how it's expressed across
assets, how it could break, and a clear write-up of all of it. They exist
because nothing else in the SDK does this — `agents/trading_strategies/
macro_multi_asset/` reviews macro-driven *strategies* but assumes the macro
read already exists; this group is where that read actually comes from.

## Pillars

| Pillar | Agents |
| --- | --- |
| Indicators | `macro_indicator_analyst/` |
| Policy & Regime | `monetary_policy_analyst/`, `macro_regime_classifier/` |
| Cross-Asset & Scenario | `cross_asset_macro_linkages/`, `macro_scenario_analyst/` |
| Synthesis & Reporting | `macro_backdrop_summarizer/`, `economic_outlook_report_writer/`, `morning_brief_writer/` |

## Note On Scope

This group is deliberately **analysis and synthesis, not action**. It does
not design or size a trading strategy — that stays
`agents/trading_strategies/macro_multi_asset/` — and it does not monitor a
live model's behavior for regime change — that stays `agents/monitoring/
model_signal_monitoring/`, a different job from classifying what the
current economic regime actually *is*. Every agent here hands its read to
a named downstream agent rather than acting on it.

## Agents

| Agent | Handles | Feeds mainly |
| --- | --- | --- |
| `economists/macro_indicator_analyst/` | Core releases (CPI/PCE, NFP, GDP, PMI, retail sales, housing) → a vintage-aware, surprise-vs-consensus read | `macro_regime_classifier`, `macro_backdrop_summarizer` |
| `economists/monetary_policy_analyst/` | Central bank stance, rate path, balance sheet, FOMC statement/minutes → a policy read | `macro_regime_classifier`, `research_analyst` |
| `economists/macro_regime_classifier/` | Indicators + policy → a classified regime (growth/inflation quadrant, cycle phase, tightening/easing) | `macro_multi_asset`, `portfolio_management/allocation_policy` |
| `economists/cross_asset_macro_linkages/` | A regime → how it's expressed across rates/FX/credit/equities/commodities | `research_analyst`, `trading_strategies/*` |
| `economists/macro_scenario_analyst/` | A regime → forward stress scenarios with quantified indicator paths | `risk`, `backtest_review` |
| `economists/macro_backdrop_summarizer/` | Everything above → a concise, recurring macro brief | `research_analyst`, `modeling`, `portfolio_management/*` (shared workflow context) |
| `economists/economic_outlook_report_writer/` | Everything above → a longer periodic outlook report | `portfolio_management/*`, an IC-facing deliverable |
| `economists/morning_brief_writer/` | Real, pulled market commentary (`market_brief.py`, spec `0059`) → grounded "Views & Analysis" for a personal daily brief | `market_brief.render_morning_brief`/`candidates_from_brief` (staged `pending_review`, never this group's other agents) |

## Data Foundation

Every agent here checks `sources/{fred,bls,bea,census,eia}.yml` (spec
`0027`) first for registered indicator data — quality, point-in-time
characteristics, and connection details — before treating any figure as
known. See `instructions/data_source_catalog.md`. `morning_brief_writer` is
the one exception: it works from market **commentary**, not macro
**indicators**, and its data foundation is `sources/{newsapi,
alpha_vantage_news,finnhub_news}.yml` (spec `0059`) instead.

## Shared Principles

Every economists agent upholds the constitution and
`instructions/macro_economic_analysis.md`:

- **Grounded, not invented.** An indicator value, policy statement, or
  forecast traces to a supplied input or a registered `sources/` entry;
  what isn't known yet is a stated gap, never a plausible guess. See
  `instructions/data_provenance.md`.
- **Point-in-time and vintage-aware.** First-print vs. revised values are
  different facts, stated explicitly. See `instructions/point_in_time.md`.
- **Analysis, not action.** Every output ends in a named handoff, not a
  trading or allocation decision made on this group's own authority.
- **Dated, always.** A macro read carries an explicit as-of date so it's
  never mistaken for live once time has passed.

## Where They Fit

`macro_indicator_analyst` and `monetary_policy_analyst` run first and feed
`macro_regime_classifier`, which in turn feeds `cross_asset_macro_linkages`
and `macro_scenario_analyst`. `macro_backdrop_summarizer` and
`economic_outlook_report_writer` synthesize all of the above into the
actual deliverable a workflow starts from — the summarizer for a recurring,
lightweight check-in, the outlook writer for a periodic, fuller report
(both render `templates/docs/macro_backdrop_report.md`, distinguished by
its `Cadence` field). A `workflow_orchestrator`-driven multi-agent sequence
typically hands one of these two reports to `research_analyst`, `modeling`,
or `portfolio_management/*` as shared context before domain-specific work
begins.

## Related

- `instructions/macro_economic_analysis.md` — the shared standard behind
  this group.
- `templates/docs/macro_backdrop_report.md` — the shared report template.
- `sources/README.md` — the data catalog this group draws from.
- `agents/trading_strategies/macro_multi_asset/` — strategy design/review,
  downstream of this group, not duplicated by it.
- `agents/monitoring/model_signal_monitoring/` — live-model regime-change
  detection, a distinct job from `macro_regime_classifier`'s economic
  regime classification.
- `agents/portfolio_management/` — the allocation/governance agents this
  group's reads typically feed.
