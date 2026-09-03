# Factory Run Card

Fill in one copy of this template per factory run and hand it to the
Quant Factory Agent (`agents/quant_factory/`). Every field must be
completed before the agent constructs the `FactorySpec`.

---

## Run metadata

| Field | Value |
| --- | --- |
| `run_id` | *(unique string, e.g. `run_20260903_momentum_v3`)* |
| `seed` | *(integer, e.g. `42`)* |
| `deadline_seconds` | *(float or `inf` — wall-clock budget per lane)* |
| `ledger_path` | *(path to the append-only JSONL ledger, e.g. `factory_ledger.jsonl`)* |

---

## Convergence settings

| Field | Value |
| --- | --- |
| `convergence_mode` | *(one of `best_of_n` / `all_required` / `first_to_pass`)* |
| `n_best` | *(integer ≥ 1; used only by `best_of_n` — number of top lanes to approve)* |
| `pass_threshold` | *(float in (0, 1]; a lane's gate score must be ≥ this to pass)* |

**Convergence mode rationale:** *(why this mode for this run?)*

For `first_to_pass`: declare the priority ordering of lanes below (the
lane listed first has highest priority; the first to pass wins):

1. *(lane_id)*
2. *(lane_id)*
3. ...

---

## Gate thresholds

| Metric | Threshold |
| --- | --- |
| `min_sharpe` | *(float, e.g. `0.8`)* |
| `max_drawdown` | *(float, negative convention, e.g. `-0.15` for 15% max drawdown)* |
| `min_annual_return` | *(float, e.g. `0.05` for 5%)* |

---

## Lanes

One block per lane. Use as many as needed.

### Lane 1

| Field | Value |
| --- | --- |
| `lane_id` | *(unique string, e.g. `lane_momentum_rsi`)* |
| `hypothesis` | *(one-sentence statement of the alpha thesis)* |
| `feature_set` | *(comma-separated feature names, e.g. `rsi_14, mom_20, vol_21`)* |
| `model_tag` | *(model identifier, e.g. `ridge`, `xgb_v2`, `lstm_daily`)* |
| `backtest_config` | *(key: value pairs — lookback, universe, cost model, …)* |

### Lane 2

| Field | Value |
| --- | --- |
| `lane_id` | |
| `hypothesis` | |
| `feature_set` | |
| `model_tag` | |
| `backtest_config` | |

*(add more Lane blocks as needed)*

---

## Expected deliverables

- A `FactoryDecision` struct with per-lane scores and statuses.
- One JSONL entry appended to `ledger_path`.
- A human-readable run summary in the format specified in
  `agents/quant_factory/instructions.md`.
- For every approved lane: a backtest tear-sheet review and leakage-gate
  result before the analyst issues a ship decision.

---

## Notes / open questions

*(anything the agent should know — data availability, known data gaps,
prior run references, risk budget context)*
