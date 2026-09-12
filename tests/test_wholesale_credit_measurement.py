"""Acceptance tests for spec 0073 — wholesale credit measurement and
counterparty limit review.

Every arithmetic primitive this module uses is imported from
credit_risk_knowledge, so these tests focus on composition: aggregation,
limit checking, concentration, and the runtime-boundary honesty that
rating/PD modeling stays out of this module.
"""

from __future__ import annotations

import pytest

from quantsmith.pipelines.wholesale_credit_measurement import (
    FacilityInput,
    WholesaleMeasurementError,
    aggregate_counterparty_exposure,
    check_counterparty_limits,
    compute_concentration,
    grade_transition_probabilities,
    measure_facility,
    run_counterparty_limit_review,
)


IRB_PD = {"value": 0.02, "horizon": "P1Y", "default_definition_id": "defn.default.irb_reference"}
IRB_LGD = {"value": 0.45, "horizon": "workout_period", "default_definition_id": "defn.default.irb_reference"}
IFRS9_LGD = {"value": 0.5, "horizon": "instrument_life", "default_definition_id": "defn.default.ifrs9_stage3"}


# --- AC-001: EAD has no default ---------------------------------------------


def test_ead_from_ccf_matches_the_golden_case():
    """Reuses 0072's own golden.ead.ccf_undrawn numbers exactly."""

    facility = FacilityInput(
        facility_id="f1", obligor_id="o1", counterparty_id="cp1",
        pd=IRB_PD, lgd=IRB_LGD, drawn_balance=400000.0, limit=1000000.0, ccf=0.5,
    )
    measurement = measure_facility(facility)
    assert measurement.ead == pytest.approx(700000.0)


def test_ead_override_bypasses_ccf_computation():
    facility = FacilityInput(
        facility_id="f1", obligor_id="o1", counterparty_id="cp1",
        pd=IRB_PD, lgd=IRB_LGD, ead_override=250000.0,
    )
    assert measure_facility(facility).ead == pytest.approx(250000.0)


def test_ead_with_no_input_path_raises():
    facility = FacilityInput(facility_id="f1", obligor_id="o1", counterparty_id="cp1", pd=IRB_PD, lgd=IRB_LGD)
    with pytest.raises(WholesaleMeasurementError, match="EAD has no default"):
        measure_facility(facility)


def test_partial_ccf_inputs_do_not_silently_fall_back():
    """Supplying only drawn_balance and limit (no ccf) must not guess a CCF."""

    facility = FacilityInput(
        facility_id="f1", obligor_id="o1", counterparty_id="cp1",
        pd=IRB_PD, lgd=IRB_LGD, drawn_balance=400000.0, limit=1000000.0,
    )
    with pytest.raises(WholesaleMeasurementError):
        measure_facility(facility)


# --- AC-002: expected loss and basis-mismatch rejection ---------------------


def test_expected_loss_matches_the_golden_case():
    facility = FacilityInput(
        facility_id="f1", obligor_id="o1", counterparty_id="cp1",
        pd={"value": 0.02, "horizon": "P1Y", "default_definition_id": "defn.default.irb_reference"},
        lgd={"value": 0.45, "horizon": "workout_period", "default_definition_id": "defn.default.irb_reference"},
        ead_override=1000000.0,
    )
    measurement = measure_facility(facility)
    assert measurement.expected_loss == pytest.approx(9000.0)
    assert measurement.violated_rules == ()


def test_basis_mismatch_withholds_expected_loss_not_a_wrong_number():
    """A one-year IRB PD with a lifetime IFRS9 LGD must not produce a number."""

    facility = FacilityInput(
        facility_id="f1", obligor_id="o1", counterparty_id="cp1",
        pd=IRB_PD, lgd=IFRS9_LGD, ead_override=1000000.0,
    )
    measurement = measure_facility(facility)
    assert measurement.expected_loss is None
    assert measurement.violated_rules == ("rule.basis.el_operands",)
    # EAD is still computed -- only the loss estimate is withheld.
    assert measurement.ead == pytest.approx(1000000.0)


# --- AC-003: RWA ------------------------------------------------------------


def test_rwa_matches_the_golden_case_and_requires_a_supplied_weight():
    facility = FacilityInput(
        facility_id="f1", obligor_id="o1", counterparty_id="cp1",
        pd=IRB_PD, lgd=IRB_LGD, ead_override=700000.0, risk_weight=0.85,
    )
    measurement = measure_facility(facility)
    assert measurement.rwa == pytest.approx(595000.0)

    no_weight = FacilityInput(
        facility_id="f2", obligor_id="o1", counterparty_id="cp1",
        pd=IRB_PD, lgd=IRB_LGD, ead_override=700000.0,
    )
    assert measure_facility(no_weight).rwa is None


# --- AC-004: counterparty aggregation ---------------------------------------


def test_aggregation_sums_ead_and_el_across_facilities_for_one_counterparty():
    f1 = FacilityInput(facility_id="f1", obligor_id="o1", counterparty_id="cp-a",
                        pd=IRB_PD, lgd=IRB_LGD, ead_override=700000.0)
    f2 = FacilityInput(facility_id="f2", obligor_id="o1", counterparty_id="cp-a",
                        pd=IRB_PD, lgd=IRB_LGD, ead_override=200000.0)
    measurements = [measure_facility(f) for f in (f1, f2)]
    exposures = aggregate_counterparty_exposure(measurements)
    assert len(exposures) == 1
    assert exposures[0].total_ead == pytest.approx(900000.0)
    assert exposures[0].facility_ids == ("f1", "f2")
    assert exposures[0].facilities_with_basis_violation == ()


def test_a_basis_violation_is_named_not_treated_as_zero_loss():
    f1 = FacilityInput(facility_id="f1", obligor_id="o1", counterparty_id="cp-a",
                        pd=IRB_PD, lgd=IFRS9_LGD, ead_override=1000000.0)
    measurements = [measure_facility(f1)]
    exposures = aggregate_counterparty_exposure(measurements)
    assert exposures[0].total_expected_loss == 0
    assert exposures[0].facilities_with_basis_violation == ("f1",)


# --- AC-005: limits ----------------------------------------------------------


def test_limit_check_detects_breach_and_within_limit():
    f1 = FacilityInput(facility_id="f1", obligor_id="o1", counterparty_id="cp-a",
                        pd=IRB_PD, lgd=IRB_LGD, ead_override=900000.0)
    f2 = FacilityInput(facility_id="f2", obligor_id="o2", counterparty_id="cp-b",
                        pd=IRB_PD, lgd=IRB_LGD, ead_override=1500000.0)
    exposures = aggregate_counterparty_exposure([measure_facility(f1), measure_facility(f2)])
    results = check_counterparty_limits(exposures, {"cp-a": 1000000.0, "cp-b": 1000000.0})
    by_id = {r.counterparty_id: r for r in results}
    assert by_id["cp-a"].status == "within_limit"
    assert by_id["cp-a"].breach_amount == 0.0
    assert by_id["cp-b"].status == "breached"
    assert by_id["cp-b"].breach_amount == pytest.approx(500000.0)


def test_exposure_without_a_registered_limit_raises_not_passes_silently():
    f1 = FacilityInput(facility_id="f1", obligor_id="o1", counterparty_id="cp-unregistered",
                        pd=IRB_PD, lgd=IRB_LGD, ead_override=100.0)
    exposures = aggregate_counterparty_exposure([measure_facility(f1)])
    with pytest.raises(WholesaleMeasurementError, match="no registered limit"):
        check_counterparty_limits(exposures, {})


# --- AC-006: concentration ----------------------------------------------------


def test_concentration_flags_a_dominant_counterparty():
    f1 = FacilityInput(facility_id="f1", obligor_id="o1", counterparty_id="cp-a",
                        pd=IRB_PD, lgd=IRB_LGD, ead_override=100000.0)
    f2 = FacilityInput(facility_id="f2", obligor_id="o2", counterparty_id="cp-b",
                        pd=IRB_PD, lgd=IRB_LGD, ead_override=900000.0)
    exposures = aggregate_counterparty_exposure([measure_facility(f1), measure_facility(f2)])
    report = compute_concentration(exposures, concentration_threshold=0.5)
    assert report.largest_counterparty_id == "cp-b"
    assert report.largest_counterparty_share == pytest.approx(0.9)
    assert report.threshold_breached is True
    # HHI for shares (0.1, 0.9) is 0.01 + 0.81 = 0.82.
    assert report.herfindahl_index == pytest.approx(0.82)


def test_concentration_threshold_is_a_required_argument_not_a_default():
    import inspect

    sig = inspect.signature(compute_concentration)
    assert sig.parameters["concentration_threshold"].default is inspect.Parameter.empty


def test_concentration_requires_at_least_one_exposure():
    with pytest.raises(WholesaleMeasurementError):
        compute_concentration([], concentration_threshold=0.5)


# --- AC-007: migration matrix ------------------------------------------------


def test_grade_transition_probabilities_matches_the_golden_matrix():
    matrix_record = {
        "grades": ["A", "B", "C", "D"],
        "matrix": [[0.90, 0.07, 0.02, 0.01],
                   [0.05, 0.85, 0.08, 0.02],
                   [0.01, 0.10, 0.80, 0.09],
                   [0.00, 0.00, 0.00, 1.00]],
        "absorbing_state": "D",
    }
    row = grade_transition_probabilities(matrix_record, "B")
    assert row == {"A": 0.05, "B": 0.85, "C": 0.08, "D": 0.02}
    assert sum(row.values()) == pytest.approx(1.0)


def test_non_stochastic_matrix_is_refused():
    bad = {"grades": ["A", "B"], "matrix": [[0.5, 0.4], [0.1, 0.8]], "absorbing_state": "B"}
    with pytest.raises(WholesaleMeasurementError, match="not stochastic"):
        grade_transition_probabilities(bad, "A")


def test_unknown_grade_is_refused():
    matrix_record = {"grades": ["A", "B"], "matrix": [[1.0, 0.0], [0.0, 1.0]], "absorbing_state": "B"}
    with pytest.raises(WholesaleMeasurementError, match="unknown starting grade"):
        grade_transition_probabilities(matrix_record, "Z")


# --- AC-008: the end-to-end workflow -----------------------------------------


def test_run_counterparty_limit_review_end_to_end():
    facilities = [
        FacilityInput(facility_id="f1", obligor_id="o1", counterparty_id="cp-a",
                      pd=IRB_PD, lgd=IRB_LGD, drawn_balance=400000.0, limit=1000000.0,
                      ccf=0.5, risk_weight=0.85),
        FacilityInput(facility_id="f2", obligor_id="o1", counterparty_id="cp-a",
                      pd=IRB_PD, lgd=IRB_LGD, ead_override=200000.0),
        FacilityInput(facility_id="f3", obligor_id="o2", counterparty_id="cp-b",
                      pd=IRB_PD, lgd=IFRS9_LGD, ead_override=1500000.0),
    ]
    report = run_counterparty_limit_review(
        facilities, limits={"cp-a": 1000000.0, "cp-b": 1000000.0}, concentration_threshold=0.5,
    )
    assert len(report.facility_measurements) == 3
    assert {e.counterparty_id for e in report.exposures} == {"cp-a", "cp-b"}
    assert report.breached_counterparty_ids == ("cp-b",)
    assert report.concentration.threshold_breached is True


def test_run_counterparty_limit_review_is_deterministic():
    facilities = [
        FacilityInput(facility_id="f1", obligor_id="o1", counterparty_id="cp-a",
                      pd=IRB_PD, lgd=IRB_LGD, ead_override=500000.0),
    ]
    first = run_counterparty_limit_review(facilities, {"cp-a": 1000000.0}, 0.5)
    second = run_counterparty_limit_review(facilities, {"cp-a": 1000000.0}, 0.5)
    assert first == second


# --- AC-009: rating/PD modeling stays out of this module --------------------


def test_module_has_no_rating_or_pd_estimation_function():
    """The runtime-boundary claim, checked mechanically: this module must not
    export anything that assigns a rating or estimates a PD/LGD -- that stays
    an adopter's own model registered via 0026."""

    import quantsmith.pipelines.wholesale_credit_measurement as module

    forbidden_substrings = ("estimate_pd", "assign_rating", "fit_", "train_", "calibrate_")
    exported = [name for name in dir(module) if not name.startswith("_")]
    for name in exported:
        lowered = name.lower()
        assert not any(bad in lowered for bad in forbidden_substrings), name
