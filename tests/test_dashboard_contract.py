"""Acceptance tests for spec 0047 -- downstream consumer contract.

AC-002 (backward compatibility of the seven existing renderers) is covered by
the *existing* renderer test modules passing unmodified — `test_powerbi_profile.py`,
`test_excel_react_profiles.py`, and `test_bi_profiles.py`. That is the real
evidence, and it is evidence precisely because those files were not touched.

Each test is named for the acceptance criterion it covers (see
``specs/0047-downstream-contract/tasks.md``).
"""

from __future__ import annotations

from quantsmith.pipelines.dashboard_spec import (
    SCHEMA_VERSION,
    DashboardSpec,
    Panel,
    check_schema_compatibility,
)


def a_spec(**kwargs):
    return DashboardSpec(
        title="Macro",
        dataset="fred_gold",
        panels=(Panel(title="Level", chart_type="line", metric="gdp_level"),),
        **kwargs,
    )


# --- AC-001: construction exactly as before this change still works ---


def test_existing_construction_unchanged_AC_001():
    # Positional construction, as a pre-0047 caller would write it.
    spec = DashboardSpec(
        "Macro",
        "fred_gold",
        (Panel(title="Level", chart_type="line", metric="gdp_level"),),
    )
    assert spec.schema_version == SCHEMA_VERSION
    assert spec.page == "Overview"
    assert spec.metrics() == ("gdp_level",)

    # And an explicit version still round-trips.
    assert a_spec(schema_version="1.4").schema_version == "1.4"


# --- AC-003: a differing major is incompatible ---


def test_major_mismatch_incompatible_AC_003():
    result = check_schema_compatibility("2.0", consumer_version="1.0")
    assert result.compatible is False
    assert "major" in result.reason.lower()
    assert result.payload_version == "2.0"
    assert result.consumer_version == "1.0"

    # Older major is equally incompatible -- the contract changed either way.
    assert check_schema_compatibility("0.9", consumer_version="1.0").compatible is False


# --- AC-004: a newer minor is compatible, with a caveat ---


def test_newer_minor_compatible_with_caveat_AC_004():
    result = check_schema_compatibility("1.4", consumer_version="1.0")
    assert result.compatible is True
    assert result.reason, "a newer minor must state its caveat, not pass silently"
    assert "ignored" in result.reason


# --- AC-005: same or older minor is compatible, no caveat ---


def test_same_or_older_minor_compatible_AC_005():
    same = check_schema_compatibility("1.2", consumer_version="1.2")
    assert same.compatible is True and same.reason == ""

    older = check_schema_compatibility("1.1", consumer_version="1.5")
    assert older.compatible is True and older.reason == ""


# --- AC-006: a malformed version is rejected with a reason ---


def test_malformed_version_incompatible_AC_006():
    for bad in ("", "1", "abc", "x.y", "1.x"):
        result = check_schema_compatibility(bad, consumer_version="1.0")
        assert result.compatible is False, f"{bad!r} should not be accepted"
        assert result.reason

    # A malformed consumer version is caught too, not just the payload.
    assert check_schema_compatibility("1.0", consumer_version="nope").compatible is False


# --- default consumer version is the module's own ---


def test_default_consumer_version_is_module_constant():
    assert check_schema_compatibility(SCHEMA_VERSION).compatible is True
    assert check_schema_compatibility(SCHEMA_VERSION).reason == ""
