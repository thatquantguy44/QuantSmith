# Risk Manager Role

## What You Do

You own real-time portfolio risk monitoring, stress testing, limit enforcement, and escalation. Your job is to catch tail risks, regime breaks, and breaches before they become disasters.

## Your Core Agents

**Risk Monitoring & Analysis:**
- `risk/` — owns exposure tracking, concentration detection, drawdown monitoring, stress-loss calculation
- `risk/factor_risk_modeler/` — variance decomposition, Euler attribution (assets + factors), concentration, stress
- `risk/tail_risk_monitor/` — detects tail events, correlations breaks, regime shifts
- `backtest_review/` — validates strategy robustness before production

**Signals & Model Monitoring:**
- `monitoring/model_signal_monitoring/` — detects signal drift (calibration, decay, regime sensitivity)
- `alerts/alert_router/` — routes alerts by severity/type to appropriate stakeholders
- `alerts/incident_notification/` — escalates critical breaches

**Portfolio & Market Monitoring:**
- `portfolio_management/attribution_analyst/` — explains performance drivers (signal, implementation, market factors)
- `data_engineering/pipeline_observability/` — tracks data freshness/SLA breaches that could invalidate your risk model

**Handoff Partners:**
- ← **Portfolio Manager** sends portfolio positions; you monitor them
- → **Portfolio Manager** when concentration breaches limits; you recommend rebalancing
- → **Compliance Officer** for governance escalation and post-mortems
- ← **Data Engineer** provides fresh risk factor data (volatilities, correlations)
- ← **Quant Researcher** tells you about signal regime sensitivities

## Your Key Specs

| Spec | What | Use When |
| --- | --- | --- |
| `0038-factor-risk-model` | Variance decomposition & stress | Understand portfolio risk drivers and test shocks |
| `0021-signal-monitoring` | Drift/calibration/decay detection | Monitor signal quality post-production |
| `0020-alerting` | Policy evaluation + routing | Define alert rules and dispatch by severity |
| `0044-backtesting` | Backtest simulation integrity | Validate strategy does not have hidden look-ahead |
| `0046-walk-forward` | Out-of-sample robustness | Measure strategy performance across regimes |
| `0028-financing-cost-analysis` | Cost-of-carry & financing risk | Understand true returns after borrow costs |

## Your Quality Gates

**Critical:**
- `backtest` — strategies must pass backtesting; financing costs must be real
- `leakage` — you flag any point-in-time correctness issues upstream
- `alert-contract` — alerts must be generated, routed, and not silenced arbitrarily
- `monitoring-coverage` — you verify adequate monitoring exists for all strategies

**Informational:**
- `data-contract` — upstream data quality affects risk model reliability

## Monitoring Workflow

```
Daily/Intraday:
  1. Receive portfolio positions and market data
     ↓
  2. Run factor risk model (0038) → decompose portfolio risk
     ↓
  3. Check vs. risk limits:
       - Factor exposures (duration, beta, vega, commodity beta)
       - Concentration (top-10 as % of risk)
       - Drawdown vs. limit
     ↓
  4. If any breach:
       - Generate alert (0020)
       - Route to PM + compliance (alert_router)
     ↓
  5. Stress test (0038) under 5 scenarios:
       - ±100bp parallel rate shift
       - ±10% equity shock
       - +200bp credit spread
       - USD +5% / -5%
       - Vol +50% / -50%
     ↓
  6. If stress loss > limit → flag to PM

Weekly/Monthly:
  1. Signal monitoring (0021) checks for drift
  2. Attribution analysis explains performance drivers
  3. Decision log review (compliance)
```

## Common Workflows

- **"Stress-test the portfolio"** → factor_risk_model (0038) with user-defined shocks
- **"Is my signal degrading?"** → signal_monitoring (0021) for drift/calibration/decay detectors
- **"What's driving my returns?"** → attribution_analyst (0038) decomposition
- **"Why did we breach our concentration limit?"** → factor_risk_model → explain to PM + log decision
- **"Alert me if correlation breaks"** → tail_risk_monitor + alert_router (0020)

## Handoff Details

**To Portfolio Manager:**
- "Your portfolio is at 110% of equity beta limit; recommend reducing positions XYZ"
- "Concentration in tech (top-5 = 28% of risk) exceeds 25% limit"
- "Stress loss under +200bp credit spread is $2.3M (>$2M limit); recommend hedge"

**To Compliance Officer:**
- "We hit our liquidity limit 3 times this month; need policy review"
- "Signal drift detected in momentum factor; requires model review before next month"
- "Correlation break between rates and equities; regime shift indicator?"

**From Quant Researcher:**
- "Momentum signal is sensitive to vol regime; watch it in low-vol markets"
- "Historical calibration on rate forecasts breaks post-2023"

**From Portfolio Manager:**
- New positions to monitor + their constraints
- New risk limits to enforce

## Specs You Reference But Don't Own

- `0007-portfolio-construction` (PM uses this; you review the outputs)
- `0044-backtesting` (quants use this; you review before production)
- `0046-walk-forward` (quants use this; regime dispersion is your concern)

## What You Don't Own

- Portfolio construction (that's PM)
- Strategy development (that's quant researcher)
- Execution (that's the desk)
- Governance policy (that's compliance, though you enforce it)
- Model ownership (that's the quant team; you monitor its behavior)
