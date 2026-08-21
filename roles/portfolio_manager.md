# Portfolio Manager Role

## What You Do

You own the portfolio construction, monitoring, and optimization lifecycle. Your decisions span:
- Allocation strategy (strategic/tactical)
- Rebalancing frequency and triggers
- Risk and concentration limits
- Performance attribution and review
- Compliance and governance handoffs

## Your Core Agents

**Routing & Orchestration:**
- `portfolio_management/pm_orchestrator/` — routes across the full portfolio lifecycle (mandate → universe → signals → allocation → implementation → risk → attribution)

**Execution & Construction:**
- `portfolio_management/portfolio_optimizer/` — builds a portfolio from return forecasts subject to constraints
- `portfolio_management/execution_scheduler/` — schedules trades to minimize market impact
- `portfolio_management/rebalancing_scheduler/` — decides when and what to rebalance

**Risk & Analysis:**
- `risk/` — monitors concentration, tail risk, factor exposures; flags breaches
- `portfolio_management/attribution_analyst/` — explains what drove your returns
- `backtest_review/` — validates your strategy works before production

**Macro & Economics:**
- `economists/macro_backdrop_summarizer/` — gives you current macro regime and cross-asset outlook
- `economists/macro_scenario_analyst/` — stress-tests your portfolio under forward scenarios

**Handoff Partners:**
- → **Quant Researcher** when you need new signals or forecasts
- → **Risk Manager** when concentration or stress loss hits limits
- → **Compliance Officer** for model governance and decision logs
- → **Data Engineer** when you need new data sources or real-time feeds
- ← **Execution desk** executes your trades; you receive fills

## Your Key Specs

| Spec | What | Use When |
| --- | --- | --- |
| `0007-portfolio-construction` | QP mean-variance optimizer | Building a portfolio from expected returns + covariance |
| `0012-execution-scheduling` | Almgren-Chriss execution | Scheduling a large rebalance with market-impact constraints |
| `0013-optimization-solvers` | LP/MILP/flow/DP toolkit | Cardinality selection, funding ladder, multi-period rebalancing |
| `0034-cardinality-constrained-portfolio` | Two-stage heuristic | Select N best stocks, optimize weights subject to limits |
| `0035-funding-ladder` | Min-cost flow | Match cash obligations to funding tenors (treasury/cash) |
| `0036-multi-period-rebalancing` | DP rebalancing policy | Decide when to rebalance based on tracking-error vs. cost tradeoff |
| `0044-backtesting` | Net-of-cost simulation engine | Backtest your strategy on historical data with financing costs |
| `0046-walk-forward` | Out-of-sample testing | Validate robustness across market regimes (folds) |
| `0038-factor-risk-model` | Risk attribution & stress | Understand risk drivers and test stress scenarios |

## Your Quality Gates

**Critical to you:**
- `backtest` — your strategy must pass backtesting before promotion
- `leakage` — advisory check for point-in-time correctness
- `data-contract` — upstream data must be validated (no garbage in)
- `alert-contract` — alerts must fire correctly so you catch issues

**Informational:**
- `monitoring-coverage` — are we monitoring your portfolio sufficiently?
- `role-context` — domain constraints wired into your automation

## Decision Workflow

```
1. Receive macro backdrop from economists
   ↓
2. Define allocation universe & constraints (sector/region/style limits)
   ↓
3. Receive return forecasts from quants (signals + ML models)
   ↓
4. Run portfolio optimizer (0007) subject to constraints
   ↓
5. Factor risk model (0038) outputs concentration & stress loss
   ↓
6. Adjust constraints if stress loss too high → re-optimize
   ↓
7. Execution scheduler (0012) creates 2-day trade plan
   ↓
8. Execution desk executes; you monitor fills
   ↓
9. Post-trade: attribution (0038) explains performance vs. benchmark
   ↓
10. Monthly: rebalancing decision via multi-period DP (0036)
```

## Common Workflows

- **"Build Q3 portfolio"** → pm_orchestrator → macro_backdrop → portfolio_optimizer → factor_risk_modeler → execution_scheduler
- **"Stress my portfolio"** → factor_risk_modeler (±100bp rate shock, ±10% equity shock) → flag if max drawdown > risk limit
- **"Backtest this strategy"** → quant_analyst (return forecasts) → backtesting (0044) → walk_forward (0046) → backtest_review
- **"Review attribution"** → factor_risk_model (0038) → outputs variance decomposition → discuss with quant team

## Handoff Details

**To Quant Researcher:**
- "I need return forecasts for equities/bonds/commodities for next month"
- "My strategy is underperforming in stagflation regimes; can you build a regime-aware signal?"

**To Risk Manager:**
- "Here's my portfolio; run stress tests and flag tail risks"
- "I'm at my duration limit; should I hedge with options?"

**To Compliance Officer:**
- "Sign off on this model card before I put it in production"
- "Here's my decision log for this quarter's allocation shift"

**From Data Engineer:**
- Receive validated data contracts for all upstream sources
- Notified of any SLA breaches or data freshness issues

## What You Don't Own

- Signal research (that's the quant researcher's domain)
- Model validation (that's the modeling/backtest_review team)
- Risk limits and policy (that's compliance/risk)
- Execution (that's the desk)
- Monitoring systems (that's operations/data engineering)
