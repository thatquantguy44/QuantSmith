# Multi-Asset Domain Starter Kit

**For:** Global macro traders, allocation managers, and cross-asset strategists.

## What's Different

- **Asset class composition:** Equities, bonds, FX, commodities, alternatives
- **Macro regime sensitivity:** Strategies change across growth/stagflation/deflation
- **Cross-asset correlation:** Equity/bond correlation breaks in regimes
- **Currency hedging:** FX exposure, carry, vol
- **Commodity exposure:** Futures contracts, roll yield, storage costs
- **Scenarios:** Multi-regime backtesting (not just historical data)

## Pre-Wired Agents (Beyond Equities)

All equities agents, plus:
- `economists/macro_backdrop_summarizer/` — current regime (growth/stagflation/deflation)
- `economists/macro_scenario_analyst/` — forward scenarios with asset-class implications
- `economists/cross_asset_macro_linkages/` — how rates affect equities, etc.
- `asset_classes/` group agents (equities, bonds, FX, commodities, digital assets)
- `portfolio_management/rebalancing_scheduler/` — tactical allocation shifts
- `risk/tail_risk_monitor/` — correlation breaks, regime shifts

## Key Specs

| Spec | Purpose |
| --- | --- |
| `0033-economists-agents` | Macro regime classification and scenario analysis |
| `0007-portfolio-construction` | Multi-asset QP with macro conditioning |
| `0038-factor-risk-model` | Cross-asset factor attribution (macro factors) |
| `0044-backtesting` | Multi-asset backtest (equities + bonds + FX + commodities) |
| `0046-walk-forward` | Test across different macro regimes (folds) |

## Domain-Specific Constraints

Add to `role_context.yml`:

```yaml
multi_asset:
  allocation:
    equities: [0.50, 0.65]
    fixed_income: [0.25, 0.35]
    commodities: [0.05, 0.10]
    fx_hedge: [0.00, 0.05]
  
  macro_scenarios:
    - growth: {equities: 0.60, bonds: 0.30, commodities: 0.10}
    - stagflation: {equities: 0.40, bonds: 0.20, commodities: 0.40}
    - deflation: {equities: 0.30, bonds: 0.60, commodities: 0.10}
  
  risks:
    max_duration: 7.0
    max_equity_beta: 1.0
    max_commodity_beta: 0.3
    max_correlation_break: 0.5  # Alert if equity/bond corr drops below -0.5
```

## Example Workflow

1. **Macro backdrop** → Economists output current regime + next regime probability
2. **Scenario weights** → Allocate capital to regime-weighted portfolio
3. **Asset class assembly** → For each asset class, pull forecasts:
   - Equities: quant_analyst (momentum + value)
   - Bonds: fixed income strategist (carry + value)
   - Commodities: commodity analyst (term structure, geopolitics)
   - FX: G10 trading desk (carry + momentum)
4. **Portfolio construction** → Optimize subject to cross-asset risk limits
5. **Execution** → Schedule across all asset classes simultaneously
6. **Monitoring** → Daily correlation/regime checks; alert if regime breaks

## Data Sources

- **FRED/BLS/BEA:** Macro indicators
- **Equity exchanges:** CRSP, etc.
- **Bond pricing:** Bloomberg MSRB
- **Commodity futures:** CME, ICE
- **FX:** ECB, Bloomberg
- **Volatility:** CBOE VIX, MOVE, commodity vol

See `data_sources/` for examples.

## Key Differences from Single-Asset

- **Regime changes matter:** Correlation breaks from +0.3 to -0.7 in stagflation
- **Carry is important:** FX carry, commodity curve carry, bond carry all add up
- **Execution is simultaneous:** Equities, bonds, FX all trade together; check for crosses
- **Stress testing must be multi-dimensional:** Not just equity down 10%; test equity down 10% + bond down 5% + VIX up 50%

## Next Steps

1. Copy this directory into your repo
2. Read spec `0033` (economists agents) — understand macro regimes
3. Define macro scenarios in `role_context.yml`
4. Integrate forecasts from each asset class
5. Build portfolio using `0007` with macro scenario constraints
6. Backtest using `0046` (walk-forward) across regime folds

See templates/equities/README.md for full guidance on other topics.
