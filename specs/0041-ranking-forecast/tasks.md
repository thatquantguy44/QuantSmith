# Tasks: Cross-Sectional Ranking Forecast (Pairwise Ranking Loss)

- **Spec:** 0041-ranking-forecast (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-12

## Definition of Done (applies to every task)

- Standard-library only; no dependency added.
- `return_forecasting.py` is imported, never modified.
- Every ranking pair is verifiably within a single decision day.
- Deterministic: the same panel and seed always return the same result.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `train_ranker`, `RankingForecastRun`, `run_ranking_forecast`. | REQ-001, REQ-002, REQ-003, REQ-004, NFR-001, NFR-002 | done | Pairwise logistic (RankNet-style) loss; imports `LinearModel`/`evaluate`/`build_labels`/`FeatureStore`/`make_folds` from `return_forecasting.py` unmodified. |
| T-002 | Write `tests/test_ranking_forecast.py`. | REQ-001, REQ-002, REQ-003, REQ-004, NFR-003 | done | One test per acceptance criterion (AC-001 – AC-006). |
| T-003 | Wire catalogs and handoff docs. | REQ-005 | done | `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md`, `docs/handoff.md`, `docs/handoffs/future_features.md`, `docs/sdk_plan.md`. |
| T-004 | Run validation gates. | NFR-004 | done | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `readme-sync`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_separable_day_achieves_perfect_rank_AC_001` | done |
| AC-002 | `test_pairs_never_cross_days_AC_002` | done |
| AC-003 | `test_ranker_plugs_into_0006_evaluate_unmodified_AC_003` | done |
| AC-004 | `test_ranker_and_baseline_share_identical_folds_AC_004` | done |
| AC-005 | `test_deterministic_AC_005` | done |
| AC-006 | `test_ranker_matches_or_beats_pointwise_on_rank_only_signal_AC_006` | done |
| AC-007 | Direct inspection of `specs/README.md`, `src/quantsmith/pipelines/README.md`, root `README.md` | done |

## Follow-ups

- A listwise ranking loss (ListNet/NDCG-style), once this pairwise
  variant is trusted (carried as an open question in `spec.md`).
- A pair-sampling strategy for very large single-day cross-sections,
  should a production-scale panel need it (RISK-002).
