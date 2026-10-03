# Visualization Packs (spec 0093)

Seven draft domain packs and fourteen decision-specific recipes extend
[0081 analytics packs](../analytics_packs/README.md) with executive findings,
ordered visual stories, analyst evidence, and investigation prompts. The
[approved specification](../../specs/0093-visualization-packs/spec.md) defines
scope; [tasks](../../specs/0093-visualization-packs/tasks.md) track remaining work.

## Use

From the repository root:

```sh
PYTHONPATH=src python3 -m quantsmith.visualization_packs validate
PYTHONPATH=src python3 -m quantsmith.visualization_packs coverage
PYTHONPATH=src python3 -m quantsmith.visualization_packs demo --output-dir /tmp/visualization-stories
```

The demo writes self-contained HTML with accessible SVG/tables, portable JSON,
and Markdown for finance, credit, and macro stories, plus a refused invalid-PD
summation case. All demo data is synthetic; see the
[disclosure](../../docs/0093_synthetic_data_disclosure.md).

## Integration contract

`load_catalog(root)` loads validated visualization and analytics packs.
`catalog.select(source_domains, intent)` returns one recipe or an explicit
unavailable/clarification outcome. Call `collect_evidence` for each section ID
using a governed `QueryPlan`, `SemanticLayer`, injected `Reader`, source citation,
as-of value, and access policy. `build_story` accepts the chosen pack/recipe,
collected evidence, and the same registry. Missing evidence returns a typed
non-answer. Comparison sections also require `<section_id>_baseline`.

Use `render_html`, `render_json`, or `render_markdown` on the story.
`dashboard_handoff(story, dataset)` returns the existing DashboardSpec payload
**with** the companion story containing evidence and caveats. A bare dashboard
spec cannot preserve these semantics by itself.

The collector authorizes every metric, dimension, and filter before invoking the
reader. It checks missing measures, non-finite values, domain aggregation rules,
and the caller's freshness limit. A trend computes each observed period
independently; it never sums balance snapshots over time. Non-additive measures
cannot use a sum/count definition. Ratios use the registered numerator and
denominator. The registered result's numeric representation must agree with the
0081 unit; the presentation layer does not infer percent/fraction conversion.

The injected reader remains responsible for release/vintage availability as of
the requested decision date: `Fact.period` is an observation period, not a
publication timestamp. `max_age` is measured in the caller's integer period units.

Claims bind their own metric, result digest, population, period, unit, and source.
Interpretations and actions are labelled investigation prompts. An optional
`Benchmark` requires a policy ID, exact evidence digest, unit, target, and declared
direction; without one, no performance verdict is inferred. No narrator, external
service, network access, or write-back is required.

## Pack contract

Schema `0093.1` requires identity, linked analytics-pack IDs, existing reviewer
agents, review metadata, and at least two recipes. Recipes name an intent,
audiences, decision, ordered sections, and a next investigation. Sections name
an existing metric, dimensions, view (`level`, `trend`, `breakdown`, `comparison`,
`attribution`), chart rule (`shape` or declared `table` fallback), interpretation
question, and caveats. Units and aggregation definitions cannot be overridden.

All packs remain draft until human content review. Approving spec 0093 did not
review domain conventions. The opt-in collector is a separately validated
composition path; it does not complete 0080's pending T-021/T-022 integration or
change existing answer behavior. Unsupported maturity curves, cumulative wealth
paths, cohort funnels, or age distributions use an explicit table fallback.

## Coverage register

Only the seven named domains are covered. Family membership does not imply
coverage of other domains. Extend a pack only with distinct decision questions,
required evidence, interpretation limits, and passing acceptance examples.

| Analytics pack | Family | Visualization coverage |
| --- | --- | --- |
| `aml_financial_crime` | `control_compliance` | covered |
| `asset_management` | `business_line` | covered |
| `cards_consumer_lending` | `business_line` | uncovered |
| `climate_esg_risk` | `risk` | uncovered |
| `collections_recovery` | `operations` | uncovered |
| `commercial_banking` | `business_line` | uncovered |
| `commodities_markets` | `markets` | uncovered |
| `consumer_compliance` | `control_compliance` | uncovered |
| `counterparty_risk_xva` | `risk` | uncovered |
| `credit_markets` | `markets` | uncovered |
| `credit_risk` | `risk` | covered |
| `custody_securities_services` | `business_line` | uncovered |
| `customer_marketing_analytics` | `cross_cutting` | uncovered |
| `derivatives_structured` | `markets` | uncovered |
| `digital_assets` | `markets` | uncovered |
| `economics_macro` | `cross_cutting` | covered |
| `equities_markets` | `markets` | uncovered |
| `finance_performance` | `finance_treasury` | covered |
| `fraud` | `control_compliance` | uncovered |
| `fx_markets` | `markets` | uncovered |
| `insurance` | `business_line` | uncovered |
| `investment_banking` | `business_line` | uncovered |
| `liquidity_risk` | `risk` | uncovered |
| `market_risk` | `risk` | uncovered |
| `model_risk` | `risk` | uncovered |
| `mortgages_home_lending` | `business_line` | uncovered |
| `operational_risk` | `risk` | uncovered |
| `operations_settlement` | `operations` | covered |
| `payments` | `business_line` | uncovered |
| `portfolio_management_performance` | `cross_cutting` | uncovered |
| `rates_fixed_income` | `markets` | covered |
| `regulatory_capital_reporting` | `finance_treasury` | uncovered |
| `retail_deposits` | `business_line` | uncovered |
| `sales_trading_execution` | `markets` | uncovered |
| `securities_financing_prime` | `markets` | uncovered |
| `short_term_markets_funding` | `markets` | uncovered |
| `trade_finance` | `business_line` | uncovered |
| `treasury_alm_irrbb` | `risk` | uncovered |
| `treasury_cash_management` | `business_line` | uncovered |
| `wealth_private_banking` | `business_line` | uncovered |
