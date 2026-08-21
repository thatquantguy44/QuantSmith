# Fixed Income Domain Starter Kit

**For:** Bond portfolio managers, fixed income quants, and rates traders.

## Key Differences from Equities

- **Duration focus:** DV01, parallel shifts, butterfly trades
- **Curve trading:** Term structure changes, roll-down, yield curve trades
- **Credit risk:** OAS, spread duration, credit event probability
- **Real-time data:** Bloomberg/ICE feeds (point-in-time lag is critical)
- **Constraints:** Rating limits, sector limits, duration ladder
- **Execution:** Bond liquidity < equity; execution cost higher; venues fragmented

## Pre-Wired Agents

Same orchestrators as equities, with these specializations:
- `asset_classes/fixed_income_analyst/` — bond-specific mechanics (coupon, accrual, duration)
- `portfolio_management/pm_orchestrator/` — with duration/spread/rating constraints
- `trading_strategies/carry_analyst/` — duration carry, roll yield
- `trading_strategies/value_analyst/` — value strategies on spreads + curve positioning
- `risk/` — with DV01, OAS, key-rate duration risk attribution
- `monitoring/` — DV01 drift, spread monitoring, curve shape monitoring

## Key Specs

| Spec | Purpose |
| --- | --- |
| `0007-portfolio-construction` | QP with duration/spread/concentration constraints |
| `0038-factor-risk-model` | Duration attribution, OAS exposure, curve positioning |
| `0044-backtesting` | Backtest bond returns (accrual + price changes) |
| `0046-walk-forward` | Regime robustness (low-vol vs. high-vol rate environments) |

## Domain-Specific Constraints

Add to `role_context.yml`:

```yaml
fixed_income:
  duration:
    target: 5.5              # Target duration = 5.5 years
    tolerance: 0.5           # ±0.5 years
    ladder: [0, 1, 3, 5, 10, 20, 30]  # Key rate durations to monitor
  
  spread_exposure:
    max_oas: 0.05            # Max OAS = 500bps
    credit_spread_max: 0.03  # Max credit spread = 300bps
  
  sector_limits:
    corporates: [0.40, 0.50]
    treasuries: [0.30, 0.40]
    municipals: [0.05, 0.15]
  
  ratings:
    min_avg_rating: 'BBB-'   # No below-BBB average
    max_high_yield: 0.10     # <10% high yield
```

## Data Sources

- **Bloomberg MSRB:** Real-time bond prices (1-minute lag)
- **FRED:** Treasury yields and spreads
- **Fed H.15:** Daily rates & spreads
- **Vendor:** Your bond pricing/valuation service

See `data_sources/` for examples.

## Example First Task

Read `0007-portfolio-construction/spec.md` and build a duration-constrained portfolio.

## Next Steps

1. Copy this directory into your repo
2. Customize `role_context.yml` with your duration/spread targets
3. Start with spec `0007` (portfolio construction with duration constraints)
4. Backtest with real accrual + price changes (0044)
5. Add your bond pricing feed to `data_sources/`

See main templates/equities/README.md for full guidance.
