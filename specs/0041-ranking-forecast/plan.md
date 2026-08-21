# Plan: Cross-Sectional Ranking Forecast (Pairwise Ranking Loss)

- **Spec:** 0041-ranking-forecast (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-12

## Approach

Add one new, small module, `src/quantsmith/pipelines/ranking_forecast.py`,
that imports `return_forecasting.py`'s `LinearModel`, `evaluate`,
`build_labels`, `FeatureStore`, and `make_folds` and adds exactly one new
piece — a pairwise-ranking-loss training procedure — plus an orchestrator
that runs it alongside `0006`'s existing point-wise baseline on identical
folds. No existing file is modified.

## Architecture & Components

```text
ranking_forecast.py
  from return_forecasting import (
      LinearModel, evaluate, build_labels, FeatureStore, make_folds,
      Panel, Fold, EvalResult, FeatureConfig,
  )

  DayGroup = Sequence[Tuple[Sequence[float], float]]  # (features, target) sharing one decision day

  train_ranker(day_groups: Sequence[DayGroup], seed=0, epochs=300, lr=0.05) -> LinearModel
      # RankNet-style pairwise logistic loss, pairs formed *within* each
      # day_group only:
      #   for each day_group:
      #     for each ordered pair (i, j) in that group with y_i > y_j:
      #       s_i = w . x_i ; s_j = w . x_j
      #       p = sigmoid(s_j - s_i)          # >0.5 while i is mis-ranked below j
      #       grad += p * (x_j - x_i)          # pushes s_i up, s_j down
      #   w -= lr * grad / total_pairs, repeated for `epochs`
      # Deterministic: weight init seeded, no other randomness (AC-005).

  RankingForecastRun (dataclass)
      folds: List[Fold]
      ranker: List[EvalResult]
      pointwise: List[EvalResult]      # 0006's train_baseline, same folds
      mean_ranker_ic() / mean_pointwise_ic()

  run_ranking_forecast(panel, horizon=5, n_folds=3, embargo=1, seed=0, config=None)
      -> RankingForecastRun
      # 1. labels = build_labels(panel, horizon)        [0006, unmodified]
      # 2. store = FeatureStore(panel, config)           [0006, unmodified]
      # 3. samples = {(t,name): (features, y)}           [same assembly as run_forecast]
      # 4. folds = make_folds(decision_days, ...)         [0006, unmodified]
      # 5. per fold:
      #      train rows -> group by day -> day_groups -> train_ranker(...)
      #      train rows -> train_baseline(...)            [0006, unmodified]
      #      evaluate both on the fold's test rows via evaluate() [0006, unmodified]
```

## Interfaces & Data Contracts

No new data contract beyond `0006`'s own `PriceBar`/`Panel`. `DayGroup`
is a lightweight, module-local type alias over tuples `0006` already
produces internally (features, target) — not a new persisted schema.
`train_ranker`'s return type is exactly `return_forecasting.LinearModel`,
so it is a drop-in for `evaluate(model, features, targets, ...)` with no
adapter code.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Pairs are built by iterating within each day's own sample list — cross-day comparison is structurally impossible, not merely filtered out after the fact (NFR-003, AC-002). |
| P10 Honest reporting | yes | AC-006's comparison is explicitly framed (in `spec.md`'s Risks and this module's docstring) as a mechanism demonstration on a constructed fixture, never a backtested market claim (RISK-003). |
| P5 Reversibility | yes | Additive-only new module; `return_forecasting.py` is imported, never edited. |
| P8 No silent trade-offs | yes | RISK-001–RISK-003 name the epoch-budget sensitivity, the pairwise O(n²) cost, and the overclaiming risk directly. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `train_ranker`'s within-day pair construction | T-001 |
| REQ-002 | `train_ranker` returns a `LinearModel` | T-001 |
| REQ-003 | `run_ranking_forecast` trains ranker + `0006`'s baseline on identical folds | T-001 |
| REQ-004 | Seeded weight init, no other randomness | T-001 |
| REQ-005 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | T-003 |
| NFR-001 | Deterministic training given panel + seed | T-001 |
| NFR-002 | Standard-library only, imports only `return_forecasting` | T-001 |
| NFR-003 | Pair-construction test | T-002 |
| NFR-004 | Validation gates | T-004 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Ranking loss form | Pairwise logistic (RankNet-style) | Listwise (ListNet/NDCG) | Smallest change that isolates the point-wise-vs-rank-objective distinction; a listwise variant is a larger, separately-scoped follow-up (Non-Goals). |
| Reuse vs. reimplement | Import `0006`'s `LinearModel`/`evaluate`/`build_labels`/`FeatureStore`/`make_folds` directly | Copy/adapt them into the new module | Matches this session's composition-not-reimplementation precedent (`0034`–`0036` on `0013`); a duplicated `evaluate` could silently drift from `0006`'s own metric definition. |
| Comparison scope | Ranker vs. `0006`'s point-wise baseline only | Ranker vs. baseline *and* challenger (gradient-descent linear model) | The baseline (closed-form ridge) and the ranker are the cleanest apples-to-apples pair — both linear scorers, differing only in loss function; adding the challenger (already itself a gradient-descent point-wise model) would muddy which axis of comparison (architecture vs. objective) explains any IC difference. |

## Validation Strategy

`tests/test_ranking_forecast.py`, one test per acceptance criterion
(AC-001 through AC-007), matching this session's per-AC test naming
convention. AC-002/NFR-003 asserts pair membership directly (not just
behavior) by exposing the pair-construction step in a form the test can
inspect. Then
`hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index readme-sync`,
the full `pytest tests/ -q`, and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is
reverting the single commit; `return_forecasting.py` is never modified.

## Open Questions

- Should a future spec add a listwise ranking loss once this pairwise
  variant is trusted? (Carried from `spec.md`.)
