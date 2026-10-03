"""Acceptance tests for spec 0095 -- venture predictive-model reference baselines.

All data are synthetic (spec 0025). Expected values come from hand or exact rational arithmetic, or from a
known generating process; passing them shows the arithmetic is right, not that a model works on real companies.
"""

from __future__ import annotations

import copy
import math
from fractions import Fraction
from pathlib import Path

import pytest

from quantsmith.pipelines.venture_pack import load_pack, validate_pack
from quantsmith.venture_models import anomaly, emergence, links, nowcast, survival, synthetic, validation
from quantsmith.venture_models.validation import LeakageError, SmallSampleError

ROOT = Path(__file__).resolve().parents[1]
RATES = {"next_round": 0.0015, "exit": 0.0004, "failure": 0.0006}


def _dur(subs):
    return [(validation.day(s["end_date"]) - validation.day(s["formation_date"])).days for s in subs]


# ---------------------------------------------------------------- AC-001 point in time
def test_ac001_as_of_view_censors_outcomes_not_yet_known():
    subs = [{"id": "a", "formation_date": "2020-01-01", "end_date": "2021-06-01", "event": "next_round"},
            {"id": "b", "formation_date": "2020-03-01", "end_date": "2020-05-01", "event": "failure"},
            {"id": "c", "formation_date": "2021-01-01", "end_date": "2021-02-01", "event": "exit"}]
    snapshot = copy.deepcopy(subs)
    view = {s["id"]: s for s in validation.as_of_view(subs, "2021-01-01")}
    assert subs == snapshot                                          # inputs untouched
    assert view["a"]["event"] == "censored" and view["a"]["end_date"] == "2021-01-01"   # event is in the future
    assert view["b"]["event"] == "failure"                           # already known
    assert "c" in view and view["c"]["event"] == "censored"          # formed on the as-of day, outcome later
    assert "c" not in {s["id"] for s in validation.as_of_view(subs, "2020-12-31")}      # not yet formed
    with pytest.raises(ValueError):
        validation.as_of_view([{"id": "x", "formation_date": "2020-02-01", "end_date": "2020-01-01", "event": "exit"}], "2021-01-01")


def test_ac001_out_of_time_split_trains_only_on_what_was_known():
    subs = synthetic.simulate_competing_risks(300, 4, RATES, "2018-01-01", "2022-12-31", "2025-12-31")
    sp = validation.out_of_time_split(subs, "2021-01-01", "2025-12-31")
    assert all(s["formation_date"] <= "2021-01-01" for s in sp["train"])
    assert all(s["end_date"] <= "2021-01-01" for s in sp["train"])             # nothing from after the split
    assert all(s["formation_date"] > "2021-01-01" for s in sp["test"])
    assert any(s["event"] == "censored" for s in sp["train"])
    with pytest.raises(ValueError):
        validation.out_of_time_split(subs, "2026-01-01", "2025-12-31")
    with pytest.raises(SmallSampleError):
        validation.out_of_time_split(subs, "2010-01-01", "2025-12-31")


def test_ac001_features_must_be_known_by_formation():
    ok = [{"id": "a", "formation_date": "2020-01-01", "features": {"x": 1}, "feature_known_at": {"x": "2019-12-01"}}]
    validation.assert_features_known(ok)
    late = [{"id": "a", "formation_date": "2020-01-01", "features": {"x": 1}, "feature_known_at": {"x": "2020-02-01"}}]
    with pytest.raises(LeakageError, match="after formation"):
        validation.assert_features_known(late)
    undated = [{"id": "a", "formation_date": "2020-01-01", "features": {"x": 1}, "feature_known_at": {}}]
    with pytest.raises(LeakageError, match="no known_at"):
        validation.assert_features_known(undated)
    assert validation.assert_features_known(synthetic.simulate_competing_risks(50, 1, RATES, "2020-01-01", "2020-12-31", "2022-01-01")) is None


# ---------------------------------------------------------------- AC-002 Kaplan-Meier
def test_ac002_kaplan_meier_hand_computed():
    steps = survival.kaplan_meier([1, 2, 3, 4, 5], [True, False, True, False, True])
    assert [s["time"] for s in steps] == [1, 3, 5]
    f = Fraction
    s1, s3 = f(4, 5), f(4, 5) * f(2, 3)
    assert steps[0]["survival"] == pytest.approx(float(s1)) and steps[1]["survival"] == pytest.approx(float(s3))
    assert steps[2]["survival"] == 0.0
    g1 = f(1, 5 * 4)
    g3 = g1 + f(1, 3 * 2)
    assert steps[0]["greenwood_var"] == pytest.approx(float(s1 ** 2 * g1))
    assert steps[1]["greenwood_var"] == pytest.approx(float(s3 ** 2 * g3))
    assert all(0 <= s["ci_low"] <= s["survival"] <= s["ci_high"] <= 1 for s in steps)


def test_ac002_ties_censored_at_an_event_time_stay_at_risk():
    steps = survival.kaplan_meier([2, 2, 3], [True, False, True])
    assert steps[0]["n_risk"] == 3 and steps[0]["survival"] == pytest.approx(2 / 3)
    assert steps[1]["n_risk"] == 1 and steps[1]["survival"] == 0.0
    assert survival.step_value(steps, 1, "survival", 1.0) == 1.0 and survival.step_value(steps, 2.5, "survival", 1.0) == pytest.approx(2 / 3)
    with pytest.raises(ValueError):
        survival.kaplan_meier([], [])


# ---------------------------------------------------------------- AC-003 competing risks
def test_ac003_aalen_johansen_hand_computed_and_sums_to_one():
    d, e = [1, 2, 3, 4], ["a", "b", "a", "censored"]
    a = survival.cumulative_incidence(d, e, "a")
    b = survival.cumulative_incidence(d, e, "b")
    assert [round(s["cif"], 9) for s in a] == [0.25, 0.25, 0.5]
    assert survival.cif_at(a, 3) == pytest.approx(0.5) and survival.cif_at(b, 3) == pytest.approx(0.25)
    assert survival.cif_at(a, 0.5) == 0.0
    assert survival.cif_at(a, 3) + survival.cif_at(b, 3) + a[-1]["all_cause_survival"] == pytest.approx(1.0)


def test_ac003_naive_one_minus_km_overstates_when_other_causes_exist():
    d, e = [1, 2, 3, 4], ["a", "b", "a", "censored"]
    naive = 1 - survival.step_value(survival.kaplan_meier(d, [x == "a" for x in e]), 3, "survival", 1.0)
    assert naive == pytest.approx(5 / 8) and naive > survival.cif_at(survival.cumulative_incidence(d, e, "a"), 3) == pytest.approx(0.5)


def test_ac003_estimator_recovers_the_generating_process():
    subs = synthetic.simulate_competing_risks(4000, 1, RATES, "2018-01-01", "2022-12-31", "2025-12-31")
    d, e = _dur(subs), [s["event"] for s in subs]
    for cause in RATES:
        steps = survival.cumulative_incidence(d, e, cause)
        for t in (365, 730):
            assert abs(survival.cif_at(steps, t) - synthetic.true_cif(RATES, cause, t)) < 0.03
    naive = 1 - survival.step_value(survival.kaplan_meier(d, [x == "next_round" for x in e]), 730, "survival", 1.0)
    assert naive - synthetic.true_cif(RATES, "next_round", 730) > 0.10          # the competing-risks trap is large


# ---------------------------------------------------------------- AC-004 hazard model
def test_ac004_hazard_model_recovers_incidence_and_the_covariate_effect():
    subs = synthetic.simulate_competing_risks(4000, 2, RATES, "2018-01-01", "2022-12-31", "2025-12-31", covariate_beta=0.7)
    m = survival.fit_hazard_model(subs, list(RATES), interval_days=180, n_intervals=6)
    assert all(m.converged.values()) and m.n_subjects == 4000
    beta_next = m.weights["next_round"][m.n_intervals]
    assert 0.45 < beta_next < 0.95                                                # true log-hazard ratio 0.7
    assert abs(m.weights["exit"][m.n_intervals]) < 0.35 and abs(m.weights["failure"][m.n_intervals]) < 0.3
    hi = survival.predict_cif(m, (1.0,), "next_round", 720)
    lo = survival.predict_cif(m, (0.0,), "next_round", 720)
    assert hi > lo
    rates_hi = {**RATES, "next_round": RATES["next_round"] * math.exp(0.7)}
    assert abs(hi - synthetic.true_cif(rates_hi, "next_round", 720)) < 0.05
    assert abs(lo - synthetic.true_cif(RATES, "next_round", 720)) < 0.05
    assert survival.predict_cif(m, (0.0,), "next_round", 360) < lo                # incidence grows with the horizon


def test_ac004_horizon_inside_an_interval_is_interpolated_not_rounded_up():
    subs = synthetic.simulate_competing_risks(1500, 6, RATES, "2018-01-01", "2022-12-31", "2025-12-31")
    m = survival.fit_hazard_model(subs, list(RATES), interval_days=180, n_intervals=6)
    x = (0.0,)
    c180, c270, c360 = (survival.predict_cif(m, x, "next_round", h) for h in (180, 270, 360))
    assert c270 == pytest.approx(c180 + 0.5 * (c360 - c180))                   # half of the second interval
    assert survival.predict_cif(m, x, "next_round", 365) < survival.predict_cif(m, x, "next_round", 540)
    assert survival.predict_cif(m, x, "next_round", 0) == 0.0
    assert survival.predict_cif(m, x, "next_round", 10_000) == survival.predict_cif(m, x, "next_round", 6 * 180)   # capped at the fitted range


def test_ac004_hazard_model_refuses_thin_data():
    few = synthetic.simulate_competing_risks(20, 3, RATES, "2018-01-01", "2018-12-31", "2019-01-10")
    with pytest.raises(SmallSampleError):
        survival.fit_hazard_model(few, list(RATES))
    nothing = synthetic.simulate_competing_risks(200, 3, {"next_round": 1e-9, "exit": 1e-9}, "2018-01-01", "2018-12-31", "2019-01-10")
    with pytest.raises(SmallSampleError, match="no 'next_round' events"):
        survival.fit_hazard_model(nothing, ["next_round", "exit"])


def test_ac004_person_periods_keep_only_fully_observed_intervals():
    s = {"formation_date": "2020-01-01", "end_date": "2020-12-01", "event": "censored", "features_vector": (1.0,)}
    rows = survival.person_periods([s], 100, 8, "next_round")                      # 335 days -> 3 full intervals
    assert [r[0] for r in rows] == [0, 1, 2] and all(r[2] == 0 for r in rows)
    ev = {**s, "end_date": "2020-04-01", "event": "next_round"}                    # 91 days -> inside interval 1
    assert survival.person_periods([ev], 100, 8, "next_round") == [(0, (1.0,), 1)]
    other = {**s, "end_date": "2020-04-01", "event": "exit"}                       # other cause leaves the risk set
    assert survival.person_periods([other], 100, 8, "next_round") == [(0, (1.0,), 0)]


# ---------------------------------------------------------------- AC-005 out-of-time evaluation
def test_ac005_out_of_time_calibration_and_concordance():
    subs = synthetic.simulate_competing_risks(6000, 5, RATES, "2018-01-01", "2023-12-31", "2026-12-31", covariate_beta=0.7)
    sp = validation.out_of_time_split(subs, "2022-01-01", "2026-12-31")
    m = survival.fit_hazard_model(sp["train"], list(RATES), interval_days=180, n_intervals=6)
    test = sp["test"]
    d, e = _dur(test), [s["event"] for s in test]
    pred = [survival.predict_cif(m, s["features_vector"], "next_round", 365) for s in test]
    cal = survival.calibration_by_group(pred, d, e, "next_round", 365, n_groups=2, min_group=50)
    assert [g["assessable"] for g in cal] == [True, True] and cal[0]["mean_predicted"] < cal[1]["mean_predicted"]
    assert all(abs(g["difference"]) < 0.08 for g in cal)
    c = survival.harrell_c(pred, d, [x for x in e], "next_round")
    assert c["c_index"] > 0.52 and c["comparable_pairs"] > 1000
    const = survival.harrell_c([0.3] * len(test), d, e, "next_round")
    assert const["c_index"] == pytest.approx(0.5)                                  # a constant baseline cannot discriminate
    with pytest.raises(SmallSampleError):
        survival.harrell_c([0.1, 0.2], [1, 2], ["next_round", "censored"], "next_round")


def test_ac005_a_group_followed_less_than_the_horizon_is_not_assessable_not_zero():
    pred = [0.1] * 100
    d, e = [30] * 100, ["censored"] * 100
    cal = survival.calibration_by_group(pred, d, e, "next_round", 365, n_groups=2, min_group=20)
    assert all(g["assessable"] is False and g["observed"] is None for g in cal)
    with pytest.raises(SmallSampleError):
        survival.calibration_by_group(pred[:10], d[:10], e[:10], "next_round", 365)


def test_ac005_bootstrap_interval_is_deterministic_and_refuses_small_samples():
    data = [float(i % 7) for i in range(60)]
    a = validation.bootstrap_ci(data, lambda xs: sum(xs) / len(xs), n_boot=200, seed=3)
    assert a == validation.bootstrap_ci(data, lambda xs: sum(xs) / len(xs), n_boot=200, seed=3)
    assert a["low"] <= a["estimate"] <= a["high"] and a["n"] == 60
    with pytest.raises(SmallSampleError):
        validation.bootstrap_ci(data[:5], lambda xs: sum(xs), n_boot=50, seed=1)


# ---------------------------------------------------------------- AC-006 emergence
def test_ac006_theil_sen_and_robust_statistics_hand_computed():
    r = emergence.theil_sen([0, 1, 2, 3], [1, 3, 5, 100])
    assert r["slope"] == 17.5 and r["intercept"] == -6.75                      # median of [2,2,2,33,48.5,95]
    assert emergence.median([3, 1, 2]) == 2 and emergence.median([1, 2, 3, 4]) == 2.5
    assert emergence.mad([1, 1, 2, 2, 4, 6, 9]) == 1.0
    assert emergence.theil_sen([0, 1, 2, 3, 4], [0, 1, 2, 3, 4])["slope"] == 1.0
    with pytest.raises(ValueError):
        emergence.theil_sen([1, 1], [1, 2])
    with pytest.raises(ValueError):
        emergence.median([])


def test_ac006_growth_signal_status_and_trailing_periods():
    flat = synthetic.simulate_poisson_series(36, 1)
    rising = synthetic.simulate_poisson_series(36, 2, emergence_start=28)
    assert emergence.growth_signal(rising)["status"] == "emerging"
    long_running = synthetic.simulate_poisson_series(36, 2, emergence_start=16)
    assert emergence.growth_signal(long_running)["slope_baseline"] > emergence.growth_signal(rising)["slope_baseline"]   # growth has leaked into the baseline
    r = emergence.growth_signal(rising)
    assert r["growth_per_period"] > 0 and r["z"] >= 3 and r["dropped_incomplete_periods"] == 2 and r["poisson_floor"] > 0
    assert emergence.growth_signal(flat)["status"] == "not_emerging"
    assert emergence.growth_signal(flat[:15])["status"] == "not_assessable"
    assert emergence.growth_signal([2.0] * 36)["status"] == "not_assessable"       # below the minimum count
    partial = flat[:-2] + [0.0, 0.0]                                               # late-reporting zeros are dropped, not read as a decline
    assert emergence.growth_signal(partial)["status"] == emergence.growth_signal(flat[:-2] + [flat[-2], flat[-1]])["status"]
    surge_only_in_incomplete = flat[:-2] + [200.0, 400.0]
    assert emergence.growth_signal(surge_only_in_incomplete)["status"] == "not_emerging"   # documented: incomplete periods are never read


def test_ac006_retrospective_detection_reports_delay_and_false_alarms():
    flat = [synthetic.simulate_poisson_series(36, s) for s in range(100)]
    emer = [synthetic.simulate_poisson_series(36, 5000 + s, emergence_start=24) for s in range(100)]
    r = emergence.retrospective_detection(flat + emer, [None] * 100 + [24] * 100)
    assert r["detection_rate"] >= 0.90 and r["false_alarm_rate"] <= 0.10
    assert r["median_delay_periods"] is not None and 1 <= r["median_delay_periods"] <= 8
    assert "synthetic" in r["note"]
    with pytest.raises(SmallSampleError):
        emergence.retrospective_detection(flat[:5], [None] * 5)


# ---------------------------------------------------------------- AC-007 links
EDGES = [("a", "b", "2021-01-01"), ("a", "c", "2021-01-02"), ("b", "c", "2021-01-03"), ("c", "d", "2021-01-04")]


def test_ac007_neighbourhood_scores_hand_computed():
    adj = links.build_adjacency(EDGES, "2021-12-31")
    assert links.common_neighbors(adj, "b", "d") == 1.0
    assert links.jaccard(adj, "b", "d") == pytest.approx(1 / 2)                    # N(b)={a,c}, N(d)={c}
    assert links.adamic_adar(adj, "b", "d") == pytest.approx(1 / math.log(3))      # shared neighbour c has degree 3
    assert links.preferential_attachment(adj, "b", "d") == 2.0
    assert links.common_neighbors(adj, "a", "d") == 1.0
    early = links.build_adjacency(EDGES, "2021-01-02")
    assert "d" not in early and links.common_neighbors(early, "b", "c") == 1.0       # b and c both know a; their own edge is not known yet


def test_ac007_auc_with_ties_hand_computed():
    assert links.auc([3, 2], [2, 1, 0]) == pytest.approx(5.5 / 6)
    assert links.auc([1], [0]) == 1.0 and links.auc([0], [1]) == 0.0 and links.auc([1, 1], [1, 1]) == 0.5
    with pytest.raises(ValueError):
        links.auc([], [1])


def test_ac007_temporal_split_has_no_leakage():
    edges, _ = synthetic.simulate_block_graph(60, 3)
    sp = links.temporal_link_split(edges, "2022-06-01", seed=1)
    train_pairs = {frozenset((a, b)) for a, n in sp["adjacency"].items() for b in n}
    assert sp["positives"] and sp["negatives"]
    for a, b in sp["positives"]:
        assert frozenset((a, b)) not in train_pairs and a in sp["adjacency"] and b in sp["adjacency"]
    pos = {frozenset(p) for p in sp["positives"]}
    for a, b in sp["negatives"]:
        assert frozenset((a, b)) not in train_pairs and frozenset((a, b)) not in pos
    late_known = {frozenset((a, b)) for a, b, k in edges if k > "2022-06-01"}
    assert pos <= late_known                                                        # every positive appeared only after the split
    assert links.temporal_link_split(edges, "2022-06-01", seed=1)["negatives"] == sp["negatives"]


def test_ac007_structure_beats_degree_and_random_on_a_block_graph():
    edges, _ = synthetic.simulate_block_graph(60, 3)
    r = links.evaluate_scorers(edges, "2022-06-01", seed=1)
    assert r["auc"]["common_neighbors"] > 0.65 and r["auc"]["adamic_adar"] > 0.65 and r["auc"]["jaccard"] > 0.65
    assert all(r["beats_degree_baseline"].values())
    assert abs(r["auc"]["random"] - 0.5) < 0.12 and "synthetic data cannot show real" in r["note"]
    with pytest.raises(SmallSampleError):
        links.evaluate_scorers(edges[:6], "2020-01-02", seed=1)


def test_ac007_person_nodes_are_rejected():
    links.validate_nodes({"org-1": "company", "org-2": "fund"})
    with pytest.raises(ValueError, match="person nodes"):
        links.validate_nodes({"org-1": "company", "p-9": "Founder"})
    assert "person" in (ROOT / "src/quantsmith/venture_models/links.py").read_text(encoding="utf-8").lower()


# ---------------------------------------------------------------- AC-008 anomaly
def test_ac008_robust_z_hand_computed_with_floor():
    assert anomaly.robust_z(13, [10, 10, 10, 10, 10, 12]) == pytest.approx(6.0)     # MAD 0 -> scale floored at 0.5
    assert anomaly.robust_z(10, [8, 9, 10, 11, 12]) == pytest.approx(0.0)
    assert anomaly.robust_z(14, [8, 9, 10, 11, 12]) == pytest.approx(4 / (1.4826 * 1.0))
    with pytest.raises(ValueError):
        anomaly.robust_z(1, [])


def test_ac008_incomplete_recent_periods_are_never_anomalous():
    series = [100, 105, 98, 102, 101, 99, 103, 100, 104, 100, 102, 3]               # last quarter still being reported
    rows = anomaly.flag_anomalies(series, period=4, lag_periods=1)
    assert rows[-1]["status"] == "incomplete_period" and "z" not in rows[-1]
    assert all(r["status"] != "anomalous" for r in rows[:-1])
    assert anomaly.flag_anomalies(series, lag_periods=0)[-1]["status"] == "anomalous"   # without the lag guard it would be a false drop


def test_ac008_detects_a_planted_spike_and_reports_assessability():
    series = synthetic.simulate_poisson_series(28, 11, mean=100)
    series[20] = 400.0
    rows = anomaly.flag_anomalies(series, period=4, lag_periods=1)
    assert rows[20]["status"] == "anomalous" and rows[20]["direction"] == "high" and rows[20]["basis"] == "same_season"
    assert rows[0]["status"] == "not_assessable" and rows[1]["status"] == "not_assessable"
    assert sum(r["status"] == "anomalous" for r in rows) <= 3


# ---------------------------------------------------------------- AC-009 nowcast
def test_ac009_chain_ladder_factors_exact():
    comp = [0.5, 0.8, 0.95, 1.0]
    finals, tri = synthetic.simulate_triangle(12, 1, comp)
    factors = nowcast.age_to_age_factors(tri)
    f = Fraction
    expected = [f(4, 5) / f(1, 2), f(19, 20) / f(4, 5), f(1) / f(19, 20)]
    assert factors == pytest.approx([float(x) for x in expected])
    curve = nowcast.completeness_curve(factors)
    assert curve == pytest.approx(comp) and curve[-1] == 1.0
    assert nowcast.nowcast_ultimate(500.0, 0, factors) == pytest.approx(1000.0)
    assert nowcast.nowcast_ultimate(950.0, 2, factors) == pytest.approx(1000.0)
    assert nowcast.nowcast_ultimate(1000.0, 3, factors) == 1000.0
    with pytest.raises(ValueError):
        nowcast.age_to_age_factors([[None, None]])


def test_ac009_vintage_shows_only_what_was_known():
    _, tri = synthetic.simulate_triangle(8, 1, [0.5, 0.8, 1.0])
    v = nowcast.vintage(tri, 4)
    assert len(v) == 5
    for q, row in enumerate(v):
        for k, val in enumerate(row):
            assert (val is not None) == (q + k <= 4)
    assert nowcast.vintage(tri, 7) == [list(r) for r in tri]


def test_ac009_backtest_is_exact_on_a_deterministic_pattern_and_beats_baselines_on_noise():
    _, tri = synthetic.simulate_triangle(24, 2, [0.5, 0.8, 0.95, 1.0], noise_sd=0.05)
    exact = nowcast.backtest_nowcast(tri)
    assert exact["mape"]["chain_ladder"] == pytest.approx(0.0, abs=1e-9) and exact["beats_baselines"]
    assert exact["mape"]["first_report_as_is"] == pytest.approx(0.5, abs=1e-9)
    _, noisy = synthetic.simulate_triangle(40, 3, [0.5, 0.8, 0.95, 1.0], noise_sd=0.05, completeness_noise_sd=0.03)
    r = nowcast.backtest_nowcast(noisy)
    assert 0.0 < r["mape"]["chain_ladder"] < min(r["mape"]["first_report_as_is"], r["mape"]["last_complete_quarter"])
    assert r["beats_baselines"] and "synthetic" in r["note"]
    with pytest.raises(SmallSampleError):
        nowcast.backtest_nowcast(synthetic.simulate_triangle(8, 1, [0.5, 0.8, 1.0])[1])


# ---------------------------------------------------------------- AC-010 governance
def _real_evidence(**over):
    ev = {"dataset_snapshot_hash": "a" * 64, "out_of_time_period": "2024-2025", "metrics": {"c_index": 0.61}, "reviewer": "reviewer-9c1d"}
    ev.update(over)
    return ev


def _deployable_model(**over):
    m = {"id": "m", "status": "validated", "validation_status": "real_data", "usable_for_decisions": True,
         "review_status": "reviewed", "validation_evidence": [_real_evidence()]}
    m.update(over)
    return m


def test_ac010_deployability_is_computed_from_evidence():
    ok, reasons = validation.deployability(_deployable_model())
    assert ok and reasons == []
    for change, needle in (({"status": "reference_baseline"}, "not 'validated'"), ({"validation_status": "synthetic_only"}, "synthetic only"),
                           ({"usable_for_decisions": False}, "usable_for_decisions"), ({"review_status": "draft"}, "not reviewed"),
                           ({"validation_evidence": []}, "no complete real-data")):
        ok, reasons = validation.deployability(_deployable_model(**change))
        assert not ok and any(needle in r for r in reasons), change
    for field in ("dataset_snapshot_hash", "out_of_time_period", "reviewer"):
        ok, _ = validation.deployability(_deployable_model(validation_evidence=[_real_evidence(**{field: None})]))
        assert not ok, field                                                       # None is never a name or a hash
    ok, _ = validation.deployability(_deployable_model(validation_evidence=[_real_evidence(metrics={})]))
    assert not ok


def test_ac010_no_catalog_model_is_usable_for_decisions_today():
    pack = load_pack(ROOT)
    assert validate_pack(pack, ROOT) == []
    models = pack["models"]["models"]
    assert len(models) == 7
    for m in models:
        assert m["usable_for_decisions"] is False and m["validation_evidence"] == [] and m["limitations"].strip()
        assert m["validation_status"] in ("synthetic_only", "deterministic_rules") and m["required_before_use"]
        ok, reasons = validation.deployability(m)
        assert not ok and reasons
    impl = {m["id"]: m["implementation"] for m in models}
    for rel in (v.split(" ")[0] for v in impl.values()):
        assert (ROOT / rel).is_file(), rel


def test_ac010_validator_rejects_a_model_marked_usable_without_evidence():
    pack = load_pack(ROOT)
    bad = copy.deepcopy(pack)
    bad["models"]["models"][1]["usable_for_decisions"] = True
    assert any("not deployable" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(pack)
    del bad["models"]["models"][2]["validation_status"]
    assert any("validation_status" in e for e in validate_pack(bad, ROOT))


# ---------------------------------------------------------------- AC-011 determinism and hygiene
def test_ac011_everything_is_deterministic_and_standard_library_only():
    a = survival.fit_hazard_model(synthetic.simulate_competing_risks(300, 9, RATES, "2019-01-01", "2020-12-31", "2023-01-01"), list(RATES))
    b = survival.fit_hazard_model(synthetic.simulate_competing_risks(300, 9, RATES, "2019-01-01", "2020-12-31", "2023-01-01"), list(RATES))
    assert a == b
    assert synthetic.simulate_poisson_series(20, 3) == synthetic.simulate_poisson_series(20, 3)
    assert links.evaluate_scorers(*synthetic_graph(), seed=2) == links.evaluate_scorers(*synthetic_graph(), seed=2)
    for p in (ROOT / "src/quantsmith/venture_models").glob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "import numpy" not in text and "import scipy" not in text and "random.seed(" not in text and "requests" not in text


def synthetic_graph():
    edges, _ = synthetic.simulate_block_graph(50, 7)
    return edges, "2022-06-01"
