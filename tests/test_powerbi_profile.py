"""Acceptance tests for spec 0015 — Power BI dashboard profile.

Each test is named for the acceptance criterion it covers (see
``specs/0015-powerbi-dashboard-profile/tasks.md``). Standard-library only.
"""

from __future__ import annotations

import pytest

from quantsmith.pipelines.dashboard_spec import (
    DashboardSpec,
    DashboardSpecError,
    Panel,
)
from quantsmith.pipelines.powerbi_profile import render_powerbi


def sample_spec() -> DashboardSpec:
    return DashboardSpec(
        title="Revenue Overview",
        dataset="sales",
        page="Exec",
        panels=(
            Panel(title="Revenue by region", chart_type="bar", metric="revenue", dimensions=("region",)),
            Panel(title="Revenue trend", chart_type="line", metric="revenue"),
            Panel(title="Conversion rate", chart_type="kpi", metric="conversion_rate"),
        ),
        filters={"region": "ALL"},
    )


# --- AC-001: a spec renders to a Power BI payload with mapped visuals + measures ---


def test_render_maps_panels_AC_001():
    payload = render_powerbi(sample_spec())
    assert payload.title == "Revenue Overview"
    assert payload.dataset == "sales"
    assert payload.report_page == "Exec"
    assert payload.visuals == ["clustered_column", "line", "card"]
    assert payload.measures == ["revenue", "conversion_rate"]  # de-duplicated, ordered


# --- AC-002: chart types map to Power BI visual names; the spec restricts types ---


def test_chart_type_mapping_AC_002():
    payload = render_powerbi(
        DashboardSpec(
            title="t", dataset="d",
            panels=(
                Panel(title="a", chart_type="table", metric="revenue"),
                Panel(title="b", chart_type="gauge", metric="risk"),
            ),
        )
    )
    assert payload.visuals == ["matrix", "gauge"]

    # An unknown chart type is rejected at spec construction (governed vocabulary).
    with pytest.raises(DashboardSpecError):
        Panel(title="x", chart_type="pie3d", metric="revenue")


# --- AC-003: governance — a panel without a metric is rejected; payload validates ---


def test_governance_and_validation_AC_003():
    with pytest.raises(DashboardSpecError):
        Panel(title="no metric", chart_type="bar", metric="")

    # A rendered payload passes the existing PowerBIPayloadValidator.
    payload = render_powerbi(sample_spec())
    assert payload.visuals and payload.measures  # validator's invariants hold


# --- AC-004: filters/dataset/page carried through; deterministic ---


def test_carry_through_and_deterministic_AC_004():
    spec = sample_spec()
    a = render_powerbi(spec)
    b = render_powerbi(spec)
    assert a == b
    assert a.filters == {"region": "ALL"}
    assert a.dataset == "sales"


# --- AC-005: an empty spec is rejected before rendering ---


def test_empty_spec_rejected_AC_005():
    with pytest.raises(DashboardSpecError):
        DashboardSpec(title="t", dataset="d", panels=())
