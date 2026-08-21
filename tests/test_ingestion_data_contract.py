"""Acceptance tests for spec 0039 -- ingestion data contract emission.

Each test is named for the acceptance criterion it covers (see
``specs/0039-ingestion-data-contract/tasks.md``).
"""

from __future__ import annotations

import re

from quantsmith.pipelines.ingestion_data_contract import (
    ColumnSpec,
    PointInTimeSpec,
    QualityRule,
    render_data_contract,
    validate_ingestion,
)

SCHEMA = [
    ColumnSpec("date", "date", False, "Observation date"),
    ColumnSpec("security_id", "string", False, "Security identifier"),
    ColumnSpec("price", "float", False, "Close price"),
]
KEY_COLUMNS = ["date", "security_id"]
RULES = [
    QualityRule(
        "Max missing per column", "< 1%", "fail load / alert", column="price", max_missing_fraction=0.01,
    ),
    QualityRule("Duplicate keys", "0", "fail load"),
]
PIT = PointInTimeSpec("T+1 publication lag", True, "join on date <= as_of, never a future vintage")


def clean_rows():
    return [
        {"date": "2026-01-01", "security_id": "AAA", "price": 10.0},
        {"date": "2026-01-01", "security_id": "BBB", "price": 20.0},
        {"date": "2026-01-02", "security_id": "AAA", "price": 11.0},
    ]


# --- AC-001: type violation reported ---


def test_type_violation_reported_AC_001():
    rows = [
        {"date": "2026-01-01", "security_id": "AAA", "price": 10.0},
        {"date": "2026-01-02", "security_id": "BBB", "price": "not-a-number"},
    ]
    result = validate_ingestion(rows, SCHEMA, KEY_COLUMNS, RULES)
    violations = [v for v in result.schema_violations if v.column == "price"]
    assert len(violations) == 1
    assert violations[0].row_index == 1
    assert "float" in violations[0].reason


# --- AC-002: null in non-nullable column reported ---


def test_null_in_non_nullable_column_reported_AC_002():
    rows = [
        {"date": "2026-01-01", "security_id": "AAA", "price": 10.0},
        {"date": "2026-01-02", "security_id": None, "price": 10.0},
    ]
    result = validate_ingestion(rows, SCHEMA, KEY_COLUMNS, RULES)
    violations = [v for v in result.schema_violations if v.column == "security_id"]
    assert len(violations) == 1
    assert violations[0].row_index == 1
    assert "non-nullable" in violations[0].reason


# --- AC-003: duplicate key count matches actual duplicates ---


def test_duplicate_key_count_AC_003():
    rows = clean_rows() + [{"date": "2026-01-01", "security_id": "AAA", "price": 12.0}]
    result = validate_ingestion(rows, SCHEMA, KEY_COLUMNS, RULES)
    assert result.duplicate_key_count == 1


# --- AC-004: missingness rule observed value matches actual computed fraction ---


def test_missingness_rule_observed_matches_actual_AC_004():
    rows = [
        {"date": "2026-01-01", "security_id": "AAA", "price": 10.0},
        {"date": "2026-01-02", "security_id": "BBB", "price": None},
        {"date": "2026-01-03", "security_id": "CCC", "price": None},
        {"date": "2026-01-04", "security_id": "DDD", "price": 10.0},
    ]
    result = validate_ingestion(rows, SCHEMA, KEY_COLUMNS, RULES)
    assert result.missingness_by_column["price"] == 0.5
    price_rule_result = next(r for r in result.rule_results if r.rule.column == "price")
    assert "0.5000" in price_rule_result.observed
    assert price_rule_result.passed is False


# --- AC-005: clean rows produce no violations, every rule passes ---


def test_clean_rows_no_violations_AC_005():
    result = validate_ingestion(clean_rows(), SCHEMA, KEY_COLUMNS, RULES)
    assert result.schema_violations == []
    assert result.duplicate_key_count == 0
    assert all(r.passed for r in result.rule_results)
    assert result.is_clean is True


# --- AC-006: rendered contract has all six sections and satisfies the gate's own keyword checks ---

_GATE_THEMES = [
    r"schema|column|field|dtype|type",
    r"primary key|join key|unique key|key column|grain",
    r"point.in.time|as.of|availability|publication lag",
    r"missing|null|nan|completeness|coverage",
]

_REQUIRED_SECTIONS = [
    "## Grain & Keys",
    "## Schema",
    "## Point-in-Time Rules",
    "## Missingness & Quality Rules",
    "## Lineage & Access",
    "## Change Policy",
]


def test_rendered_contract_satisfies_gate_keywords_AC_006():
    result = validate_ingestion(clean_rows(), SCHEMA, KEY_COLUMNS, RULES)
    doc = render_data_contract(
        "Test Dataset", "Quant Research", "test_source", SCHEMA, KEY_COLUMNS,
        "one row per (date, security_id)", PIT, result,
        "Upstream: test_source", "daily", "Breaking changes require a version bump.",
    )
    for section in _REQUIRED_SECTIONS:
        assert section in doc
    for pattern in _GATE_THEMES:
        assert re.search(pattern, doc, re.IGNORECASE | re.DOTALL), f"gate theme not satisfied: {pattern}"


# --- AC-007: duplicate keys stated explicitly, never a default "unique" statement ---


def test_duplicate_keys_stated_not_default_AC_007():
    rows = clean_rows() + [{"date": "2026-01-01", "security_id": "AAA", "price": 12.0}]
    result = validate_ingestion(rows, SCHEMA, KEY_COLUMNS, RULES)
    doc = render_data_contract(
        "Test Dataset", "Quant Research", "test_source", SCHEMA, KEY_COLUMNS,
        "one row per (date, security_id)", PIT, result,
        "Upstream: test_source", "daily", "Breaking changes require a version bump.",
    )
    assert "NOT unique" in doc
    assert "1 duplicate key combination(s) found in the validated sample" in doc
    assert "the key is unique per grain — no duplicates found" not in doc


# --- AC-008: deterministic across repeated validate + render calls ---


def test_deterministic_AC_008():
    rows = clean_rows()
    r1 = validate_ingestion(rows, SCHEMA, KEY_COLUMNS, RULES)
    r2 = validate_ingestion(rows, SCHEMA, KEY_COLUMNS, RULES)
    assert r1 == r2

    doc1 = render_data_contract(
        "Test Dataset", "Quant Research", "test_source", SCHEMA, KEY_COLUMNS,
        "one row per (date, security_id)", PIT, r1,
        "Upstream: test_source", "daily", "Breaking changes require a version bump.",
    )
    doc2 = render_data_contract(
        "Test Dataset", "Quant Research", "test_source", SCHEMA, KEY_COLUMNS,
        "one row per (date, security_id)", PIT, r2,
        "Upstream: test_source", "daily", "Breaking changes require a version bump.",
    )
    assert doc1 == doc2
