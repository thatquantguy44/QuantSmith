# Quant Researcher Role

## What You Do

You own signal research, return forecasting, model development, and backtesting. Your work transforms raw data into testable, production-ready trading strategies.

## Your Core Agents

**Research & Development:**
- `research_analyst/` — structures your research hypothesis and validates assumptions
- `quant_analyst/` — composes research → data → signal → forecast → portfolio workflow end-to-end
- `modeling/` — selects models, validates against leakage, analyzes errors

**Data & Features:**
- `data_quality/` — reviews lineage, timestamps, missingness, and point-in-time correctness
- `feature_engineering/` — builds features with leakage detection and stability checks
- `data_ingestion/` — pulls and validates raw data via contracts

**Signal Development:**
- `trading_strategies/` group agents (momentum, value, carry, mean-reversion, volatility)

**Validation & Testing:**
- `backtest_review/` — catches biases, costs, and robustness issues before production
- `modeling/` — runs leakage-free validation with purged/embargoed folds
- `testing_validation/` — stage owner ensuring all acceptance criteria pass

**Handoff Partners:**
- → **Portfolio Manager** when signal is production-ready (returns forecast)
- → **Risk Manager** for monitoring and drift detection
- ← **Data Engineer** provides clean, versioned datasets
- ← **Economist** provides macro regime context

## Your Key Specs

| Spec | What | Use When |
| --- | --- | --- |
| `0001-daily-momentum-signal` | Cross-sectional momentum | First working example (read this first) |
| `0006-ml-return-forecasting` | ML forecasting end-to-end | Building a supervised return prediction model |
| `0041-ranking-forecast` | Ranking-loss variant | Pairwise RankNet-style forecasting |
| `0044-backtesting` | Net-of-cost simulation | Testing your strategy on historical data |
| `0046-walk-forward` | Out-of-sample validation | Measuring robustness across regimes |
| `0039-ingestion-data-contract` | Data contract validation | Checking your data for schema/key/quality breaches |
| `0038-factor-risk-model` | Factor attribution | Understanding what drives your signal |

## Your Quality Gates

**Critical:**
- `leakage` — your signal must pass point-in-time correctness (look-ahead is fatal)
- `backtest` — backtests must show no look-ahead, honest costs, probabilistic Sharpe
- `repro` — your results must be reproducible (same seed, same data, same result)
- `data-contract` — data must be validated before you build on it

**Informational:**
- `monitoring-coverage` — is your signal monitored for drift post-production?

## Development Workflow

```
1. Form hypothesis (e.g., "momentum reversal in the cross-section")
   ↓
2. Research plan: data sources, periods, universe, success criteria
   ↓
3. Data pull via data_ingestion agents + validate with data contract (0039)
   ↓
4. Exploratory analysis (EDA) for patterns, missing data, outliers
   ↓
5. Feature engineering with leakage detection (0006's make_features)
   ↓
6. Model selection (linear, tree, neural net) with proper cross-validation
   ↓
7. Train on purged/embargoed folds (no look-ahead by construction)
   ↓
8. Backtest with walk-forward folds (0046) to measure out-of-sample Sharpe
   ↓
9. backtest_review agent checks for remaining biases or issues
   ↓
10. Pass to Portfolio Manager as a return forecast
```

## Common Workflows

- **"Build a momentum signal"** → Start at `0001-daily-momentum-signal/` (worked example)
- **"Forecast returns"** → `0006-ml-return-forecasting/` (full ML chain with DL challenger)
- **"Validate leakage"** → research_analyst + data_quality + `instructions/point_in_time.md`
- **"Backtest my strategy"** → backtesting (0044) → walk_forward (0046) → backtest_review
- **"Measure signal drift"** → `0021-signal-monitoring/` (regime, calibration, decay, decay detectors)

## Handoff Details

**To Portfolio Manager:**
- "Here are my return forecasts for equities/bonds; ready to integrate into portfolio construction"
- Input format: DataFrame with `(date, ticker, predicted_return, confidence)` columns
- Must include caveats: signal type, training period, out-of-sample Sharpe, regime sensitivities

**To Risk Manager:**
- "This signal is correlated with momentum; watch for factor concentration"
- "This is a macro signal; regimes shift it dramatically"

**From Data Engineer:**
- Receive validated datasets with data contracts (schema, keys, freshness SLAs)
- Notified of any upstream freshness issues that invalidate your backtest

## Specs You Reference But Don't Own

- `0007-portfolio-construction` (PM uses your forecasts as inputs)
- `0012-execution-scheduling` (PM uses this to trade your signal)
- `0038-factor-risk-model` (risk uses this to monitor your signal)

## What You Don't Own

- Portfolio construction (that's PM's domain)
- Execution (that's the desk)
- Production monitoring (that's operations/risk)
- Policy constraints (that's compliance)
