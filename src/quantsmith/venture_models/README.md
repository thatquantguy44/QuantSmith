# Venture Predictive-Model Reference Baselines (Spec 0095)

Standard, dependency-free baselines for five venture model families, plus the validation harness
that makes the venture-specific traps structural. **Every result here is on synthetic data. Nothing in
this package may inform a decision**; `deployability` computes that from evidence and every catalog
model currently fails it.

| Module | Model family | Method | Trap it guards |
| --- | --- | --- | --- |
| `validation.py` | all | `as_of_view`, `out_of_time_split`, `assert_features_known`, `bootstrap_ci`, `deployability` | look-ahead, undated features, thin samples, unreviewed use |
| `survival.py` | round progression | Kaplan-Meier, Aalen-Johansen, cause-specific discrete-time hazards, calibration, Harrell C | competing risks (`1 - KM` overstates), censoring is not failure |
| `emergence.py` | technology emergence | Theil-Sen slope and MAD on log counts, Poisson noise floor, retrospective replay | reporting lag, noisy short baselines |
| `links.py` | network link | common neighbours, Jaccard, Adamic-Adar, preferential attachment, temporal AUC | leakage across the split, hubs, individuals (person nodes rejected) |
| `anomaly.py` | funding anomaly | seasonal median/MAD z | an incomplete latest period read as a collapse |
| `nowcast.py` | sector nowcast | chain-ladder on real-time vintages | evaluating on revised data |
| `synthetic.py` | tests | seeded generators with known truth | none; outputs are flagged synthetic |

```python
from quantsmith.venture_models import survival, synthetic, validation

subs = synthetic.simulate_competing_risks(4000, 1, {"next_round": .0015, "exit": .0004, "failure": .0006},
                                          "2018-01-01", "2022-12-31", "2025-12-31")
split = validation.out_of_time_split(subs, "2021-01-01", "2025-12-31")   # train only on what was known
model = survival.fit_hazard_model(split["train"], ["next_round", "exit", "failure"])
survival.predict_cif(model, (1.0,), "next_round", 365)
```

## What the checks showed (synthetic)

- Treating exits and failures as censoring overstated two-year incidence by 0.16 (0.666 against a true 0.503); Aalen-Johansen was within 0.01.
- An out-of-time calibration test found a real bug: a 365-day horizon was rounded up to 540 days. Fixed by interpolation.
- A tuned emergence threshold gave a 40% false-alarm rate on flat series; a Poisson noise floor gives about 5% with 98% detection and a median delay of 5 periods on Poisson-noise series.
- The emergence indicator is an onset detector: a long-running emergence fills the baseline and stops flagging.

## Before any model is used

Real-data validation on a point-in-time cohort with a dataset snapshot hash, out-of-time evaluation with
intervals against the stated baseline, and a named human reviewer. See `required_before_use` in
`knowledge/venture_intelligence/models.json`. Adopter-trained models register through `0026` and must beat
these baselines. Tests: `tests/test_venture_models.py`. Spec: `specs/0095-venture-predictive-model-baselines/`.
