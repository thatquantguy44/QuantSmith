# Analytics Domain Packs (spec `0081`)

Pluggable financial-services knowledge for natural-language analytics
([`specs/0080-nl-analytics-insights/`](../../specs/0080-nl-analytics-insights/)).
Owned by [`specs/0081-analytics-domain-packs/`](../../specs/0081-analytics-domain-packs/);
validated by `src/quantsmith/pipelines/analytics_packs.py`.

A pack tells `0080` how to read one kind of data. It supplies the words people
use for each metric, the metric's unit, and whether it can be added up. It
also says which insights make no sense for the metric, which caveats always
apply, how to chart it, and which agent reviews answers about it. **40 packs, 204 metrics, across seven
families** spanning a bank or financial-services firm, front to back office.

## How a pack is chosen

Every `sources/*.yml` entry already declares `domain:` tags (spec `0027`). A
dataset's tags select every pack whose `source_domains` intersect them — a FRED
rates series tagged `["macro", "fixed_income_rates"]` selects
`economics_macro` and `rates_fixed_income`. Where two selected packs use the
same word for different metrics, `0080` asks a clarification instead of
picking. No match means generic behavior, stated in the response.

## Where packs are loaded from

This directory is the single source. A build of the `quantsmith` package
copies it, byte for byte, into the package as read-only **bundled defaults**
(`setup.py`), so `pip install quantsmith` works without a checkout.
`analytics_packs.resolve_packs()` then picks one whole catalog:

1. `--packs-root DIR` (or `resolve_packs(DIR)`): only `DIR/knowledge/analytics_packs/`.
   No packs there is an error; it never falls back to the bundle.
2. Otherwise `./knowledge/analytics_packs/` under the working directory, if it
   holds any packs. It **replaces** the bundle entirely — packs are never
   merged one by one, so an answer's review status is never a mix of your
   reviewed packs and newer bundled drafts.
3. Otherwise the bundled defaults.

Every answer that applies a pack cites the source (local or bundled, location,
package version, catalog hash), so you can tell which packs a reviewer signed
off. Bundled defaults change with each release; pin the package version or keep
a local copy if answers must not move on upgrade. To customize or review packs,
copy this directory into your repository and edit or `--mark-reviewed` there —
never edit the bundled copy inside `site-packages`.

## What a pack can and cannot do

- **Only restrict.** A pack suppresses insights, adds caveats, and fixes units.
  It can never widen access (`0058`), loosen `0008` metric governance, or
  enable an insight the base rules forbid.
- **Additivity is the core rule.** `additive` (flows: P&L, volume, losses) sums
  across dimensions and time; `semi_additive` (stocks: balances, exposures)
  sums across dimensions but not time; `non_additive` (rates, ratios, prices,
  VaR/PFE quantiles) never sums. A rate-like unit (`pct`, `bps`, `ratio`, …)
  must be `non_additive` unless the metric states an `additivity_rationale`.
  A non-additive metric never gets a "contributor" insight.
- **Review gates write-back, not chat.** Every pack ships `draft`. `0080` may
  apply a draft pack in chat with a visible "unreviewed domain pack" caveat,
  but database write-back requires every applied pack to be `reviewed` by a
  named person with a date. The validator refuses `reviewed` without both.
- **Not advice, not firm data.** Conventions are general, public industry
  practice. Nothing here is legal, accounting, or regulatory advice, and no
  pack contains company data. Deep, reviewed contracts stay in
  [`knowledge/credit_risk/`](../credit_risk/) and
  [`knowledge/short_term_markets/`](../short_term_markets/); the packs that
  touch them reference them in `builds_on` rather than redefine them.

## Pack shape (`schema_version` `0081.1`)

| Field | Meaning |
| --- | --- |
| `pack_id`, `name`, `family`, `description` | Identity; `pack_id` equals the file name. |
| `source_domains` | `sources/*.yml` domain tags that select this pack. |
| `builds_on` | Existing specs or knowledge packs this pack defers to (paths must exist). |
| `reviewer_agents` | Existing agents that review answers in this domain (must have `prompt.md`). |
| `dimensions[]` | `name`, `description`, `synonyms` — breakdowns people ask for. |
| `metrics[]` | `name`, `description`, `unit`, `additivity`, `synonyms`, optional `additivity_rationale`. |
| `conventions[]` | `id`, `rule` — units, sign conventions, bases, definitions. |
| `insight_rules[]` | `id`, `applies_to` (metric name or glob), `suppress_kinds`, `reason`. |
| `caveats[]` | `id`, `trigger` (`always` \| `metric:<name>` \| `dimension:<name>`), `text`. |
| `chart_conventions[]` | `id`, `rule`. |
| `golden_cases[]` | Machine-checked cases: `bps_change`, `additivity`, `ratio`. |
| `review` | `status` (`draft` \| `in_review` \| `reviewed`), `reviewer`, `reviewed_on`, `notes`. |

Units: `currency`, `currency_per_unit`, `count`, `quantity`, `pct`, `bps`,
`ratio`, `multiple`, `index`, `score`, `years`, `days`.

## Validate

```sh
PYTHONPATH=src python3 -m quantsmith.pipelines.analytics_packs --report
python3 -m pytest tests/test_analytics_packs.py -q
```

## Review assignments

Joshua Lutkemuller, CFA reviews all seven families (owner decision,
2026-09-24). Review pack by pack:

```sh
# read everything to check for one family
PYTHONPATH=src python3 -m quantsmith.pipelines.analytics_packs --review-sheet risk
# after editing any wrong content, record the review on one pack
PYTHONPATH=src python3 -m quantsmith.pipelines.analytics_packs \
  --mark-reviewed market_risk --reviewer "Joshua Lutkemuller, CFA" --date 2026-09-24
```

`--mark-reviewed` refuses an empty name, a non-ISO date, or a pack that fails
validation, and changes only that pack's `review` block.

## Adding or reviewing a pack

1. Copy the closest pack, keep `review.status: draft`, and add a row below.
2. Map at least one `sources/*.yml` domain tag; name an existing reviewer agent.
3. Add golden cases for every metric whose additivity or unit is non-obvious.
4. To review: a named domain owner checks every convention, then sets
   `status: reviewed`, `reviewer`, and `reviewed_on`. That is the only change
   that makes the pack eligible for write-back.

## Catalog

### Business lines & client franchises (`business_line`)

| Pack | Covers | Selected by `sources/*.yml` domain | Reviewer agent(s) | Builds on | Status |
| --- | --- | --- | --- | --- | --- |
| `asset_management` | Funds and mandates: AUM, flows, fees, and investment performance versus benchmark. (6 metrics) | `asset_management`, `funds` | `portfolio_management/performance_attribution`, `portfolio_management/monitoring_governance` | — | draft |
| `cards_consumer_lending` | Credit cards, personal loans, and auto loans: balances, spend, yield, delinquency, and losses. (7 metrics) | `consumer_lending`, `cards`, `retail_lending` | `risk`, `credit_risk/fair_lending_review` | `knowledge/credit_risk`, `specs/0074-retail-underwriting-fairness-harness` | draft |
| `commercial_banking` | Commercial and industrial loans, commercial real estate, small business, and corporate relationship lending. (6 metrics) | `commercial_lending`, `corporate_banking`, `commercial_real_estate`, `small_business` | `risk`, `credit_risk/counterparty_limits` | `knowledge/credit_risk`, `specs/0073-wholesale-credit-measurement` | draft |
| `custody_securities_services` | Custody, fund administration, and asset servicing for institutional clients. (4 metrics) | `custody`, `securities_services`, `fund_administration` | `risk`, `data_quality` | — | draft |
| `insurance` | Property & casualty and life insurance underwriting, claims, and reserves. (6 metrics) | `insurance`, `underwriting` | `risk`, `modeling` | — | draft |
| `investment_banking` | Advisory, equity and debt capital markets underwriting, and the deal pipeline. (5 metrics) | `investment_banking`, `capital_markets_origination` | `research_analyst`, `risk` | — | draft |
| `mortgages_home_lending` | Residential mortgage and home-equity origination, servicing, prepayment, and credit performance. (7 metrics) | `mortgages`, `home_lending`, `residential_real_estate` | `risk`, `asset_classes/fixed_income_rates` | `knowledge/credit_risk` | draft |
| `payments` | Card issuing and acquiring, ACH, wires, and real-time payments: volumes, authorization, disputes, and economics. (5 metrics) | `payments`, `cards_network`, `merchant_acquiring` | `risk`, `monitoring/pipeline_monitoring` | — | draft |
| `retail_deposits` | Consumer checking, savings, money market, and certificate-of-deposit balances, pricing, and account dynamics. (6 metrics) | `retail_deposits`, `deposits` | `risk`, `portfolio_management/liquidity_cash_management` | — | draft |
| `trade_finance` | Letters of credit, guarantees, documentary collections, and supply-chain finance. (4 metrics) | `trade_finance` | `risk`, `credit_risk/counterparty_limits` | — | draft |
| `treasury_cash_management` | Transaction banking for corporate clients: operating balances, liquidity products, and payment and receivables services. (4 metrics) | `cash_management`, `transaction_banking` | `portfolio_management/liquidity_cash_management`, `risk` | — | draft |
| `wealth_private_banking` | Advisory and brokerage assets, flows, fee rates, and lending to high-net-worth clients. (5 metrics) | `wealth_management`, `private_banking` | `portfolio_management/performance_attribution`, `risk` | — | draft |

### Markets (`markets`)

| Pack | Covers | Selected by `sources/*.yml` domain | Reviewer agent(s) | Builds on | Status |
| --- | --- | --- | --- | --- | --- |
| `commodities_markets` | Energy, metals, and agricultural futures: curves, roll, and inventories. (5 metrics) | `commodities` | `asset_classes/commodities`, `trading_strategies/carry` | `specs/0022-asset-class-mechanics-agents` | draft |
| `credit_markets` | Corporate bonds, leveraged loans, CDS, and securitized credit: spreads, defaults, and ratings. (5 metrics) | `credit_markets`, `corporate_bonds`, `securitized` | `asset_classes/fixed_income_rates`, `risk` | `specs/0022-asset-class-mechanics-agents`, `knowledge/credit_risk` | draft |
| `derivatives_structured` | Listed and OTC options, swaps, and structured notes: notionals, valuations, and greeks. (5 metrics) | `derivatives`, `options`, `structured_products` | `trading_strategies/volatility_options`, `risk` | — | draft |
| `digital_assets` | Cryptoassets and tokenized instruments: prices, volumes, venues, and custody. (4 metrics) | `digital_assets`, `crypto` | `asset_classes/digital_assets`, `risk` | `specs/0022-asset-class-mechanics-agents` | draft |
| `equities_markets` | Cash equities and equity indices: prices, returns, volumes, valuation, and risk. (6 metrics) | `equities` | `asset_classes/equities`, `trading_strategies/value_factor` | `specs/0022-asset-class-mechanics-agents` | draft |
| `fx_markets` | Spot and forward FX, FX options, and currency exposure. (5 metrics) | `fx` | `asset_classes/fx`, `trading_strategies/carry` | `specs/0022-asset-class-mechanics-agents` | draft |
| `rates_fixed_income` | Government bonds, swaps, and interest-rate curves: yields, spreads, and rate sensitivity. (5 metrics) | `fixed_income_rates`, `rates` | `asset_classes/fixed_income_rates`, `risk` | `specs/0022-asset-class-mechanics-agents`, `specs/0045-fred-point-in-time` | draft |
| `sales_trading_execution` | Client franchise and execution quality: revenues, market share, hit ratios, and transaction costs. (5 metrics) | `execution`, `sales_trading`, `market_structure` | `optimization/execution_optimization`, `trading_strategies/market_making_microstructure` | `specs/0012-execution-scheduling` | draft |
| `securities_financing_prime` | Securities lending, borrow costs, and prime brokerage client financing. (5 metrics) | `securities_lending`, `prime_brokerage` | `securities_financing/securities_lending`, `securities_financing/financing_cost_analysis` | `specs/0023-securities-lending-workflow`, `specs/0028-financing-cost-analysis`, `specs/0066-securities-lending-model-correction` | draft |
| `short_term_markets_funding` | Repo, money markets, and short-dated cash products: rates, haircuts, and funding structure. (5 metrics) | `short_term_markets`, `repo`, `money_markets`, `funding`, `cash_products`, `collateral` | `securities_financing/repo_financing`, `securities_financing/collateral_management` | `knowledge/short_term_markets`, `specs/0063-short-term-markets-domain-foundation` | draft |

### Risk (`risk`)

| Pack | Covers | Selected by `sources/*.yml` domain | Reviewer agent(s) | Builds on | Status |
| --- | --- | --- | --- | --- | --- |
| `climate_esg_risk` | Financed emissions, physical and transition risk exposure, and sustainability metrics. (4 metrics) | `climate`, `esg` | `enterprise_risk/climate_esg_risk`, `research_analyst` | `instructions/enterprise_risk.md` | draft |
| `counterparty_risk_xva` | Derivative and securities-financing counterparty exposure and valuation adjustments. (5 metrics) | `counterparty_credit_risk`, `xva` | `enterprise_risk/counterparty_credit_risk`, `credit_risk/counterparty_limits` | `instructions/enterprise_risk.md`, `specs/0073-wholesale-credit-measurement` | draft |
| `credit_risk` | Wholesale and retail credit exposure, expected loss, allowance, and credit quality. (6 metrics) | `credit_risk`, `expected_credit_loss`, `regulatory_capital` | `credit_risk/counterparty_limits`, `risk` | `knowledge/credit_risk`, `specs/0072-credit-risk-domain-foundation`, `specs/0073-wholesale-credit-measurement` | draft |
| `liquidity_risk` | Regulatory and internal liquidity metrics, buffers, and funding concentration. (5 metrics) | `liquidity`, `liquidity_risk` | `enterprise_risk/liquidity_treasury_risk`, `portfolio_management/liquidity_cash_management` | `instructions/enterprise_risk.md` | draft |
| `market_risk` | Trading-book risk: VaR, expected shortfall, sensitivities, stress, and backtesting. (6 metrics) | `market_risk` | `risk`, `backtest_review` | — | draft |
| `model_risk` | Model inventory, validation status, findings, performance monitoring, and overrides. (4 metrics) | `model_risk_management` | `enterprise_risk/model_risk_management`, `role_operations/governance_readiness_checklist`, `machine_learning/mlops_monitoring` | `instructions/enterprise_risk.md` | draft |
| `operational_risk` | Operational loss events, risk and control self-assessments, key risk indicators, and issues. (5 metrics) | `operational_risk` | `enterprise_risk/operational_risk`, `alerts/incident_notification` | `instructions/enterprise_risk.md` | draft |
| `treasury_alm_irrbb` | Balance-sheet interest-rate risk, funds transfer pricing, and net interest income sensitivity. (5 metrics) | `alm`, `irrbb`, `treasury` | `enterprise_risk/liquidity_treasury_risk`, `portfolio_management/liquidity_cash_management` | `instructions/enterprise_risk.md` | draft |

### Finance & treasury (`finance_treasury`)

| Pack | Covers | Selected by `sources/*.yml` domain | Reviewer agent(s) | Builds on | Status |
| --- | --- | --- | --- | --- | --- |
| `finance_performance` | Firm, segment, and product financial performance: revenue, expense, margins, and returns. (6 metrics) | `finance`, `financial_reporting`, `fpa`, `accounting` | `reporting-agent`, `analytics/metrics_semantic_layer` | — | draft |
| `regulatory_capital_reporting` | Capital ratios, risk-weighted assets, leverage, stress capital, and regulatory reports. (5 metrics) | `regulatory_capital`, `regulatory_reporting` | `risk`, `credit_risk/counterparty_limits` | `knowledge/credit_risk` | draft |

### Control & compliance (`control_compliance`)

| Pack | Covers | Selected by `sources/*.yml` domain | Reviewer agent(s) | Builds on | Status |
| --- | --- | --- | --- | --- | --- |
| `aml_financial_crime` | Transaction monitoring, sanctions screening, KYC, and suspicious activity reporting. (6 metrics) | `aml`, `sanctions`, `kyc`, `financial_crime` | `enterprise_risk/aml_financial_crime`, `alerts/alert_policy` | `instructions/enterprise_risk.md` | draft |
| `consumer_compliance` | Complaints, fair lending, UDAAP, and conduct risk indicators. (4 metrics) | `consumer_compliance`, `fair_lending`, `conduct` | `credit_risk/fair_lending_review`, `risk` | `knowledge/credit_risk`, `specs/0074-retail-underwriting-fairness-harness` | draft |
| `fraud` | First- and third-party fraud across cards, payments, and digital channels. (4 metrics) | `fraud` | `machine_learning/unsupervised_anomaly`, `risk` | — | draft |

### Operations (`operations`)

| Pack | Covers | Selected by `sources/*.yml` domain | Reviewer agent(s) | Builds on | Status |
| --- | --- | --- | --- | --- | --- |
| `collections_recovery` | Delinquent account treatment, roll rates, cures, and recoveries. (4 metrics) | `collections`, `recovery` | `risk`, `credit_risk/fair_lending_review` | `knowledge/credit_risk` | draft |
| `operations_settlement` | Trade processing, settlement, reconciliations, and operational service levels. (5 metrics) | `operations`, `settlement`, `clearing` | `monitoring/pipeline_monitoring`, `data_quality` | — | draft |

### Cross-cutting (`cross_cutting`)

| Pack | Covers | Selected by `sources/*.yml` domain | Reviewer agent(s) | Builds on | Status |
| --- | --- | --- | --- | --- | --- |
| `customer_marketing_analytics` | Acquisition, engagement, cross-sell, attrition, and customer value across products. (6 metrics) | `customer`, `marketing` | `analytics/experimentation`, `machine_learning/causal_uplift` | `specs/0009-experimentation` | draft |
| `economics_macro` | Macroeconomic indicators, policy rates, and regimes used as context across the firm. (4 metrics) | `macro`, `labor` | `economists/macro_indicator_analyst`, `economists/monetary_policy_analyst` | `specs/0033-economists-agents`, `specs/0045-fred-point-in-time` | draft |
| `portfolio_management_performance` | Portfolio positioning, risk budgets, and performance attribution for any managed book. (5 metrics) | `portfolio_management`, `performance_attribution` | `portfolio_management/performance_attribution`, `portfolio_management/risk_budgeting` | `instructions/portfolio_management.md` | draft |

## Not yet covered

Source tags with no pack (reported by the validator as `info`):
`market_commentary`, `nlp_llm`, `quant_text_intelligence`,
`text_intelligence`, `supervisory_guidance`, `regulatory_context`. These tag
text and document sources handled by `0071`/`0077`, not tabular data `0080`
queries. Corporate functions without financial-services-specific conventions
(HR, procurement, facilities) use `0080`'s generic behavior.
