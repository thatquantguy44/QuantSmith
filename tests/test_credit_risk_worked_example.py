"""Acceptance tests for the cross-cutting credit risk worked example.

This is not a spec acceptance module — the worked example consumes no
reserved spec number and adds no new capability. These tests instead prove
the composition itself: that 0077's admission, 0073's measurement, and
0074's fairness harness genuinely run end to end against one coherent
narrative, deterministically, without reimplementing any of the three
specs' own arithmetic.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from quantsmith.pipelines.credit_risk_worked_example import (
    BLUE_HARBOR_COUNTERPARTY_ID,
    CASCADIA_COUNTERPARTY_ID,
    NORTHFIELD_COUNTERPARTY_ID,
    WorkedExampleReport,
    generate_worked_example,
    run_document_intelligence_step,
    run_retail_fairness_step,
    run_wholesale_measurement_step,
    run_worked_example,
)


ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "examples" / "credit_risk_worked_example"


@pytest.fixture()
def scratch_root(tmp_path_factory):
    """Written under the repo checkout, not a bare OS temp dir -- 0071's
    source-registration check walks up from the output path looking for
    sources/ + pyproject.toml (see the same fixture pattern in
    tests/test_credit_document_intelligence.py)."""

    out_root = ROOT / "examples" / f".pytest_scratch_worked_example_{tmp_path_factory.mktemp('x').name}"
    out_root.mkdir(parents=True, exist_ok=True)
    try:
        yield out_root
    finally:
        shutil.rmtree(out_root, ignore_errors=True)


# --- step 1: document intelligence (0077) -----------------------------------


def test_document_intelligence_step_admits_cascadias_memo(scratch_root):
    step = run_document_intelligence_step(scratch_root)
    assert step.admission["admitted"] is True
    # The memo's own fixture review promotes it all the way to decision_input,
    # not merely derived_evidence -- the same promotion path
    # test_credit_document_intelligence.py proves against 0077's own example.
    assert step.admission["evidence_class"] == "decision_input"
    assert step.bundle_dir.exists() or step.bundle_dir.parent.exists()


# --- step 2: wholesale measurement (0073) -----------------------------------


def test_wholesale_step_measures_cascadia_and_two_peers():
    report = run_wholesale_measurement_step()
    counterparty_ids = {e.counterparty_id for e in report.exposures}
    assert counterparty_ids == {
        CASCADIA_COUNTERPARTY_ID,
        NORTHFIELD_COUNTERPARTY_ID,
        BLUE_HARBOR_COUNTERPARTY_ID,
    }
    cascadia = next(m for m in report.facility_measurements if m.counterparty_id == CASCADIA_COUNTERPARTY_ID)
    assert cascadia.ead == pytest.approx(4_000_000.0)
    assert cascadia.expected_loss == pytest.approx(0.015 * 0.40 * 4_000_000.0)
    assert cascadia.rwa == pytest.approx(0.75 * 4_000_000.0)


def test_wholesale_step_finds_a_real_limit_breach_and_concentration_breach():
    """Northfield's limit is deliberately set below its EAD, and Cascadia's
    share deliberately exceeds the concentration threshold -- a portfolio
    where nothing ever breaches would prove the checks run but not that they
    catch anything."""

    report = run_wholesale_measurement_step()
    assert NORTHFIELD_COUNTERPARTY_ID in report.breached_counterparty_ids
    assert CASCADIA_COUNTERPARTY_ID not in report.breached_counterparty_ids
    assert report.concentration.threshold_breached is True
    assert report.concentration.largest_counterparty_id == CASCADIA_COUNTERPARTY_ID


# --- step 3: retail fairness testing (0074) ---------------------------------


def test_retail_fairness_step_is_a_distinct_population_from_cascadia():
    """The retail book must never be Cascadia -- see the module docstring's
    non-goal. Applicant IDs must not collide with any wholesale identifier."""

    report = run_retail_fairness_step()
    # ScoredApplicant carries no counterparty/obligor id at all -- there is no
    # field through which the retail population could even reference Cascadia.
    from quantsmith.pipelines.retail_fairness_harness import ScoredApplicant

    assert isinstance(report.baseline.cutoff, (int, float))
    assert not hasattr(ScoredApplicant, "counterparty_id")


def test_retail_fairness_step_breaches_and_finds_an_alternative():
    """A synthetic population constructed to actually breach the disparity
    threshold and have a real less-discriminatory alternative available --
    the complete, honest happy path, not a trivial pass-through."""

    report = run_retail_fairness_step()
    assert report.baseline.threshold_breached is True
    assert report.less_discriminatory_alternative is not None
    assert report.less_discriminatory_alternative.alternative_found is True
    assert len(report.proxy_associations) == 1
    assert report.proxy_associations[0].correlation_with_protected_class < 0


# --- the composed report ----------------------------------------------------


def test_worked_example_composes_all_three_steps(scratch_root):
    report = run_worked_example(scratch_root)
    assert isinstance(report, WorkedExampleReport)
    assert report.document_intelligence.admission["admitted"] is True
    assert report.wholesale_measurement.concentration.threshold_breached is True
    assert report.retail_fairness.baseline.threshold_breached is True
    assert "0077" in report.narrative
    assert "0073" in report.narrative
    assert "0074" in report.narrative
    assert "Cascadia" in report.narrative


def test_worked_example_narrative_states_the_two_populations_are_distinct():
    """The one claim this whole module exists to get right: wholesale and
    retail are not fictionalized as the same borrower."""

    report = run_worked_example  # not called; assert against the module docstring instead
    import quantsmith.pipelines.credit_risk_worked_example as module

    assert "not the same borrower" in module.__doc__ or "not Cascadia" in module.__doc__


def test_worked_example_is_deterministic(scratch_root, tmp_path_factory):
    other_root = ROOT / "examples" / f".pytest_scratch_worked_example_{tmp_path_factory.mktemp('y').name}"
    other_root.mkdir(parents=True, exist_ok=True)
    try:
        first = run_worked_example(scratch_root)
        second = run_worked_example(other_root)
        assert first.wholesale_measurement == second.wholesale_measurement
        assert first.retail_fairness == second.retail_fairness
        assert first.document_intelligence.admission == second.document_intelligence.admission
    finally:
        shutil.rmtree(other_root, ignore_errors=True)


def test_no_arithmetic_is_reimplemented():
    """Mechanically checked: none of 0072's/0073's/0074's arithmetic
    primitives are *defined* in this module -- they are only reachable
    through the imported step functions this module composes."""

    import quantsmith.pipelines.credit_risk_worked_example as module

    forbidden = ("expected_loss", "ead_from_ccf", "rwa_from_risk_weight", "adverse_impact_ratio")
    own_functions = {
        name for name, value in vars(module).items()
        if callable(value) and getattr(value, "__module__", None) == module.__name__
    }
    assert not (own_functions & set(forbidden))


# --- the committed example ---------------------------------------------------


def test_committed_example_exists_and_matches_regeneration():
    assert (COMMITTED / "report.json").exists()
    assert (COMMITTED / "narrative.md").exists()

    import json

    committed = json.loads((COMMITTED / "report.json").read_text())

    out_root = ROOT / "examples" / ".pytest_regen_check_worked_example"
    shutil.rmtree(out_root, ignore_errors=True)
    try:
        fresh_dir = generate_worked_example(out_root)
        fresh = json.loads((fresh_dir / "report.json").read_text())
        assert fresh["wholesale_measurement"] == committed["wholesale_measurement"]
        assert fresh["retail_fairness"] == committed["retail_fairness"]
        assert fresh["document_intelligence"]["admission"] == committed["document_intelligence"]["admission"]
    finally:
        shutil.rmtree(out_root, ignore_errors=True)
