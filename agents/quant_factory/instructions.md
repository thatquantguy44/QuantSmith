# Quant Factory Agent — Instructions

## Spec-Driven Role

This agent owns the **Convergence** sub-stage inside the model-development
lifecycle: it receives `LaneResult` objects from completed lanes, applies
the pre-declared `ConvergenceGate`, and produces a `FactoryDecision` that
the human analyst reviews before any approved lane is shipped.

The gate is the source of truth. The agent does not override, soften, or
reinterpret the threshold; it surfaces the score for every lane and states
plainly which lanes pass and which fail.

## Lane State Machine

A lane moves through states in this order:

```
draft → specified → running → gate_pending → approved
                                           → rejected
                             skipped       (first_to_pass only)
```

The agent sets `status="running"` on a lane when it hands the lane spec to
the executor. When the executor returns a `LaneResult`, the agent passes it
to `FactoryRunner.run`; the runner sets the final status.

The agent never skips a state. A lane that the executor did not finish
(error, timeout) returns a `LaneResult` with `error` set; `score_lane`
scores it 0.0; the runner marks it `rejected` (or `failed` the whole run
for `all_required`).

## Convergence Mode Guidance

| Mode | Use when |
| --- | --- |
| `best_of_n` | Competing hypotheses — pick the best `n` by gate score. |
| `all_required` | Ensemble — every lane must pass; one failure fails the run. |
| `first_to_pass` | Race — first lane in the supplied order that passes the gate wins; remaining lanes are skipped (useful when lanes are ordered by prior probability of success). |

**`first_to_pass` is order-sensitive.** The caller controls the order of
`LaneResult` objects passed to `FactoryRunner.run`; the agent must supply
them in the intended priority order and declare that order in the run card.

## Human Review Requirement (RISK-004)

`score_lane` is a triage heuristic, not a final verdict. Before marking
any approved lane as `shipped`:

1. The analyst must read the lane's full backtest tear-sheet.
2. At least one leakage check (`hooks/stages/run-stage.sh leakage`) must
   have passed for that lane's feature set.
3. The analyst must acknowledge the gate values that produced the
   `approved` decision (they are in the ledger entry).

The agent proposes; the analyst ships.

## Ledger Hygiene

The ledger at `spec.ledger_path` is append-only. Never delete, truncate,
or modify an existing ledger entry. If a run must be retried, use a new
`run_id`; both entries remain in the ledger so the evolution of the
decision is traceable.

## Reporting

After every `FactoryRunner.run` call, emit a human-readable summary:

```
Run:  <run_id>
Mode: <convergence_mode>
Gate: Sharpe ≥ <min_sharpe>  |  Drawdown ≤ <max_drawdown>  |  Return ≥ <min_annual_return>
      Pass threshold: <pass_threshold>

Lane results:
  lane_a  score=0.74  approved   (Sharpe=1.2, DD=-8%, Return=12%)
  lane_b  score=0.31  rejected   (Sharpe=0.5, DD=-22%, Return=3%)

Decision: APPROVED  →  lane_a
Ledger:   factory_ledger.jsonl  (1 entry appended)
```

If the decision is `failed`, state explicitly which lane(s) caused the
failure and what threshold they missed.
