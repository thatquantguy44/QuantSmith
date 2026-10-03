# Plan: Venture Predictive-Model Reference Baselines

- **Spec:** 0095-venture-predictive-model-baselines (`spec.md`)
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-03

> HOW. Requires the Draft spec; `tasks.md` tracks status.

## Approach

Build the harness before the models. `validation.py` makes the venture-specific traps structural
(no look-ahead via `as_of_view`, no undated features, no thin samples, no unreviewed deployment);
each model is the simplest standard estimator for its job; every test compares against hand
arithmetic or a generating process whose truth is known. Defaults follow theory, not tuning on the
generator (for example the Poisson noise floor in the emergence indicator, adopted after a tuned
threshold produced a 40% false-alarm rate on flat series).

## Architecture & Components

```
src/quantsmith/venture_models/
  validation.py   as_of_view, out_of_time_split, assert_features_known, bootstrap_ci, require_min_n, deployability
  survival.py     kaplan_meier, cumulative_incidence (Aalen-Johansen), fit_hazard_model, predict_cif,
                  calibration_by_group, harrell_c
  emergence.py    median, mad, theil_sen, growth_signal, retrospective_detection
  links.py        build_adjacency, scores, auc, temporal_link_split, evaluate_scorers, validate_nodes
  anomaly.py      robust_z, flag_anomalies
  nowcast.py      age_to_age_factors, completeness_curve, nowcast_ultimate, vintage, backtest_nowcast
  synthetic.py    seeded generators with known truth
knowledge/venture_intelligence/models.json   (+ implementation, validation_status, usable_for_decisions, limitations, evidence)
src/quantsmith/pipelines/venture_pack.py     (+ model governance rule using deployability)
tests/test_venture_models.py
```

## Interfaces & Data Contracts

- Subject: `id`, `formation_date`, `end_date`, `event` (`"censored"` or a cause), optional `features_vector`, `features`, `feature_known_at`.
- `cumulative_incidence(durations, events, cause) -> [{"time", "cif", "n_risk", "all_cause_survival"}]`.
- `predict_cif(model, features, cause, horizon_days)`: full intervals plus a proportional share of the next one; capped at the fitted range.
- `growth_signal(counts, lag_periods, recent, baseline, ...) -> {"status": emerging | not_emerging | not_assessable, "z", "poisson_floor", ...}`.
- `flag_anomalies(series, period, lag_periods, ...) -> [{"index", "value", "status": anomalous | normal | incomplete_period | not_assessable, ...}]`.
- `deployability(model) -> (bool, reasons)`; catalog fields `implementation`, `validation_status`, `usable_for_decisions`, `limitations`, `validation_evidence`, `required_before_use`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | PIT view, undated-feature rejection, vintages, minimum-n refusals |
| P5 Reversibility | yes | Additive |
| P6 Observability | partial | Results carry n, intervals, and not-assessable reasons |
| P9 Security & data | yes | Synthetic only; person nodes rejected |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `validation.py` | T-001 |
| REQ-002 | `survival.py` KM and AJ | T-002 |
| REQ-003 | hazard model, `predict_cif` | T-003 |
| REQ-004 | calibration, concordance, bootstrap | T-004 |
| REQ-005 | `emergence.py` | T-005 |
| REQ-006 | `links.py` | T-006 |
| REQ-007 | `anomaly.py` | T-007 |
| REQ-008 | `nowcast.py` | T-008 |
| REQ-009 | `deployability`, catalog, validator rule | T-009 |
| REQ-010 | `synthetic.py`, stdlib-only | T-010 |
| REQ-011 | gap, roadmap, indexes, run card | T-011 |
| NFR-001 | seeded generators, no globals | T-010 |
| NFR-002 | limitations text, notes in results | T-009, T-011 |
| NFR-003 | gates, full suite | T-012 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Competing risks | Aalen-Johansen and cause-specific hazards | `1 - KM` per cause | Quantified overstatement of more than 0.10 |
| Horizon inside an interval | Interpolate | Round up | Rounding up over-predicted 365-day incidence by 7-9 points |
| Emergence noise scale | MAD with Poisson floor | Tuned z threshold | Tuning chased the generator; the floor follows counting theory |
| Nowcast | Chain-ladder on real-time vintages | Regression on revised data | Revised data leaks information the nowcaster would not have had |
| Link prediction | Neighbourhood scores | Learned embeddings | No data to train or validate; scores are the floor |
| Deployment | Computed gate | A status label | A label can be typed; evidence has to exist |

## Validation Strategy

`tests/test_venture_models.py` (33 tests): hand and rational arithmetic, generating-process
recovery, degenerate and refusal cases, determinism; the pack validator for the catalog rule;
gates and the full suite.

## Rollout, Observability & Rollback

Additive. Rollback: delete the package and its tests and revert the catalog, validator, and doc edits.

## Open Questions

First real cohort and licensed database; the reviewer's minimum evidence standard.
