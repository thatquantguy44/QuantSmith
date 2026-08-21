# Spec: Cross-Sectional Ranking Forecast (Pairwise Ranking Loss)

- **ID:** 0041-ranking-forecast
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-12

## Problem & Context

`specs/0006-ml-return-forecasting/` (`return_forecasting.py`) trains its
baseline and challenger with **point-wise** regression loss (ridge /
gradient-descent MSE against the de-meaned forward-return label), then
scores them with cross-sectional rank IC (`evaluate`'s `_spearman`). That
mismatch is a known, common gap in return forecasting: a model trained
to minimize point-wise error is not directly trained to get the
cross-sectional *order* right, which is what a long/short selection
process (rank the names, go long the top decile, short the bottom)
actually consumes. `docs/handoffs/future_features.md`'s sole remaining
`P0` line names exactly this gap — "additional ML/DL examples" beyond
`0006`'s point-wise baseline/challenger — and a pairwise ranking-loss
variant is the natural first one: it changes only the training
objective, reusing every other piece of `0006`'s already-shipped,
leakage-safe machinery unmodified.

## Goals

- Add `src/quantsmith/pipelines/ranking_forecast.py`: `train_ranker`, a
  linear scorer trained with a pairwise (RankNet-style logistic) ranking
  loss over same-day pairs only — the score should put a higher-labeled
  name above a lower-labeled name *within its own cross-section*, never
  comparing names across different decision days.
- Compose, never reimplement, `0006`'s already-shipped pieces: reuse
  `build_labels`, `FeatureStore`, `make_folds`, `evaluate`, and
  `LinearModel` from `return_forecasting.py` exactly as they are —
  `train_ranker` only replaces the *training* step, matching how `0034`
  composed `0013`'s MILP with `0007`'s QP instead of rewriting either.
- Add `run_ranking_forecast`: an orchestrator that trains **both** the
  ranker and `0006`'s existing point-wise `train_baseline` on the
  *identical* folds and samples, evaluating both with `0006`'s own
  `evaluate`, so the two training objectives are compared apples-to-
  apples on the metric (rank IC) that a ranking loss is meant to
  improve.
- Demonstrate, with a deterministic synthetic panel where the true
  signal is rank-only (feature order determines label order, but label
  *magnitude* carries noise a point-wise loss would chase), that the
  ranker's held-out rank IC is at least as good as the point-wise
  baseline's — the concrete case a ranking loss earns its keep.

## Non-Goals

- No new label definition, feature set, validation-fold design, or
  evaluation metric — this spec is scoped to the *training objective*
  only; everything else is `0006`'s contract, reused unmodified (Non-
  Goal boundary mirrors `0034`'s explicit "does not modify
  `optimization_solvers.py` or `portfolio_construction.py`").
- No listwise ranking loss (e.g. ListNet, LambdaMART-style NDCG
  optimization) — pairwise logistic is the smallest ranking-loss variant
  that demonstrates the point-wise-vs-rank-objective distinction; a
  listwise variant is a natural, separately-scoped follow-up once this
  one is trusted.
- No promotion logic (which model "wins" and gets deployed) — `0006`'s
  own REQ-005 promotion-bar language stays that spec's concern; this
  spec only produces a third, directly comparable candidate.
- No deep-learning ranking architecture (e.g. a neural pairwise/listwise
  net) — the linear scorer is the reference stand-in, exactly matching
  `0006`'s own precedent of a linear closed-form baseline and a linear
  gradient-descent "challenger" standing in for a real GBT/DL model.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `train_ranker` shall train a linear scorer by gradient descent on a pairwise logistic ranking loss, forming preference pairs only from samples sharing the same decision day — never a pair spanning two different days. | must |
| REQ-002 | `train_ranker`'s output shall be a `return_forecasting.LinearModel` (or structurally identical scorer), so it plugs directly into `0006`'s existing `evaluate` without any new evaluation code. | must |
| REQ-003 | `run_ranking_forecast` shall train the ranker and `0006`'s `train_baseline` on identical folds and samples (reusing `build_labels`, `FeatureStore`, `make_folds` unmodified) and evaluate both with `0006`'s `evaluate`. | must |
| REQ-004 | Given a fixed seed, `train_ranker` and `run_ranking_forecast` shall be fully deterministic — identical inputs always produce identical weights and evaluation results. | must |
| REQ-005 | `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md` shall list the new module and its spec. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Reproducibility | The same day-grouped samples and seed always produce the same trained weights and evaluation metrics. |
| NFR-002 | Dependency isolation | Standard-library only, consistent with `return_forecasting.py` and the rest of `pipelines/`. |
| NFR-003 | No cross-day leakage in pairs | Every pair used in the ranking loss is verified to come from a single decision day, checked directly in tests, not assumed. |
| NFR-004 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `readme-sync` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a single day's cross-section with features perfectly rank-correlated with targets (a separable synthetic case), when `train_ranker` runs for enough epochs, then the resulting scores' rank order exactly matches the targets' rank order (Spearman rank IC of 1.0). | REQ-001 |
| AC-002 | Given samples spanning multiple decision days, when `train_ranker` forms its training pairs, then every pair's two samples share the same decision day (asserted directly, not inferred from behavior). | REQ-001, NFR-003 |
| AC-003 | Given a trained ranker, when its `.predict` is called via `0006`'s `evaluate`, then it runs unmodified and returns a well-formed `EvalResult` — no new evaluation code is exercised. | REQ-002 |
| AC-004 | Given `run_ranking_forecast` on a panel, when it runs, then the ranker and the point-wise baseline are trained and evaluated on identical fold train/test day sets. | REQ-003 |
| AC-005 | Given the same panel and seed, when `run_ranking_forecast` runs twice, then both runs' fold-level results (ranker and baseline) are identical. | REQ-004, NFR-001 |
| AC-006 | Given a synthetic panel where label *rank* is a clean function of a feature but label *magnitude* carries added noise, when `run_ranking_forecast` runs, then the ranker's mean held-out rank IC is greater than or equal to the point-wise baseline's. | REQ-003 |
| AC-007 | Given `specs/README.md`, `src/quantsmith/pipelines/README.md`, and root `README.md`, when inspected, then each lists spec `0041` and `ranking_forecast.py`. | REQ-005 |

## Data & Dependencies

No data dependencies beyond `0006`'s own (a `Panel` of `PriceBar`s).
Standard-library only.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Gradient descent on the pairwise loss may not fully converge within a fixed epoch budget on noisy real data, understating the ranker's advantage. | AC-006's comparison could be sensitive to the epoch/learning-rate choice on a specific synthetic fixture. | AC-001's separable single-day case gives a convergence sanity check independent of noise; AC-006 uses a deterministic, fixed-seed fixture so the result is reproducible even if not universally generalizable — a known, disclosed scope limit, not a claim of general superiority. |
| RISK-002 | Pairwise loss is O(pairs-per-day²) in the worst case; a very large single-day cross-section could be slow. | Training cost grows quadratically with names-per-day. | Explicitly out of scope to optimize (no capacity claim made); the reference panels here are small, matching `0006`'s own reference-scale precedent. A production implementation would sample pairs rather than enumerate all of them. |
| RISK-003 | A reader could mistake AC-006's "ranker beats baseline on this fixture" for a general claim that ranking loss always beats point-wise loss on real markets. | Overclaiming a narrow, synthetic demonstration as a market finding. | `plan.md` and this module's docstring state explicitly that AC-006 demonstrates the *mechanism* (a rank-only signal favors a rank objective) on a constructed fixture, not a backtested market claim — honest-reporting discipline (P10). |

## Assumptions & Open Questions

- Assumption: composing `0006`'s existing `build_labels`/`FeatureStore`/
  `make_folds`/`evaluate`/`LinearModel` unmodified is the right scope,
  matching this session's established composition-not-reimplementation
  precedent (`0034`–`0036` on `0013`).
- Open question: should a future spec add a listwise ranking loss
  (ListNet/NDCG-style) once this pairwise variant is trusted, per the
  Non-Goals note?

## Exceptions

None.
