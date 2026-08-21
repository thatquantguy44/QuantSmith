# Example Equities Workflow: Cross-Sectional Momentum Signal

**Goal:** Build a cross-sectional momentum signal, backtest it, and integrate into portfolio construction.

**Timeline:** 2 weeks (research) → 1 week (validation) → production

## Phase 1: Research Planning (Week 1)

### Step 1: Hypothesis Structuring
```
Call: research_analyst
Input: "Cross-sectional momentum reversal in US large-cap equities"
Output: 
  - REQ-001: Build a momentum signal on 6-month past returns
  - REQ-002: Backtest 2000-2024, rebalance monthly
  - AC-001: Outperform SPY benchmark by ≥2% Sharpe
  - NFR-001: Execute in <100ms per portfolio update
```

### Step 2: Data Validation
```
Call: data_quality
Input: CRSP daily returns, 2000-2024
Checks:
  - Point-in-time correctness: returns available by 5pm ET on day D+1 ✓
  - Delisting handling: do we include delisted stock returns? Yes, until delisting date.
  - Survivorship bias: backtest excludes stocks that didn't exist in 2000 ✓
  - Corporate actions: splits/dividends adjusted? Yes (CRSP adjusted factor) ✓
Output: Data contract passed
```

## Phase 2: Feature & Model Development (Weeks 2-3)

### Step 3: Feature Engineering
```
Call: feature_engineering
Code:
  # 6-month lagged returns (no look-ahead)
  returns_6m = (price[t-1] / price[t-252]) - 1  # 252 trading days ≈ 1 year
  rank_6m = cross_sectional_rank(returns_6m)    # Rank within universe
  
Leakage check:
  ✓ No forward-looking data
  ✓ Cross-sectional (no time-series leakage across stocks)
  ✓ Embargo window: momentum from t-252 to t-1 meets returns at t to t+21
Output: (date, ticker, rank_6m) feature set
```

### Step 4: Model Selection & Training
```
Call: modeling
Approach: Linear model on ranks (simplest baseline)
  Long signal: rank > 60th percentile
  Short signal: rank < 40th percentile
  Position size: rank_score (0 to 1)

Cross-validation:
  ✓ Purged folds: training and test periods don't share stock identities
  ✓ Embargo window: 6 months after training period (respect momentum lag)
  ✓ No parameter tuning on test set (backtest_review will check this)

Output: Fitted model, validation IC=0.08 (in-sample)
```

## Phase 3: Backtesting (Week 4)

### Step 5: Run Backtest
```
Call: backtesting (Spec 0044)
Input:
  - Weights from model (long/short positions)
  - Daily returns (CRSP)
  - Transaction costs: 10bps entry, 10bps exit
  - Rebalance frequency: monthly (first trading day)
  - Period: 2000-2024

Backtester checks:
  ✓ No look-ahead: weights[i] meets returns[i+1] (lag ≥ 1 day) ✓
  ✓ Financing: shorts cost 3% annually
  ✓ Costs: turnover × 20bps
  ✓ Sharpe: computed with probabilistic Sharpe (PSR)

Output:
  - Cumulative return: +4.2% annualized (log returns)
  - Sharpe (arithmetic): 0.62
  - Probabilistic Sharpe (2% threshold): 0.38 (not great, but non-random)
  - Max drawdown: -22%
  - Financing costs: -45bps annually
  - Net-of-cost Sharpe: 0.58
```

### Step 6: Out-of-Sample Validation
```
Call: walk_forward (Spec 0046)
Methodology:
  - Divide 24 years into 4-year train/test folds
  - Train model in fold t on 2000-2003
  - Test in fold t on 2004-2007 (no overlap)
  - Repeat for all folds

Results per fold:
  Fold 1 (2004-2007): Sharpe 0.45, +1.8% return
  Fold 2 (2008-2011): Sharpe 0.12, -0.1% return (financial crisis!)
  Fold 3 (2012-2015): Sharpe 0.68, +2.5% return
  Fold 4 (2016-2024): Sharpe 0.41, +1.2% return

Distribution:
  - Mean Sharpe: 0.41
  - Std Sharpe: 0.21
  - % positive folds: 75% (3/4)
  - Pooled PSR: 0.31 (borderline)

Interpretation: Strategy works, but regime-dependent (financial crisis hurt it)
```

## Phase 4: Validation & Governance (Week 5)

### Step 7: Backtest Review
```
Call: backtest_review
Checklist:
  ✓ No look-ahead (verified by backtester)
  ✓ Realistic costs (10bps + financing included)
  ✓ Out-of-sample validation (walk-forward results)
  ✓ Regime robustness (works in 3/4 folds)
  ⚠ Concern: Sharpe < 1.0 (crowded strategy? declining alpha?)

Recommendations:
  1. Monitor signal decay post-2024
  2. Consider macro overlay (boost in growth regimes, reduce in stagflation)
  3. Do not rely on historical crisis performance (2008 was outlier)

Status: Approved with caveats
```

### Step 8: Model Card & Governance
```
Call: model_card_drafter
Output: model_card.md

Title: Cross-Sectional Momentum Signal (6M Lag)

Assumptions:
  - Momentum persistence exists (6-month reversion is weak)
  - No market microstructure frictions > 20bps
  - Borrow costs: 3% annually (liquidity premium)

Limitations:
  - Poor performance during regime shifts (2008)
  - Declining alpha post-2015 (possibly crowded)
  - Sensitive to rebalance frequency (monthly assumed)

Fairness & Bias:
  - Survives delisting (not penny stocks)
  - Borrow availability varies by ticker (small-cap constraint)

Monitoring:
  - Signal drift: Is 6M momentum still predictive? (0021-signal-monitoring)
  - Performance: Compare to SPY; alert if underperforming > 500bps

Approval: [Your Name], Date: [Date]
```

## Phase 5: Integration into Portfolio (Weeks 6-7)

### Step 9: Portfolio Construction
```
Call: pm_orchestrator
Input: 
  - Momentum signal: long/short weights by ticker
  - Macro backdrop: current regime = "growth", EM allocation = 20%
  - Risk limits: max beta 1.2, max concentration 30% top-10

Portfolio construction (0007 QP):
  - Objective: Minimize portfolio variance
  - Subject to: expected return ≥ 8%, beta ≤ 1.2, concentration ≤ 30%
  - Constraints on momentum: long ≥ 0.4, short ≤ 0.1 (long bias)

Output: Target weights (500 stocks, 40% cash for limit compliance)
```

### Step 10: Risk Attribution
```
Call: factor_risk_model (0038)
Decomposition:
  - Equity beta: 65% of portfolio risk
  - Momentum factor: 20% of portfolio risk
  - Idiosyncratic: 15% of portfolio risk

Stress tests:
  - -10% equity shock: portfolio loss = -6.5%
  - +200bp credit spread: portfolio loss = -1.2%
  - Regime shift to stagflation: portfolio loss = -8.5%

Findings: Portfolio OK under base case; monitor regime shift risk.
```

### Step 11: Execution
```
Call: execution_scheduler (0012 Almgren-Chriss)
Constraints:
  - Market impact: 1bp per $1M traded
  - Execution window: 2 trading days
  - Market volatility: 15% (current)

Output: Trading schedule
  Day 1: Buy 60% of target positions (300 stocks)
  Day 2: Buy remaining 40% + rebalance small-cap

Estimated cost: 15bps of AUM
```

## Phase 6: Production & Monitoring (Week 8+)

### Step 12: Launch
```
Call: deployment_release
Checklist:
  ✓ Model card approved
  ✓ Decision log entry: "Approved for 500-stock long/short momentum, max beta 1.2"
  ✓ Monitoring setup: Alert if Sharpe < 0.3 (drift)
  ✓ Limits: Max short ratio 10%, max drawdown 20%

Go live: First rebalance scheduled for [date]
```

### Step 13: Ongoing Monitoring
```
Call: maintenance_monitoring + monitoring/model_signal_monitoring
Daily:
  - Portfolio risk: factor decomposition, stress loss
  - Signal IC: Is momentum still predictive? (rolling window)
  - Drawdown: Alert if > 10%

Monthly:
  - Attribution: What drove returns? (0038 factor model)
  - Signal drift: Calibration, decay, regime sensitivity (0021)
  - Rebalance: Execute via execution_scheduler

Alert triggers:
  - Signal IC < 0.03: Investigate decay
  - Sharpe < 0.3: Model review + potential parameter tuning
  - Regime shift: Notify portfolio team for macro overlay
```

## Summary

**Timeline:** 8 weeks from hypothesis to production
**Output:** Signal live, monitored, with governance trail
**Outcome:** 0.58 Sharpe net-of-cost, approved with risk caveats

**Key Learnings:**
1. Walk-forward shows strategy is robust (0.41 Sharpe) but regime-dependent
2. Backtest realistic (10bps costs + 3% financing included)
3. Model card honest about limitations (declining alpha, crowded strategy)
4. Governance trail complete (decision log, model card, risk review)

**Next:** Monitor signal drift; consider macro overlay for stagflation hedge.
