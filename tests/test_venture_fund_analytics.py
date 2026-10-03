"""Acceptance tests for spec 0091 -- venture fund and portfolio analytics.

All flows, indices, marks, and cohorts are synthetic (spec 0025). Expected values come from
hand arithmetic or exact rational arithmetic, not from the module under test.
"""

from __future__ import annotations

import json
import random
import re
from fractions import Fraction
from pathlib import Path

import pytest

from quantsmith.pipelines.venture_fund_analytics import (
    MARK_FLAG_CODES, alpha_sensitivity, bootstrap_fund, deal_moic, fund_multiples, index_level_at, j_curve,
    ks_pme, net_cash_flow_profile, normalize_flows, peer_percentile, reserve_policy_table, review_marks,
    simulate_fund, simulate_reserves, xirr,
)
from quantsmith.pipelines.venture_pack import load_pack, validate_pack

ROOT = Path(__file__).resolve().parents[1]
FUND = [
    {"date": "2021-01-01", "type": "contribution", "amount": 40},
    {"date": "2022-01-01", "type": "contribution", "amount": 60},
    {"date": "2023-01-01", "type": "distribution", "amount": 30},
    {"date": "2024-01-01", "type": "nav", "amount": 100},
]
INDEX = {"2021-01-01": 100, "2022-01-01": 110, "2023-01-01": 121, "2024-01-01": 133.1}


def _npv(flows, rate, as_of):
    """Independent NPV at a rate, Actual/365, latest NAV terminal."""
    fl = normalize_flows(flows, as_of)
    t0 = fl[0]["date"]
    navs = [f for f in fl if f["type"] == "nav"]
    total = 0.0
    for f in fl:
        sign = -1 if f["type"] == "contribution" else 1
        if f["type"] == "nav" and f is not navs[-1]:
            continue
        total += sign * f["amount"] / (1 + rate) ** ((f["date"] - t0).days / 365.0)
    return total


# ---------------------------------------------------------------- AC-001
def test_ac001_multiples_hand_arithmetic():
    m = fund_multiples(FUND, "2024-01-01")
    assert (m["paid_in"], m["distributions"], m["nav"]) == (100, 30, 100)
    assert (m["dpi"], m["rvpi"], m["tvpi"]) == pytest.approx((0.3, 1.0, 1.3))
    assert m["tvpi"] == pytest.approx(m["dpi"] + m["rvpi"])
    assert m["warnings"] == []


def test_ac001_as_of_uses_only_what_was_known():
    early = fund_multiples(FUND, "2022-06-01")
    assert early["paid_in"] == 100 and early["distributions"] == 0 and early["nav"] == 0
    assert "no_nav_reported" in early["warnings"] and early["tvpi"] == 0
    late_known = FUND + [{"date": "2022-03-01", "type": "distribution", "amount": 500, "known_at": "2022-09-01"}]
    assert fund_multiples(late_known, "2022-06-01")["distributions"] == 0          # not yet known
    assert fund_multiples(late_known, "2022-12-31")["distributions"] == 500
    with pytest.raises(ValueError):
        fund_multiples(FUND, "2020-06-01")                                          # nothing paid in yet
    old_nav = FUND + [{"date": "2023-06-01", "type": "nav", "amount": 80}]
    assert fund_multiples(old_nav, "2023-07-01")["nav"] == 80                       # latest NAV on or before
    assert "nav_stale" in fund_multiples(old_nav, "2023-12-31", max_nav_age_days=90)["warnings"]
    assert deal_moic(10, 5, 20) == 2.5
    with pytest.raises(ValueError):
        deal_moic(0, 1, 1)


def test_ac001_input_validation():
    with pytest.raises(ValueError):
        normalize_flows([{"date": "2021-01-01", "type": "fee", "amount": 1}])
    with pytest.raises(ValueError):
        normalize_flows([{"date": "2021-01-01", "type": "contribution", "amount": -1}])
    out = normalize_flows([{"date": "2021-01-01", "type": "distribution", "amount": 1},
                           {"date": "2021-01-01", "type": "contribution", "amount": 1}])
    assert [f["type"] for f in out] == ["contribution", "distribution"]            # contributions first on a date


# ---------------------------------------------------------------- AC-002
def test_ac002_xirr_closed_form_and_npv_zero():
    two_years = [{"date": "2021-01-01", "type": "contribution", "amount": 100},
                 {"date": "2023-01-01", "type": "distribution", "amount": 121}]       # exactly 730 days
    assert xirr(two_years, "2023-01-01")["irr"] == pytest.approx(0.10, abs=1e-9)
    r = xirr(FUND, "2024-01-01")
    assert abs(_npv(FUND, r["irr"], "2024-01-01")) < 1e-6 and r["day_count"] == "Actual/365"
    leap = [{"date": "2020-01-01", "type": "contribution", "amount": 100},
            {"date": "2021-01-01", "type": "distribution", "amount": 110}]             # 366 days
    assert xirr(leap, "2021-01-01")["irr"] == pytest.approx(1.1 ** (365 / 366) - 1, abs=1e-9)


def test_ac002_xirr_refuses_and_warns():
    with pytest.raises(ValueError):
        xirr([{"date": "2021-01-01", "type": "contribution", "amount": 100}], "2022-01-01")
    with pytest.raises(ValueError):
        xirr([{"date": "2021-01-01", "type": "distribution", "amount": 5},
              {"date": "2022-01-01", "type": "distribution", "amount": 5}], "2022-01-01")
    classic = [{"date": "2021-01-01", "type": "contribution", "amount": 100},
               {"date": "2022-01-01", "type": "distribution", "amount": 230},
               {"date": "2023-01-01", "type": "contribution", "amount": 132}]        # IRR 10% and 20%
    out = xirr(classic, "2023-01-01")
    assert "multiple_sign_changes_irr_may_not_be_unique" in out["warnings"]
    assert len(out["roots"]) == 2
    assert out["roots"][0] == pytest.approx(0.10, abs=1e-6) and out["roots"][1] == pytest.approx(0.20, abs=1e-6)
    assert out["irr"] == pytest.approx(0.10, abs=1e-6)                           # nearest the 10% guess
    assert xirr(classic, "2023-01-01", guess=0.19)["irr"] == pytest.approx(0.20, abs=1e-6)
    assert xirr(FUND, "2024-01-01")["warnings"] == []


# ---------------------------------------------------------------- AC-003
def test_ac003_j_curve_cash_profile():
    p = net_cash_flow_profile(FUND)
    assert [x["running_net"] for x in p["points"]] == [-40, -100, -70]
    assert p["trough"] == {"date": "2022-01-01", "running_net": -100} and p["breakeven_date"] is None
    recovered = FUND + [{"date": "2025-01-01", "type": "distribution", "amount": 120}]
    q = net_cash_flow_profile(recovered)
    assert q["breakeven_date"] == "2025-01-01"
    with pytest.raises(ValueError):
        net_cash_flow_profile([{"date": "2024-01-01", "type": "nav", "amount": 1}])


def test_ac003_j_curve_series_uses_only_known_information():
    rows = j_curve(FUND, ["2020-06-01", "2021-06-01", "2022-06-01", "2023-06-01", "2024-01-01"])
    assert rows[0]["error"] == "no_paid_in_capital_yet"
    assert rows[1]["tvpi"] == 0 and rows[1]["irr"] is None                         # paid in, nothing back or reported
    assert rows[2]["paid_in" if "paid_in" in rows[2] else "dpi"] == 0
    assert rows[3]["dpi"] == pytest.approx(0.3) and rows[3]["tvpi"] == pytest.approx(0.3)
    assert rows[4]["tvpi"] == pytest.approx(1.3) and rows[4]["irr"] > 0
    assert rows[1]["irr_unavailable_reason"]


# ---------------------------------------------------------------- AC-004
def test_ac004_ks_pme_exact_rational_check():
    f = Fraction
    idx = {k: f(str(v)) for k, v in INDEX.items()}
    fv_c = f(40) * idx["2024-01-01"] / idx["2021-01-01"] + f(60) * idx["2024-01-01"] / idx["2022-01-01"]
    fv_d = f(30) * idx["2024-01-01"] / idx["2023-01-01"] + f(100)
    r = ks_pme(FUND, INDEX, "2024-01-01")
    assert r["ks_pme"] == pytest.approx(float(fv_d / fv_c), rel=1e-12)
    assert r["fv_contributions"] == pytest.approx(125.84) and r["fv_distributions_and_nav"] == pytest.approx(133.0)


def test_ac004_ks_pme_equals_one_when_fund_matches_index():
    flows = [{"date": "2021-01-01", "type": "contribution", "amount": 100},
             {"date": "2023-01-01", "type": "nav", "amount": 121}]
    assert ks_pme(flows, {"2021-01-01": 100, "2023-01-01": 121}, "2023-01-01")["ks_pme"] == pytest.approx(1.0)


def test_ac004_index_gaps_are_refused():
    from datetime import date
    with pytest.raises(ValueError):
        index_level_at({"2022-01-01": 100}, date(2021, 1, 1))
    with pytest.raises(ValueError):
        ks_pme(FUND, {"2022-01-01": 100, "2024-01-01": 120}, "2024-01-01")         # starts after first flow
    with pytest.raises(ValueError):
        index_level_at({"2021-01-01": 0}, date(2021, 6, 1))
    assert index_level_at(INDEX, date(2022, 6, 1)) == 110                           # last level on or before


# ---------------------------------------------------------------- AC-005
def test_ac005_peer_percentile_vintage_matched_and_thin_refused():
    peers = [{"vintage": 2021, "tvpi": x / 10} for x in range(10, 30)] + [{"vintage": 2020, "tvpi": 9.9}] * 5
    r = peer_percentile(2.0, peers, 2021)
    assert r["n_peers"] == 20 and r["percentile_rank"] == pytest.approx(0.525) and r["quartile"] == 2
    assert "survivorship" in r["caveat"]
    assert peer_percentile(2.95, peers, 2021)["quartile"] == 1 and peer_percentile(0.5, peers, 2021)["quartile"] == 4
    with pytest.raises(ValueError):
        peer_percentile(2.0, peers, 2020)                                          # only 5 peers that vintage
    with pytest.raises(ValueError):
        peer_percentile(2.0, peers, 1999)


# ---------------------------------------------------------------- AC-006
def _h(**over):
    base = {"company_id": "synthetic.c1", "mark_date": "2026-06-30", "fair_value": 1000, "shares": 100, "basis": "last_round",
            "prior_mark_value": 1000, "prior_mark_date": "2026-03-31", "last_round_date": "2026-01-15",
            "last_round_price": 10.0}
    base.update(over)
    return base


def _codes(holdings, **kw):
    args = {"as_of": "2026-09-30", "max_age_days": 120, "price_tolerance": 0.10}
    args.update(kw)
    return [(f["company_id"], f["code"]) for f in review_marks(holdings, **args)]


def test_ac006_clean_mark_has_no_flags():
    assert _codes([_h()]) == []


def test_ac006_each_flag_fires_on_its_condition():
    assert _codes([_h(basis="")]) == [("synthetic.c1", "missing_basis")]
    assert ("synthetic.c1", "stale_mark") in _codes([_h(mark_date="2026-01-31")])
    up = _h(fair_value=1500, prior_mark_value=1000)                                # up, no round since prior mark
    assert ("synthetic.c1", "markup_without_new_round") in _codes([up])
    assert ("synthetic.c1", "markup_without_new_round") not in _codes([_h(fair_value=1500, last_round_date="2026-05-01",
                                                                         last_round_price=15.0)])
    newer = _h(last_round_date="2026-08-01", last_round_price=6.0)                 # round after the mark, lower price
    c = _codes([newer])
    assert ("synthetic.c1", "mark_predates_latest_round") in c and ("synthetic.c1", "down_round_not_reflected") in c
    dev = _h(fair_value=1500, last_round_date="2026-01-15", last_round_price=10.0, prior_mark_value=1500)
    assert ("synthetic.c1", "price_deviates_from_last_round") in _codes([dev])
    assert set(c for _, c in _codes([newer, up, dev, _h(basis="")])) <= set(MARK_FLAG_CODES)


def test_ac006_flags_carry_numbers_and_the_decision_owner():
    f = review_marks([_h(fair_value=1500)], "2026-09-30", 120, 0.10)
    dev = next(x for x in f if x["code"] == "price_deviates_from_last_round")
    assert dev["detail"]["implied_price"] == pytest.approx(15.0) and dev["detail"]["deviation"] == pytest.approx(0.5)
    assert all(x["decision_owner"] == "valuation committee" for x in f)
    assert not any(k in x for x in f for k in ("approved", "recommended_mark", "new_value"))


# ---------------------------------------------------------------- AC-007
PARAMS = dict(n_companies=10, p_loss=0.5, alpha=1.5, xmin=1.0, cap=50.0, trials=400, seed=11)


def test_ac007_simulation_is_deterministic_and_leaves_global_random_alone():
    state = random.getstate()
    a, b = simulate_fund(**PARAMS), simulate_fund(**PARAMS)
    assert a == b and random.getstate() == state
    assert simulate_fund(**{**PARAMS, "seed": 12}) != a
    assert a["assumptions"]["seed"] == 11 and "before fees" in a["assumptions"]["gross"]


def test_ac007_degenerate_cases_have_exact_answers():
    assert simulate_fund(**{**PARAMS, "p_loss": 1.0})["mean"] == 0.0
    fixed = simulate_fund(**{**PARAMS, "p_loss": 0.0, "cap": 1.0})                  # every company returns exactly xmin
    assert fixed["q05"] == fixed["q95"] == fixed["mean"] == 1.0 and fixed["p_below_1x"] == 0.0
    all_win_2x = simulate_fund(n_companies=4, p_loss=0.0, alpha=1.0, xmin=2.0, cap=2.0, trials=100, seed=1)
    assert all_win_2x["mean"] == 2.0
    one = simulate_fund(**{**PARAMS, "n_companies": 1, "p_loss": 0.0, "cap": 1.0})
    assert one["mean_top_company_share_of_proceeds"] == 1.0


def test_ac007_intervals_are_ordered_and_mcse_reported():
    s = simulate_fund(**{**PARAMS, "trials": 2000})
    assert s["q05"] <= s["q25"] <= s["q50"] <= s["q75"] <= s["q95"]
    assert s["mcse"] > 0 and 0.0 <= s["p_below_1x"] <= 1.0 and 0 < s["mean_top_company_share_of_proceeds"] <= 1


def test_ac007_heavier_tail_raises_upper_quantile_and_concentration():
    out = alpha_sensitivity([1.2, 3.0], **{k: v for k, v in PARAMS.items() if k != "alpha"}, **{})  # type: ignore[arg-type]
    heavy, light = out[1.2], out[3.0]
    assert heavy["q95"] > light["q95"] and heavy["mean"] > light["mean"]


def test_ac007_invalid_parameters_raise():
    for bad in ({"n_companies": 0}, {"p_loss": 1.5}, {"alpha": 0}, {"cap": 0.5}, {"trials": 10}):
        with pytest.raises(ValueError):
            simulate_fund(**{**PARAMS, **bad})


# ---------------------------------------------------------------- AC-008
def test_ac008_bootstrap_and_equal_outcome_null():
    same = bootstrap_fund([2.0] * 40, 8, 200, 3)
    assert same["q05"] == same["q95"] == 2.0 and same["equal_outcome_null"] == 2.0
    cohort = [0.0] * 8 + [0.5] * 6 + [1.0] * 4 + [10.0] * 2                         # one in ten is a ten-bagger
    b = bootstrap_fund(cohort, 10, 1000, 5)
    assert b["equal_outcome_null"] == pytest.approx(sum(cohort) / len(cohort))
    assert "small_sample" in b["warnings"]
    assert 0.4 < b["share_below_equal_outcome_null"] < 0.8                          # skew puts most trials under the mean
    assert bootstrap_fund(cohort, 10, 1000, 5) == b
    with pytest.raises(ValueError):
        bootstrap_fund([], 5, 200, 1)
    with pytest.raises(ValueError):
        bootstrap_fund([-1.0, 2.0], 5, 200, 1)


# ---------------------------------------------------------------- AC-009
RESERVE = dict(n_companies=10, p_loss=0.5, alpha=1.5, xmin=1.0, cap=50.0, check=1.0, follow_on_size=1.0,
               hit_rate=0.5, false_positive_rate=0.1, breakout_multiple=3.0, follow_on_dilution=0.7, trials=400, seed=11)


def test_ac009_no_identified_companies_means_no_follow_ons_and_the_baseline():
    none = simulate_reserves(reserve_fraction=0.3, **{**RESERVE, "hit_rate": 0.0, "false_positive_rate": 0.0})
    base = simulate_reserves(reserve_fraction=0.0, **RESERVE)
    assert none["mean"] == base["mean"] and none["mean_share_of_total_capital_deployed"] < 1.0
    assert base["max_follow_ons"] == 0 and base["mean_share_of_total_capital_deployed"] == 1.0


def test_ac009_reserve_table_uses_common_outcomes_and_states_assumptions():
    t = reserve_policy_table([0.0, 0.2, 0.4], **RESERVE)
    assert set(t) == {0.0, 0.2, 0.4}
    assert t[0.2]["max_follow_ons"] == 2 and t[0.4]["max_follow_ons"] == 4
    for s in t.values():
        a = s["assumptions"]
        assert a["hit_rate"] == 0.5 and a["follow_on_dilution"] == 0.7 and "assumed, not estimated" in a["note"]
    perfect = simulate_reserves(reserve_fraction=0.4, **{**RESERVE, "hit_rate": 1.0, "false_positive_rate": 0.0,
                                                          "follow_on_dilution": 1.0})
    assert perfect["mean"] >= simulate_reserves(reserve_fraction=0.0, **RESERVE)["mean"]
    for bad in ({"hit_rate": 1.5}, {"follow_on_size": 0}, {"check": 0}, {"follow_on_dilution": -1}):
        with pytest.raises(ValueError):
            simulate_reserves(reserve_fraction=0.2, **{**RESERVE, **bad})


# ---------------------------------------------------------------- AC-010 / AC-011
def test_ac010_conventions_and_flag_registry_match_the_module():
    pack = load_pack(ROOT)
    assert validate_pack(pack, ROOT) == []
    norm = pack["conventions"]
    ids = {c["id"] for c in norm["fund_metrics"]}
    assert {"conv.xirr", "conv.peer_percentile"} <= ids
    flags = norm["mark_review_flags"]
    assert tuple(f["code"] for f in flags) == MARK_FLAG_CODES
    assert all(f["review_status"] == "draft" and f["citation"].strip() for f in flags)


def test_ac011_agents_built_with_boundaries_and_indexed():
    pack = load_pack(ROOT)
    cov = {a["id"]: a for a in pack["coverage"]["agents"]}
    names = {"fund_performance_analyst": "set, certify, or adjust a valuation",
             "valuation_marks_reviewer": "approve, reject, set, or propose a replacement for a mark",
             "portfolio_reserve_analyst": "decide follow-on investments"}
    base = ROOT / "agents/venture_intelligence"
    catalog = (ROOT / "agents/README.md").read_text(encoding="utf-8")
    standard = (ROOT / "instructions/venture_intelligence.md").read_text(encoding="utf-8")
    for name, boundary in names.items():
        assert cov[name]["status"] == "built" and cov[name]["creating_spec"] == "0091"
        for f in ("README.md", "instructions.md", "tasks.md", "prompt.md"):
            assert (base / name / f).is_file()
        assert boundary in (base / name / "README.md").read_text(encoding="utf-8").lower()
        assert f"venture_intelligence/{name}/" in catalog and f"`{name}`" in standard
    wf = next(w for w in pack["workflows"]["workflows"] if w["id"] == "workflow.portfolio_fund_review")
    assert not any("(planned)" in a for a in wf["agents"])
    roadmap = {r["spec"]: r for r in pack["coverage"]["roadmap"]}
    assert "0095" in roadmap and roadmap["0095"]["closes"] == [] and "survival" in roadmap["0095"]["scope"]
    assert set(roadmap["0091"]["closes"]) == set(names)
    def nxt(path: str) -> str:
        m = re.search(r"Next unreserved spec number: `(\d+)`", (ROOT / path).read_text(encoding="utf-8"))
        return m.group(1)
    assert nxt("specs/README.md") == nxt("docs/handoff.md") and int(nxt("specs/README.md")) >= 96   # the indexes agree; the value advances as specs land


# ---------------------------------------------------------------- AC-012
def test_ac012_synthetic_only_and_no_global_state():
    src = (ROOT / "src/quantsmith/pipelines/venture_fund_analytics.py").read_text(encoding="utf-8")
    assert "random.seed(" not in src and "import numpy" not in src and "requests" not in src
    assert json.dumps(simulate_fund(**PARAMS)) == json.dumps(simulate_fund(**PARAMS))
