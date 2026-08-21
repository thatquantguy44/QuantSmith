# Compliance Officer Role

## What You Do

You own model governance, decision documentation, risk limits, and audit trails. Your job is to ensure all decisions are defensible, traceable, and compliant with policy.

## Your Core Agents

**Governance & Documentation:**
- `role_operations/model_card_drafter/` — structures model assumptions, limitations, and bias analysis
- `role_operations/audit_trail_keeper/` — maintains decision logs with timestamps, rationale, exceptions
- `role_operations/governance_readiness_checklist/` — validates a model against governance checklist before production
- `role_operations/decision_log_keeper/` — persistent workflow memory for domain decisions

**Risk & Policy Monitoring:**
- `risk/` — monitors exposure vs. limits; flags breaches
- `alerts/alert_router/` — routes alerts by severity; you review critical ones
- `alerts/incident_notification/` — escalates incidents; you own the post-mortem
- `backtest_review/` — reviews strategy backtests for bias, costs, robustness

**Model & Signal Monitoring:**
- `monitoring/model_signal_monitoring/` — detects signal drift, regime shifts
- `role_operations/second_look_backtest_reviewer/` — provides independent backtest review before promotion

**Handoff Partners:**
- ← **Portfolio Manager** for portfolio decisions + risk limit changes
- ← **Quant Researcher** for new signal/model development
- ← **Risk Manager** for limit breaches + escalations
- ← **Data Engineer** for data provenance issues + SLA breaches

## Your Key Specs

| Spec | What | Use When |
| --- | --- | --- |
| `0030-role-operations-phase3` | Model governance agents + decision log | Structuring governance for new strategies |
| `0044-backtesting` | Backtest integrity check | Validating strategy has no look-ahead |
| `0046-walk-forward` | Out-of-sample robustness | Confirming strategy works across regimes |
| `0025-data-provenance-guardrail` | Real-data-first + synthetic disclosure | Flagging synthetic data in production |
| `0047-downstream-contract` | Schema versioning + consumer contracts | Managing model updates across systems |

## Your Quality Gates

**Critical to you:**
- `backtest` — backtests must be integrity-checked
- `leakage` — advisory but important for understanding point-in-time correctness
- `role-context` — local policy constraints wired into automation
- `alert-contract` — alerts routed correctly, not suppressed

**Informational:**
- `data-provenance` — synthetic data disclosed
- `doc-counts`, `agent-catalog`, `spec-index` — institutional knowledge tracked

## Governance Workflow

```
When a new strategy or model is proposed:
  1. Quant researcher provides return forecasts + backtests
     ↓
  2. Model card review:
     - Assumptions (market regime, data quality, etc.)
     - Limitations (crowded strategy? regime-dependent?)
     - Bias analysis (survivor bias? look-ahead?)
     ↓
  3. Backtest review (0044/0046):
     - Look-ahead check
     - Financing cost realism
     - Walk-forward robustness across folds
     ↓
  4. Risk limits review:
     - Concentration limits (single-position cap, sector caps)
     - Factor exposure limits (beta, duration, vega)
     - Max drawdown + stress loss caps
     ↓
  5. Approval → sign off in decision log
     ↓
  6. Promotion to production
     ↓
  7. Post-launch monitoring:
     - Signal drift (0021)
     - Performance attribution
     - Limit breach escalation

If limit breached or model degrades:
  1. Alert routed to risk manager
  2. Investigation: regime shift? data issue? model failure?
  3. Decision log entry explaining action taken (rebalance/suspend/update)
```

## Common Workflows

- **"Approve a new strategy"** → governance_readiness_checklist → model_card review → backtest_review → sign off
- **"A model is drifting"** → signal_monitoring (0021) shows decay → decision log entry → model review → recommend retraining
- **"We hit a concentration limit"** → alert triggered → decision log entry → rebalancing recommendation to PM
- **"Audit our decisions from Q2"** → audit_trail_keeper → export decision log → regulatory review
- **"Is this synthetic data in our backtest?"** → data_provenance guardrail (0025) → flag and require disclosure

## Handoff Details

**To Portfolio Manager:**
- "I've approved this strategy for production; limits are [X,Y,Z]"
- "If you breach these limits, I need a written decision entry (decision_log.md) explaining why"

**To Quant Researcher:**
- "Before development: write a model card draft"
- "Before production: I need model_card_drafter output + backtest_review sign-off"
- "Model assumes equities in normal regime; if regime shifts, notify me immediately"

**To Risk Manager:**
- "New strategy is approved; these are the limits"
- "If concentration hits 110% of limit, escalate to me immediately"

**From Everyone:**
- Decisions, assumptions, and exceptions logged in decision_log.md
- Model cards for all production strategies
- Backtests with financing costs and walk-forward validation

## Specs You Reference But Don't Own

- `0006-ml-return-forecasting` (quants use this; you review the model card)
- `0044-backtesting` (quants use this; you review the output)
- `0046-walk-forward` (quants use this; you check fold distribution)
- `0038-factor-risk-model` (risk uses this; you review concentration/stress)

## What You Don't Own

- Strategy development (that's the quant team)
- Portfolio construction (that's PM)
- Risk monitoring (that's risk manager; you set the policy they enforce)
- Data engineering (that's data engineer; you check provenance)

## Critical Principles

1. **Traceability** — every decision logged with date, rationale, exception (if any)
2. **Honesty** — model cards state limitations, backtests disclose costs and look-ahead checks
3. **Limits enforced** — breaches are escalated and logged, never silent
4. **Real data first** — synthetic data disclosed; never misrepresent in production
5. **Reversibility** — decisions are documented so you can explain them to auditors
