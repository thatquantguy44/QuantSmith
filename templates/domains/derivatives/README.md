# Derivatives Domain Starter Kit

**For:** Options traders, volatility strategists, and exotic derivatives quants.

## What's Different from Cash Equities

- **Greeks management:** Delta, gamma, vega, rho require active rehedging
- **Vol surface:** Implied vol varies by strike/tenor; surface dynamics matter
- **Non-linear P&L:** Gamma P&L significant in high-vol regimes
- **Execution:** Hedging frequency (daily/intraday) drives costs
- **Implied vs. realized vol:** Strategy profits when IV > realized vol
- **Exotics:** Barrier, lookback, correlation products require MC simulation

## Pre-Wired Agents

All equities agents, plus:
- `trading_strategies/volatility_options_analyst/` — vol-based strategies, skew trading
- `portfolio_management/rehedging_scheduler/` — optimal hedge frequency under gamma P&L
- `risk/greek_risk_modeler/` — Delta, gamma, vega, rho attribution
- `risk/tail_risk_monitor/` — tail event monitoring, vol spike alerts
- `modeling/` — vol surface modeling, vol term structure

## Key Specs

| Spec | Purpose |
| --- | --- |
| `0007-portfolio-construction` | QP with Greeks constraints (delta-neutral, vega-constrained) |
| `0012-execution-scheduling` | Hedging execution (gamma P&L vs. bid-ask) |
| `0036-multi-period-rebalancing` | When to rehedge (DP: transaction cost vs. gamma drag) |
| `0038-factor-risk-model` | Greeks decomposition, vol factor attribution |
| `0044-backtesting` | Backtest with realistic vol surface, hedging costs |

## Domain-Specific Constraints

Add to `role_context.yml`:

```yaml
derivatives:
  greeks:
    target_delta: 0.0        # Delta-neutral
    max_vega: 50.0           # Max vega = 50 per bp move
    max_gamma: 10.0          # Max gamma per 1% move
  
  hedging:
    rehedge_frequency: 'daily'          # Rebalance daily
    rehedge_threshold_delta: 0.05       # If delta drifts >5%, rehedge
    rehedge_cost_budget: 0.0010         # Max 10bps per rehedge
  
  vol_surface:
    vol_model: 'smile'       # Include vol smile/skew
    surface_bump: [0.05, 0.10, 0.20]   # Test ±5%, ±10%, ±20% vol bumps
  
  execution:
    market_impact_vega: 0.001  # 0.1bp per unit vega traded
    bid_ask_spread: 0.001      # 0.1% bid-ask on underlying
```

## Strategy Types

### 1. **Volatility Arbitrage** (Buy vol when IV < RV)
```
Strategy: Long straddle (buy ATM call + put)
Setup:
  - Buy calls at 20 delta strikes
  - Buy puts at 20 delta strikes
  - Hedge with short stock (delta-neutral)
  - Hold for realized vol to exceed implied vol

Monitoring:
  - Daily Greeks: delta < 5%, vega = portfolio vega
  - Realized vol: rolling 30-day RV vs. strategy IV
  - Gamma P&L: realized vol × gamma² × time
  - Rehedge when delta > 5% or gamma drag > transaction cost

Backtest:
  - Historical IV vs. RV (1995-2024)
  - Hedging costs: bid-ask + commissions
  - Edge: RV - IV > hedging cost
```

### 2. **Skew/Smile Trading** (Sell OTM puts, buy OTM calls)
```
Strategy: Skew capture
Setup:
  - Sell 20-delta puts (receive premium for tail risk)
  - Buy 20-delta calls (cap upside but low cost)
  - Hedge with stock to stay delta-neutral

Monitoring:
  - Vol surface changes (is skew collapsing?)
  - Tail events (are we catching fat tails?)
  - Gamma P&L (realized vol drives profit/loss)

Backtest:
  - Vol surface changes across regimes
  - Crash scenarios (2008, 2020) where skew widens (bad)
  - Stable regimes where skew earns premium (good)
```

### 3. **Rate Hedge** (Long duration via swaptions)
```
Strategy: Swaption butterfly
Setup:
  - Long ATM swaption
  - Short 2× OTM swaptions
  - Calibrated to rate regime expectations

Monitoring:
  - Implied vol surface (rates vega)
  - Rate curve moves (convexity)
  - Realized rate vol

Backtest:
  - Historical rate moves (yields) vs. swaption payoffs
  - Hedging costs (bid-ask on rates)
  - Edge: swaption IV > realized rate vol
```

## Data Sources

- **Equity options:** Real-time bid/ask, implied vol surface (Bloomberg, vendor)
- **Rates options:** Swaption cubes, caplet-floorlet vols
- **Commodity options:** Volatility term structures
- **Realized vol:** Daily returns to compute RV windows

See `data_sources/` for examples.

## Execution Considerations

- **Hedging frequency:** Daily (equities), intraday (rates), event-driven (exotics)
- **Transaction costs:** Bid-ask spread + commissions (wider than cash equities)
- **Gamma P&L:** Realized vol × gamma × time → major P&L driver in backtest
- **Vol surface risk:** Smile/skew changes matter; not just spot vol level

## Example Workflow

1. **Strategy hypothesis** (e.g., "IV > RV; sell premium")
2. **Vol surface modeling** (implied vol surface + skew dynamics)
3. **Greeks setup** (delta-neutral hedge, vega exposure, gamma limits)
4. **Backtest** (0044) with daily hedging:
   - Pull historical vol surface + underlying prices
   - Price options each day (Black-Scholes or smile model)
   - Compute Greeks, rehedge, calculate P&L
   - Include transaction costs
5. **Out-of-sample validation** (0046) across vol regimes
6. **Risk monitoring** (0038 Greeks decomposition + tail monitoring)

## Critical Differences

| Aspect | Equities | Derivatives |
| --- | --- | --- |
| **Main P&L driver** | Directional (delta) | Gamma (if hedged) + theta + vega |
| **Rebalancing** | Monthly/weekly | Daily/intraday |
| **Transaction cost** | ~10bps | 50-200bps (options) / 20bps (futures) |
| **Tail risk** | Position size | Gamma P&L, vol spike |
| **Monitoring** | Price, return | Delta, gamma, vega, theta |

## Next Steps

1. Copy this directory
2. Choose a strategy (vol arb, skew, carry)
3. Model the vol surface for your underlying
4. Define Greeks limits in `role_context.yml`
5. Backtest with daily Greeks monitoring (0044)
6. Validate rehedging strategy (0036 multi-period DP)
7. Deploy with Greeks dashboard + tail alerts

See templates/equities/README.md for full guidance on orchestration and governance.
