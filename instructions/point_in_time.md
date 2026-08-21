# Point-in-Time & Leakage Checklist

Look-ahead and leakage are the most common way quant work is wrong while looking
right. This checklist is the standard the SDK holds features, models, and
backtests to. It backs the `leakage-check` hook and the Feature Engineering,
Modeling, and Backtest Review agents.

The governing principle is constitution P4: **correct by construction**. Prefer a
design where leakage is impossible over a check that catches it after the fact.

## Definitions

- **Look-ahead:** using information that would not have been available at the
  decision time.
- **Leakage:** any path by which the target, the future, or out-of-sample data
  influences training, features, or a backtest signal.
- **Point-in-time (PIT):** each input is used only as of when it was actually
  knowable, including publication and revision lags. A source's PIT
  characteristics are registered once in `sources/<source-id>.yml`
  (`point_in_time.supports_asof`, `revision_policy`) so every feature or
  backtest drawing on it starts from a stated answer, not a fresh guess. See
  `instructions/data_source_catalog.md`.

## Feature Checklist

- [ ] Every input has a known availability timestamp, including publication lag.
- [ ] No feature uses data dated after the decision time it feeds.
- [ ] Rolling/aggregation windows look backward only (watch negative shifts).
- [ ] Backfill (`bfill`) is not used to fill values with future observations.
- [ ] Restated/revised data uses the original vintage, not the latest revision.
- [ ] Normalization/scaling is fit on training data only, then applied.
- [ ] The label/target is not present, directly or derived, among the features.

## Split & Validation Checklist

- [ ] Splits are time-ordered; no shuffling of time-series rows.
- [ ] An embargo/purge gap separates train and validation around the horizon.
- [ ] Cross-validation respects time order (e.g. walk-forward), not plain k-fold.
- [ ] Hyperparameter search does not select on the test set.
- [ ] The number of configurations tried is recorded (multiple-testing risk).

## Backtest Checklist

- [ ] Signals at time t use only information available at t.
- [ ] Execution assumes realistic fills and delays (no same-bar look-ahead).
- [ ] The universe is point-in-time (survivorship and listing bias controlled).
- [ ] Corporate actions and symbol changes are handled point-in-time.
- [ ] Transaction costs, slippage, and borrow are modeled.

## Common Leakage Smells (code)

- Negative shifts: `shift(-n)` pulls the future into the present.
- `bfill` / `fillna(method="bfill")`: fills gaps with later values.
- Whole-sample `fit`/`fit_transform` on a scaler before splitting.
- `train_test_split(..., shuffle=True)` on time-ordered data.
- Global statistics (mean, std, min, max) computed over the full sample.
- Joining a "latest" snapshot instead of an as-of/point-in-time join.

If a smell is unavoidable, record it as a `RISK-*` in the spec with the reason and
the mitigation, per constitution P8 (no silent trade-offs).
