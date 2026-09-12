"""Acceptance tests for spec 0074 — retail underwriting fairness harness.

No scorecard is tested here because none exists: every applicant's score is
a synthetic input, standing in for whatever an adopter's own model produces.
The tests exercise disparity measurement, proxy association, and the
less-discriminatory-alternative search this module adds on top of
credit_risk_knowledge.py's existing, unchanged arithmetic.
"""

from __future__ import annotations

import pytest

from quantsmith.pipelines.retail_fairness_harness import (
    FairnessHarnessError,
    ScoredApplicant,
    measure_disparity,
    measure_proxy_association,
    run_fairness_harness,
    search_less_discriminatory_alternative,
)


def _population(ref_mean=650, prot_mean=610, n=100, seed=42):
    import random

    rng = random.Random(seed)
    applicants = []
    for i in range(n):
        applicants.append(
            ScoredApplicant(
                applicant_id=f"ref-{i}", score=rng.gauss(ref_mean, 40),
                protected_class_member=False,
                feature_values={"zip_income_proxy": rng.gauss(70000, 10000)},
            )
        )
    for i in range(n):
        applicants.append(
            ScoredApplicant(
                applicant_id=f"prot-{i}", score=rng.gauss(prot_mean, 40),
                protected_class_member=True,
                feature_values={"zip_income_proxy": rng.gauss(50000, 10000)},
            )
        )
    return applicants


# --- AC-001: no scorecard, mechanically checked ------------------------------


def test_module_has_no_scoring_or_training_function():
    """The runtime-boundary claim, checked mechanically: this module must not
    export anything that scores an applicant or trains a model."""

    import quantsmith.pipelines.retail_fairness_harness as module

    forbidden = ("score_applicant", "train_", "fit_", "predict_")
    for name in dir(module):
        if name.startswith("_"):
            continue
        lowered = name.lower()
        assert not any(bad in lowered for bad in forbidden), name


# --- AC-002: disparity measurement reuses adverse_impact_ratio unchanged ---


def test_disparity_matches_the_golden_case_shape():
    """Same 0.36/0.60 selection rates as golden.fairness.adverse_impact_ratio,
    constructed from a raw applicant population instead of pre-aggregated
    counts."""

    applicants = (
        [ScoredApplicant(f"p{i}", 1.0, True, {}) for i in range(180)]
        + [ScoredApplicant(f"p{i}", 0.0, True, {}) for i in range(320)]
        + [ScoredApplicant(f"r{i}", 1.0, False, {}) for i in range(600)]
        + [ScoredApplicant(f"r{i}", 0.0, False, {}) for i in range(400)]
    )
    result = measure_disparity(applicants, cutoff=1.0, disparity_threshold=0.8)
    assert result.protected_approval_rate == pytest.approx(0.36)
    assert result.reference_approval_rate == pytest.approx(0.60)
    assert result.adverse_impact_ratio == pytest.approx(0.6)
    assert result.threshold_breached is True


def test_disparity_requires_both_groups():
    applicants = [ScoredApplicant("p1", 1.0, True, {})]
    with pytest.raises(FairnessHarnessError, match="both a protected-class group"):
        measure_disparity(applicants, cutoff=0.5, disparity_threshold=0.8)


def test_disparity_requires_at_least_one_applicant():
    with pytest.raises(FairnessHarnessError):
        measure_disparity([], cutoff=0.5, disparity_threshold=0.8)


# --- AC-003: proxy association -----------------------------------------------


def test_proxy_association_detects_a_real_correlation():
    applicants = _population()
    result = measure_proxy_association(applicants, "zip_income_proxy")
    # Protected group has systematically lower income proxy values by
    # construction, so the correlation must be negative and substantial.
    assert result.correlation_with_protected_class < -0.5


def test_proxy_association_rejects_a_constant_feature():
    applicants = [
        ScoredApplicant("p1", 1.0, True, {"x": 5.0}),
        ScoredApplicant("p2", 1.0, False, {"x": 5.0}),
    ]
    with pytest.raises(FairnessHarnessError, match="zero variance"):
        measure_proxy_association(applicants, "x")


def test_proxy_association_rejects_a_single_group_population():
    applicants = [
        ScoredApplicant("p1", 1.0, True, {"x": 1.0}),
        ScoredApplicant("p2", 1.0, True, {"x": 2.0}),
    ]
    with pytest.raises(FairnessHarnessError, match="zero variance"):
        measure_proxy_association(applicants, "x")


# --- AC-004: less-discriminatory-alternative search -------------------------


def test_lda_search_requires_supplied_candidates_and_tolerance():
    applicants = _population()
    with pytest.raises(FairnessHarnessError, match="non-empty"):
        search_less_discriminatory_alternative(
            applicants, baseline_cutoff=620, disparity_threshold=0.8,
            candidate_cutoffs=[], max_approval_rate_delta=0.2,
        )


def test_lda_search_finds_an_alternative_within_tolerance():
    applicants = _population()
    search = search_less_discriminatory_alternative(
        applicants, baseline_cutoff=620, disparity_threshold=0.8,
        candidate_cutoffs=[560, 580, 600, 610, 620], max_approval_rate_delta=0.35,
    )
    assert search.alternative_found is True
    # The recommendation is the closest-to-baseline eligible candidate, not
    # necessarily the one with the best AIR: 580 clears the threshold and is
    # closer to the 620 baseline than 560, which also clears it.
    assert search.recommended_cutoff == 580
    eligible = [c for c in search.candidates if not c.disparity.threshold_breached]
    assert len(eligible) >= 2
    assert all(abs(search.recommended_cutoff - 620) <= abs(c.cutoff - 620) for c in eligible)


def test_lda_search_honestly_reports_no_alternative_within_tolerance():
    applicants = _population()
    search = search_less_discriminatory_alternative(
        applicants, baseline_cutoff=620, disparity_threshold=0.8,
        candidate_cutoffs=[560, 580, 600, 610, 620], max_approval_rate_delta=0.15,
    )
    assert search.alternative_found is False
    assert search.recommended_cutoff is None


# --- AC-005: the composed harness (the disparate_impact_hook implementation) -


def test_harness_skips_lda_search_when_not_breached():
    """No search runs when nothing needs fixing -- matches REQ-020's own
    'required when disparity_threshold_breached' conditional exactly."""

    applicants = _population(ref_mean=630, prot_mean=625)
    report = run_fairness_harness(
        applicants, cutoff=500, disparity_threshold=0.5, features=["zip_income_proxy"],
    )
    assert report.baseline.threshold_breached is False
    assert report.less_discriminatory_alternative is None


def test_harness_requires_lda_inputs_when_breached():
    applicants = _population()
    with pytest.raises(FairnessHarnessError, match="REQ-020"):
        run_fairness_harness(
            applicants, cutoff=620, disparity_threshold=0.8, features=["zip_income_proxy"],
        )


def test_harness_runs_lda_search_when_breached_and_inputs_supplied():
    applicants = _population()
    report = run_fairness_harness(
        applicants, cutoff=620, disparity_threshold=0.8, features=["zip_income_proxy"],
        candidate_cutoffs=[560, 580, 600, 610, 620], max_approval_rate_delta=0.35,
    )
    assert report.baseline.threshold_breached is True
    assert report.less_discriminatory_alternative is not None
    assert report.less_discriminatory_alternative.alternative_found is True
    assert len(report.proxy_associations) == 1


def test_harness_rejects_unknown_protected_class_basis():
    applicants = _population()
    with pytest.raises(FairnessHarnessError, match="protected_class_basis"):
        run_fairness_harness(
            applicants, cutoff=500, disparity_threshold=0.5, features=[],
            protected_class_basis="guessed",
        )


def test_harness_is_deterministic():
    applicants = _population()
    first = run_fairness_harness(
        applicants, cutoff=620, disparity_threshold=0.8, features=["zip_income_proxy"],
        candidate_cutoffs=[560, 580, 600, 610, 620], max_approval_rate_delta=0.35,
    )
    second = run_fairness_harness(
        applicants, cutoff=620, disparity_threshold=0.8, features=["zip_income_proxy"],
        candidate_cutoffs=[560, 580, 600, 610, 620], max_approval_rate_delta=0.35,
    )
    assert first == second
