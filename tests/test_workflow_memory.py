"""Tests for spec 0048 — workflow memory runtime (T-001, T-003, T-005).

One test per acceptance criterion, named for the AC it verifies, so the
coverage map in ``specs/0048-workflow-memory-runtime/tasks.md`` can be checked
mechanically rather than by assertion.

The committed store under ``memory/`` is the fixture for the "parses unchanged"
criteria — the point of NFR-003 is that real files written under spec 0002 load
without edits. Malformed fixtures are written to ``tmp_path``; broken YAML is
never committed.
"""

from __future__ import annotations

import datetime
import pathlib

import pytest

from quantsmith.pipelines.workflow_memory import (
    MemoryParseError,
    Record,
    build_record,
    load_records,
    parse_memory_file,
    point_in_time_filter,
    type_rule_admits,
    validate,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
STORE_FILES = (
    REPO_ROOT / "memory/_shared/datasets/example_prices/provenance.yaml",
    REPO_ROOT / "memory/quant_researcher/index.yaml",
)


def _committed_records():
    records = []
    for path in STORE_FILES:
        records.extend(load_records(path.read_text(), str(path)))
    return records


def _record(**overrides) -> Record:
    """A minimal valid record; override one field per test."""
    base = dict(
        id="MEM-T-0001",
        scope="field:x",
        type="quirk",
        statement="s",
        confidence="high",
        corroboration_count=1,
        first_seen=datetime.date(2020, 1, 1),
        last_confirmed=datetime.date(2020, 1, 1),
        status="active",
        pit_scope="<= run date",
    )
    base.update(overrides)
    return Record(**base)


# --------------------------------------------------------------------------
# T-001 — parsing
# --------------------------------------------------------------------------

def test_committed_store_loads_unchanged_AC_001():
    """Every file spec 0002 committed parses into typed records, no edits."""
    records = _committed_records()
    ids = {r.id for r in records}
    assert ids == {
        "MEM-0001", "MEM-0002", "MEM-0003", "MEM-QR-0001", "MEM-QR-0002"
    }
    by_id = {r.id: r for r in records}
    # Spot-check that values survived typing, not just that keys were found.
    assert by_id["MEM-0001"].type == "schema"
    assert by_id["MEM-0001"].first_seen == datetime.date(2026, 3, 1)
    assert by_id["MEM-0002"].pit_scope == "original vintage only"
    assert by_id["MEM-QR-0001"].scope == "dataset:example_prices"
    # A colon inside a value must not be read as a key separator.
    assert by_id["MEM-0001"].scope == "field:security_id"


def test_unsupported_yaml_raises_with_location_AC_015():
    """Outside the subset we raise with a location — never a silent guess."""
    with pytest.raises(MemoryParseError) as exc:
        parse_memory_file("records:\n  - id: A\n    tags: [a, b]\n", "f.yaml")
    assert exc.value.file == "f.yaml"
    assert exc.value.line == 3
    with pytest.raises(MemoryParseError):
        parse_memory_file("a:\n\tb: 1\n", "f.yaml")  # tab indentation


def test_evidence_singular_and_list_forms_AC_022():
    """0002's single mapping and 0048's list both parse; count is distinct runs."""
    singular = build_record({
        "id": "A", "scope": "s", "type": "quirk", "statement": "x",
        "confidence": "low", "first_seen": datetime.date(2020, 1, 1),
        "last_confirmed": datetime.date(2020, 1, 1), "status": "active",
        "pit_scope": "<= run date",
        "evidence": {"source_run": "run-1"},
    })
    listed = build_record({
        "id": "B", "scope": "s", "type": "quirk", "statement": "x",
        "confidence": "low", "first_seen": datetime.date(2020, 1, 1),
        "last_confirmed": datetime.date(2020, 1, 1), "status": "active",
        "pit_scope": "<= run date",
        "evidence": [
            {"source_run": "run-1"}, {"source_run": "run-2"},
            {"source_run": "run-1"},  # repeat of run-1 must not double-count
        ],
    })
    assert singular.corroboration_derived == 1
    assert listed.corroboration_derived == 2


# --------------------------------------------------------------------------
# T-003 — point-in-time (REQ-003, REQ-016)
# --------------------------------------------------------------------------

def test_pit_scope_excludes_original_vintage_AC_004():
    """'original vintage only' is out of a bounded query, in an unbounded one."""
    rec = _record(id="V", pit_scope="original vintage only")
    assert point_in_time_filter([rec], datetime.date(2030, 1, 1)) == []
    # Unbounded: no as-of, so the caller sees it.
    assert rec.pit_scope == "original vintage only"

    # An unrecognised value is excluded too -- the failure is a missing record,
    # never a leaked one.
    unknown = _record(id="U", pit_scope="whenever you like")
    assert point_in_time_filter([unknown], datetime.date(2030, 1, 1)) == []


def test_mechanical_type_is_timeless_AC_016():
    """A quirk recorded in 2026 is admissible as of 2020.

    It describes how the data is built. "Tickers get reused" was true in 2005;
    nobody had written it down. Excluding it makes a backtest re-learn a
    mechanical fact, with no leakage benefit.
    """
    as_of = datetime.date(2020, 1, 1)
    for mechanical in ("schema", "quirk", "pitfall"):
        rec = _record(
            type=mechanical,
            first_seen=datetime.date(2026, 1, 1),
            last_confirmed=datetime.date(2026, 6, 1),
        )
        assert type_rule_admits(rec, as_of) is True
        assert point_in_time_filter([rec], as_of) == [rec]


def test_predictive_type_bounded_by_last_confirmed_AC_017():
    """A pattern first seen 2018 but confirmed 2026 is excluded as of 2020.

    Bounding on first_seen would admit it. The record as it stands was shaped
    by data through 2026 -- corroboration is where the future enters.
    """
    rec = _record(
        type="pattern",
        first_seen=datetime.date(2018, 1, 1),
        last_confirmed=datetime.date(2026, 1, 1),
    )
    assert type_rule_admits(rec, datetime.date(2020, 1, 1)) is False
    assert point_in_time_filter([rec], datetime.date(2020, 1, 1)) == []
    # Once as_of reaches last_confirmed it becomes admissible.
    assert type_rule_admits(rec, datetime.date(2026, 1, 1)) is True


def test_decision_bounded_by_first_seen_AC_018():
    """A decision is an event: it exists from when it was made, not before."""
    rec = _record(
        type="decision",
        first_seen=datetime.date(2026, 6, 2),
        last_confirmed=datetime.date(2026, 6, 2),
    )
    assert type_rule_admits(rec, datetime.date(2020, 1, 1)) is False
    assert type_rule_admits(rec, datetime.date(2027, 1, 1)) is True


def test_type_rule_and_pit_scope_are_independent():
    """Both rules must pass; the weaker cannot override the stronger.

    pit_scope is free text, so it must not be able to admit a record the
    type rule excludes.
    """
    rec = _record(
        type="pattern",
        first_seen=datetime.date(2018, 1, 1),
        last_confirmed=datetime.date(2026, 1, 1),
        pit_scope="<= run date",  # permissive
    )
    assert point_in_time_filter([rec], datetime.date(2020, 1, 1)) == []


def test_committed_store_point_in_time_as_of_2020():
    """The real store, filtered to 2020: mechanics survive, claims do not."""
    records = _committed_records()
    got = {r.id for r in point_in_time_filter(records, datetime.date(2020, 1, 1))}
    # MEM-0002 is mechanical but 'original vintage only'; QR-0001/0002 encode
    # 2026 knowledge.
    assert got == {"MEM-0001", "MEM-0003"}


# --------------------------------------------------------------------------
# T-005 — validation (REQ-005, REQ-009, REQ-010)
# --------------------------------------------------------------------------

def test_missing_last_confirmed_flagged_AC_006():
    """A structurally incomplete record is an error, not a silent skip."""
    with pytest.raises(MemoryParseError) as exc:
        build_record({"id": "A", "scope": "s", "type": "quirk",
                      "statement": "x", "confidence": "low",
                      "first_seen": datetime.date(2020, 1, 1),
                      "status": "active", "pit_scope": "<= run date"},
                     file="f.yaml")
    assert "last_confirmed" in str(exc.value)


def test_duplicate_id_flagged_AC_007():
    findings = validate([_record(id="DUP"), _record(id="DUP")])
    assert any(f.record_id == "DUP" and f.severity == "error"
               and "duplicate" in f.message for f in findings)


def test_date_order_flagged_AC_008():
    rec = _record(
        first_seen=datetime.date(2026, 5, 1),
        last_confirmed=datetime.date(2026, 1, 1),
    )
    findings = validate([rec])
    assert any("precedes first_seen" in f.message and f.severity == "error"
               for f in findings)


def test_email_author_flagged_and_agrees_with_pii_scan_AC_013():
    """An address as authorship is an error; the '@' guard is structural."""
    findings = validate([_record(author="someone@example.com")])
    assert any(f.severity == "error" and "pseudonymous handle" in f.message
               for f in findings)
    # A well-formed handle passes.
    assert not [f for f in validate([_record(author="a1b2c3d4")])
                if f.severity == "error"]


def test_unknown_enum_values_flagged():
    """type/confidence/status are vocabularies, and every breach is reported."""
    rec = _record(type="rumour", confidence="certain", status="probably")
    messages = " ".join(f.message for f in validate([rec]) if f.severity == "error")
    assert "unknown type" in messages
    assert "unknown confidence" in messages
    assert "unknown status" in messages


def test_unrecognised_pit_scope_reported_as_warning():
    """Excluded at read time (AC-004) AND reported, so it is not silent."""
    findings = validate([_record(pit_scope="whenever")])
    assert any(f.severity == "warn" and "EXCLUDED" in f.message for f in findings)


def test_committed_store_validates_with_only_author_findings():
    """The real store is structurally sound; its only gap is authorship.

    This is the negative control for the gate: if validate() ever reports an
    error against the committed store, either the store or the runtime broke.
    """
    findings = validate(_committed_records())
    assert [f.severity for f in findings] == ["info"] * 5
    assert all("no author" in f.message for f in findings)
