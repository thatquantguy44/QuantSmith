# Spec: Venture Predictive-Model Reference Baselines

- **ID:** 0095-venture-predictive-model-baselines
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-03

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`; follows `0091` (fund analytics), which split these models out. Adopter-trained models register through `0026`; the baselines here are the floor they must beat.

## Problem & Context

`0083` cataloged five predictive model families (round-progression survival, technology
emergence, network link prediction, funding-flow anomaly, sector nowcast) as design only.
Venture data is hostile to modelling: databases backfill, survivors are over-represented,
recent periods are always incomplete, and "no news" is not failure. A model built on the usual
quant pattern would look excellent and mean nothing. What is needed first is not a clever model
but a validation harness that makes the traps structural, plus simple, standard baselines that
any later model must beat, and a gate that stops either from informing a decision before real
evidence exists.

## Goals

- Point-in-time tools that rebuild a cohort as it was known on a date, so training never sees an outcome the world had not shown.
- Standard, checkable baselines for each family, validated against hand arithmetic and known generating processes.
- Out-of-time evaluation with calibration, concordance, intervals, and honest refusal of thin samples.
- A deployability gate computed from evidence, with every model currently not usable for decisions.

## Non-Goals

- No model trained or validated on real companies, funds, or documents; every dataset here is synthetic.
- No claim of predictive value for any real technology, company, or market.
- No person-level link prediction or founder modelling.
- No machine-learning libraries, embeddings, or network access.
- No change to the `0026` plugin contract or to credit-style scoring rules.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall provide `as_of_view` (outcomes after a date become censoring at that date; later-formed subjects absent; inputs unmodified), `out_of_time_split` (train on the view at the split date, test on later-formed cohorts followed to the observation end), and `assert_features_known` (reject any feature learned after formation or with no known date). | must |
| REQ-002 | The SDK shall provide Kaplan-Meier with Greenwood variance and a log-log interval and Aalen-Johansen cumulative incidence for competing causes, matching hand-computed answers and recovering a known generating process, and shall document that treating competing causes as censoring overstates incidence. | must |
| REQ-003 | The SDK shall fit cause-specific discrete-time logistic hazards with ridge regularization, predict cumulative incidence at any horizon without rounding a mid-interval horizon up to the interval boundary, cap horizons at the fitted range, and refuse thin data or a cause with no events. | must |
| REQ-004 | The SDK shall evaluate out of time with calibration by prediction group (a group never followed to the horizon is not assessable, never zero), a cause-specific concordance that refuses too few comparable pairs and equals 0.5 for a constant baseline, and a deterministic bootstrap interval that refuses small samples. | must |
| REQ-005 | The SDK shall provide an emergence indicator using Theil-Sen slopes and the median absolute deviation on log counts, dropping incomplete trailing periods, flooring the noise scale at the Poisson sampling noise, declining to assess short or low-volume series, and a period-by-period retrospective replay that reports detection rate, delay, and false-alarm rate; it shall state that it is an onset detector. | must |
| REQ-006 | The SDK shall provide organization-level link prediction with common-neighbour, Jaccard, Adamic-Adar, and preferential-attachment scores, a temporal split in which every positive appeared only after the split and no negative is a known or later link, tie-aware AUC, a random and a degree baseline, and rejection of person nodes and of too few positives. | must |
| REQ-007 | The SDK shall provide a seasonal robust-z anomaly indicator in which the latest periods are `incomplete_period` and never anomalous, early periods without enough history are `not_assessable`, and the scale is floored. | must |
| REQ-008 | The SDK shall provide a chain-ladder nowcast with volume-weighted development factors, a completeness curve, real-time vintages in which an entry exists only if its lag has elapsed, and a backtest against a first-report baseline and a last-complete-quarter baseline that refuses too few targets. | must |
| REQ-009 | The SDK shall compute deployability from evidence (status validated, not synthetic-only, usable flag, reviewed record, and at least one complete real-data evidence entry with a snapshot hash, out-of-time period, metrics, and named reviewer, where `None` is never a name); record the fields in the model catalog; mark every current model not usable; and make the pack validator reject a model marked usable that fails the gate or lacks the fields. | must |
| REQ-010 | The SDK shall provide seeded synthetic generators with known truth, flag every output as synthetic, and keep all code standard-library only and deterministic. | must |
| REQ-011 | The SDK shall retitle the predictive-models gap as an unvalidated-on-real-data gap, update the roadmap and indexes, and update the run card. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Identical inputs and seeds give identical outputs; no global random state; no third-party imports. |
| NFR-002 | Honesty | Every result and document states that validation is synthetic only; no number is presented as real accuracy. |
| NFR-003 | Gates | All gates with enforcement on pass and no existing test regresses. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given cohorts with future outcomes, when viewed as of a date, then those outcomes are censored, later cohorts are absent, and inputs are unchanged; and the out-of-time split trains only on what was known, and a late or undated feature raises. | REQ-001 |
| AC-002 | Given a five-subject example, when Kaplan-Meier runs, then survival, Greenwood variance, and ties match hand computation, and an empty input raises. | REQ-002 |
| AC-003 | Given four subjects with two causes, when Aalen-Johansen runs, then incidences are 0.5 and 0.25, they sum with survival to one, and naive `1 - KM` gives 5/8; and on a generated cohort the estimator recovers the true incidence while the naive estimate overstates it by more than 0.10. | REQ-002 |
| AC-004 | Given a generated cohort with a covariate effect, when the hazard model is fitted, then it converges, recovers the covariate log-hazard ratio and the incidence, interpolates a mid-interval horizon, caps beyond the range, and refuses thin data or an eventless cause. | REQ-003 |
| AC-005 | Given an out-of-time split, when evaluated, then calibration differences are small, concordance exceeds 0.5 while a constant baseline equals 0.5, an unfollowed group is not assessable, and thin samples raise. | REQ-004 |
| AC-006 | Given hand-computed Theil-Sen and MAD cases and Poisson series, when run, then slopes match, a planted emergence is flagged, flat, short, and low-volume series are not, trailing zeros and surges are ignored, and the replay reports at least 90% detection and at most 10% false alarms with a bounded delay. | REQ-005 |
| AC-007 | Given a small graph and a block graph, when scored, then neighbourhood scores and AUC with ties match hand computation, the temporal split leaks nothing, structure beats degree and random, and person nodes and thin positives are rejected. | REQ-006 |
| AC-008 | Given hand-computed robust-z cases and a series ending in a partial period, when flagged, then the partial period is incomplete and never anomalous, a planted spike is flagged, and early periods are not assessable. | REQ-007 |
| AC-009 | Given a deterministic reporting pattern, when chain-ladder runs, then factors, completeness, and nowcasts are exact, vintages show only elapsed lags, the backtest is exact and beats both baselines, and on noisy patterns it still beats them without being exact. | REQ-008 |
| AC-010 | Given model records, when deployability is computed, then each missing condition blocks it, `None` as a hash, period, or reviewer blocks it, no catalog model is usable today, and the validator rejects a model marked usable without evidence or missing the fields. | REQ-009 |
| AC-011 | Given repeated runs and the source, when inspected, then outputs are identical and there are no third-party imports or global seeding. | REQ-010, NFR-001 |
| AC-012 | Given the repository, when gates and the full suite run, then no gate has findings, the gap is retitled, the roadmap and indexes name this spec, and no previously passing test fails. | REQ-011, NFR-002, NFR-003 |

## Data & Dependencies

Depends on `0083` (model catalog, conventions), `0088` (`known_at`, cohort formation), `0091` (fund simulation, the catalog's other
reference implementation), and `0026` for adopter-trained models. Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Survivorship or backfill leaks into training. | Inflated accuracy. | `as_of_view` censors future outcomes; `assert_features_known`; out-of-time split. |
| RISK-002 | Competing events treated as censoring. | Overstated incidence. | Aalen-Johansen; a test that quantifies the overstatement. |
| RISK-003 | Late-reporting periods read as declines or surges. | False anomalies. | Incomplete periods dropped or marked; vintage-based nowcast. |
| RISK-004 | A horizon rounded up to an interval boundary. | Over-prediction. | Interpolation; test pins it (found by the out-of-time calibration test). |
| RISK-005 | Synthetic success read as real validity. | False confidence. | Catalog marks `synthetic_only`; deployability false; every output states it. |
| RISK-006 | Emergence indicator trusted after it stops flagging. | Missed long-running growth. | Documented as an onset detector; baseline leakage test. |
| RISK-007 | Link prediction drifts to individuals. | Privacy harm. | Person nodes rejected. |
| RISK-008 | Thin samples support confident estimates. | Overfit. | Minimum-n refusals and bootstrap intervals. |

## Assumptions & Open Questions

- Assumption: simple standard estimators, checked against hand arithmetic and known processes, are the right first floor; a learned model is accepted only if it beats them out of time on real data.
- Open question: which licensed database and which Southeast Asia cohort will supply the first real, point-in-time dataset (`knowledge_local/venture_intelligence/cohorts/`).
- Open question: the minimum real-data evidence the reviewer will accept (cohort size, out-of-time period length).

## Exceptions

None.
