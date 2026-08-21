# Equities Domain Starter Kit

**For:** Portfolio managers, quant researchers, and risk managers building equities strategies.

## What's In This Kit

A pre-wired collection of agents, specs, and instructions for building, backtesting, monitoring, and attributing equity portfolios. Copy this directory into your repo and customize the constraints for your mandate.

## Quick Start

1. **Copy this directory** into your repo (e.g., `your-org/quantsmith`)
2. **Review the pre-wired agents** (see `agents.txt`)
3. **Read the example workflow** (see `example_workflow.md`)
4. **Adapt data_sources/** for your data providers (CRSP, Compustat, vendor, etc.)
5. **Set constraints** in your role_context.yml (sector caps, position limits, etc.)
6. **Start with the first spec** (`0001-daily-momentum-signal/`) as a worked example

## Pre-Wired Agents (Core Path)

| Agent | Role | When |
| --- | --- | --- |
| `workflow_orchestrator` | Routes work through Specify→Plan→Implement→Verify | Entry point for all work |
| `quant_analyst` | Composes research→data→signal→forecast→portfolio | Planning signals and strategies |
| `research_analyst` | Structures hypothesis, validates assumptions | Starting new research |
| `data_quality` | Reviews lineage, timestamps, point-in-time | Before any backtest |
| `feature_engineering` | Builds features with leakage detection | Signal development |
| `modeling` | Selects models, validates with purged folds | Return forecasting |
| `trading_strategies/momentum_analyst` | Cross-sectional momentum strategy | Momentum research |
| `trading_strategies/value_analyst` | Value/factor strategies | Value-based signals |
| `trading_strategies/carry_analyst` | Dividend carry + corporate actions | Dividend/carry strategies |
| `trading_strategies/mean_reversion_analyst` | Mean-reversion patterns | Reversal signals |
| `portfolio_management/pm_orchestrator` | Routes portfolio construction → execution → risk | After you have a forecast |
| `portfolio_management/portfolio_optimizer` | QP mean-variance construction | Building the portfolio |
| `portfolio_management/execution_scheduler` | Almgren-Chriss optimal execution | Trading into positions |
| `risk/` | Factor risk modeling, attribution, stress | Monitoring + validation |
| `backtest_review/` | Checks backtests for bias, costs, robustness | Before production |
| `testing_validation` | Validates acceptance criteria | Sign-off before launch |
| `deployment_release` | Handles production release + monitoring setup | Going live |
| `maintenance_monitoring` | Living spec, signal drift detection | Ongoing operations |

## Key Specs for Equities

| Spec | Purpose | When |
| --- | --- | --- |
| `0001-daily-momentum-signal` | Worked example: cross-sectional momentum | **Start here** — full end-to-end pipeline |
| `0006-ml-return-forecasting` | ML return forecast with DL challenger | Building supervised prediction models |
| `0041-ranking-forecast` | Ranking-loss variant (pairwise RankNet) | When ranking > point-wise predictions |
| `0007-portfolio-construction` | QP mean-variance optimizer | Portfolio construction from forecasts |
| `0034-cardinality-constrained-portfolio` | Select N best, optimize weights | When you want heuristic stock selection |
| `0012-execution-scheduling` | Almgren-Chriss execution optimizer | Scheduling trades to minimize impact |
| `0038-factor-risk-model` | Factor risk attribution & stress loss | Risk monitoring, portfolio review |
| `0044-backtesting` | Net-of-cost simulation engine | Validating strategies |
| `0046-walk-forward` | Out-of-sample testing with purged folds | Measuring robustness across regimes |
| `0021-signal-monitoring` | Drift/calibration/decay detection | Post-production signal health |
| `0028-financing-cost-analysis` | Cost-of-carry, short-borrow, financing | Adjusting for real transaction costs |

## Domain-Specific Instructions

- `instructions/point_in_time.md` — ensures no look-ahead in backtests
- `instructions/backtesting.md` — how to validate a strategy correctly
- `instructions/portfolio_engineering.md` — portfolio construction best practices
- `instructions/risk_management.md` — factor risk and stress testing
- `instructions/asset_class_mechanics.md` — equities-specific constraints (borrow costs, sector limits, etc.)

## Data Sources (Pre-Populated Examples)

| Source | What | Point-in-Time | Frequency | Notes |
| --- | --- | --- | --- | --- |
| CRSP | Daily returns, volumes, corporate actions | Yes (from CRSP) | Daily (5pm ET) | Include in `data_sources/crsp.yml` |
| Compustat | Fundamentals, financials | Yes (annual/quarterly) | Quarterly | Lag: 45 days after quarter end |
| FRED | Macro (yields, credit spreads, etc.) | Yes (publication lag) | Daily | Use `0045-fred-point-in-time` adapter |
| Yahoo Finance | Free alternative to CRSP | Limited | Daily | No delisting adjustment; use for prototyping |
| Vendor Feed | Your internal data (if any) | Configured by you | Intraday/daily | Define in your own `data_sources/` entries |

**See `data_sources/` for example `.yml` files.**

## Equity-Specific Constraints to Define

In your repo's `role_context.yml`:

```yaml
equities:
  sectors:
    max_single: 0.15          # No sector >15% of portfolio
    top_10_max: 0.60          # Top 10 sectors ≤60%
  
  positions:
    max_single_stock: 0.05    # No single stock >5%
    top_10_max: 0.30          # Top 10 stocks ≤30%
  
  borrowing:
    max_short_ratio: 0.10     # Shorts ≤10% of long positions
    borrow_cost_param: 0.03   # Assume 3% borrow cost on average
  
  market_impact:
    temporary_param: 0.01     # Temporary impact (bps per $1M traded)
    permanent_param: 0.001    # Permanent impact (bps per $1M traded)
  
  limits:
    max_beta: 1.2
    min_beta: 0.8
    max_drawdown: 0.20        # 20% max drawdown
    max_concentration: 0.30   # Top 10 holdings ≤30% of risk
```

## Example Workflow

See `example_workflow.md` for a step-by-step walkthrough:
1. Research hypothesis (e.g., "momentum reversal in the cross-section")
2. Data pull + validation (CRSP daily returns)
3. Feature engineering (past 6-month return, ranks)
4. Model selection (linear model on ranks)
5. Backtest with walk-forward (0046)
6. Portfolio construction (0007)
7. Execution scheduling (0012)
8. Risk attribution (0038)
9. Live monitoring (0021)

## Common Equity Workflows

**Signal Research → Portfolio → Backtest:**
```
Start → research_analyst (hypothesis)
     → data_quality (CRSP check)
     → feature_engineering (signals)
     → modeling (train/validate)
     → quant_analyst (forecast)
     → backtest (0044/0046)
     → backtest_review
     → pm_orchestrator (portfolio)
     → risk (attribution)
```

**Portfolio Rebalance:**
```
Start → macro_backdrop (current regime)
     → portfolio_optimizer (0007, with macro weights)
     → factor_risk_model (0038, stress test)
     → execution_scheduler (0012)
     → trading desk (execute)
     → risk monitor (watch intraday)
```

**Post-Trade Review:**
```
Start → attribution_analyst (what drove returns?)
     → signal_monitoring (0021, any drift?)
     → decision_log (document why/how)
```

## Customization Points

1. **Add a new signal type** → copy `agents/trading_strategies/momentum_analyst/` as a template
2. **Add a new data source** → add entry to `data_sources/` + register in source_catalog
3. **Tighten constraints** → edit `role_context.yml` + re-run gates
4. **Add a risk model** → extend `0038-factor-risk-model` runtime or add new agent

See `docs/extending_quantsmith/` for step-by-step examples.

## Quality Gates You Care About

- `leakage` — checks for look-ahead (point-in-time correctness)
- `backtest` — validates simulation integrity (no look-ahead, realistic costs)
- `repro` — reproducible results (same seed, same data = same result)
- `data-contract` — validates data schema/keys/freshness before you build on it

Run gates before any production deployment:
```bash
QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh leakage backtest repro data-contract
```

## Next Steps

1. Read `0001-daily-momentum-signal/spec.md` (requirements and acceptance criteria)
2. Run `example_workflow.md` (step-by-step walkthrough)
3. Adapt `role_context.yml` for your mandate
4. Add your data sources to `data_sources/`
5. Build your first signal following the worked example
6. Backtest with `0044-backtesting` and `0046-walk-forward`
7. Ship to production with `deployment_release` agent

Questions? Start with the **worked example specs** at `specs/README.md`.
