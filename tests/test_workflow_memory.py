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
    check_decay,
    format_record_line,
    load_records,
    parse_memory_file,
    point_in_time_filter,
    query,
    rank_key,
    render_context,
    store_version,
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
        "MEM-0001", "MEM-0002", "MEM-0003", "MEM-0004", "MEM-0005",
        "MEM-QR-0001", "MEM-QR-0002", "MEM-QR-0003", "MEM-QR-0004", "MEM-QR-0005",
    }
    by_id = {r.id: r for r in records}
    # Spot-check that values survived typing, not just that keys were found.
    assert by_id["MEM-0001"].type == "schema"
    assert by_id["MEM-0001"].first_seen == datetime.date(2026, 3, 1)
    assert by_id["MEM-0002"].pit_scope == "original vintage only"
    assert by_id["MEM-QR-0001"].scope == "dataset:example_prices"
    # A colon inside a value must not be read as a key separator.
    assert by_id["MEM-0001"].scope == "field:security_id"
    # Spot-check new records.
    assert by_id["MEM-0004"].type == "schema"
    assert by_id["MEM-QR-0003"].type == "pattern"


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


def test_depends_on_parses_list_and_string_forms():
    """``depends_on`` accepts a list or a single id, mirroring ``coexists``.

    Not validated yet (no cycle/dangling check) -- the field exists so a real
    record can carry the relation from the day it is written, distinct from
    ``coexists`` (two records that legitimately both hold, not one relying on
    the other).
    """
    a = build_record({
        "id": "A", "scope": "s", "type": "pattern", "statement": "x",
        "confidence": "low", "first_seen": datetime.date(2020, 1, 1),
        "last_confirmed": datetime.date(2020, 1, 1), "status": "active",
        "pit_scope": "<= run date",
        "depends_on": ["MEM-0002", "MEM-0001"],
    })
    b = build_record({
        "id": "B", "scope": "s", "type": "pattern", "statement": "x",
        "confidence": "low", "first_seen": datetime.date(2020, 1, 1),
        "last_confirmed": datetime.date(2020, 1, 1), "status": "active",
        "pit_scope": "<= run date",
        "depends_on": "MEM-0002",
    })
    assert a.depends_on == ("MEM-0002", "MEM-0001")
    assert b.depends_on == ("MEM-0002",)
    assert _record().depends_on == ()  # default: no dependency declared


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
    # MEM-0002: quirk but pit_scope="original vintage only" → excluded.
    # QR-0001/0002/0003/0005: encode 2026-dated knowledge (pattern/decision).
    # MEM-0004/0005 and MEM-QR-0004 are mechanical (schema/quirk/pitfall) → timeless.
    assert got == {"MEM-0001", "MEM-0003", "MEM-0004", "MEM-0005", "MEM-QR-0004"}


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

    The original five reference records carry declared corroboration_counts
    higher than their single evidence entry (by design — they are illustrative
    records, not a live run), so T-014 emits one warn per original record.
    The five new records have matching count=1 with one evidence entry, so they
    produce no corroboration warn. Errors are the real gate; warns here are
    expected and documented.
    """
    findings = validate(_committed_records())
    errors = [f for f in findings if f.severity == "error"]
    assert errors == [], f"unexpected errors: {errors}"
    info_findings = [f for f in findings if f.severity == "info"]
    assert len(info_findings) == 10  # one "no author" per record
    assert all("no author" in f.message for f in info_findings)
    warn_findings = [f for f in findings if f.severity == "warn"]
    assert len(warn_findings) == 5  # only original 5 records have mismatch
    assert all("corroboration_count" in f.message for f in warn_findings)


# --------------------------------------------------------------------------
# T-002 — query and deterministic ordering (REQ-002, NFR-002)
# --------------------------------------------------------------------------

def test_query_by_scope_AC_002():
    """A scope query returns only that scope's records."""
    got = query(_committed_records(), scope="field:volume", status=None)
    assert [r.id for r in got] == ["MEM-0003"]


def test_query_deterministic_AC_003():
    """The same query twice returns identical content AND order.

    The id tiebreak is what makes this true: without it, records equal on
    confidence/corroboration/date would come back in filesystem order.
    """
    records = _committed_records()
    first = query(records, status=None)
    second = query(list(reversed(records)), status=None)
    assert [r.id for r in first] == [r.id for r in second]
    # Ties on the first three keys must still be ordered, by id.
    tied = [_record(id="B", confidence="high"), _record(id="A", confidence="high")]
    assert [r.id for r in query(tied, status=None)] == ["A", "B"]


def test_query_filters_compose():
    """Filters are opt-in and stack; status defaults to active."""
    records = _committed_records()
    assert len(query(records)) == 10                     # all committed are active
    assert query(records, status="retired") == []
    hi = query(records, min_confidence="high", status=None)
    assert {r.id for r in hi} == {"MEM-0001", "MEM-0002", "MEM-QR-0001"}
    assert [r.id for r in query(records, type="decision", status=None)] == ["MEM-QR-0002"]


def test_query_as_of_applies_the_firewall():
    """as_of is opt-in; supplying it bounds the result to what was knowable."""
    records = _committed_records()
    assert len(query(records, status=None)) == 10
    bounded = query(records, status=None, as_of=datetime.date(2020, 1, 1))
    assert {r.id for r in bounded} == {
        "MEM-0001", "MEM-0003", "MEM-0004", "MEM-0005", "MEM-QR-0004"
    }


def test_rank_prefers_derived_corroboration_over_declared():
    """A larger declared count must not buy a higher rank."""
    liar = _record(id="LIAR", corroboration_count=99, evidence=({"source_run": "r1"},))
    honest = _record(id="HONEST", corroboration_count=1,
                     evidence=({"source_run": "r1"}, {"source_run": "r2"}))
    assert [r.id for r in sorted([liar, honest], key=rank_key)] == ["HONEST", "LIAR"]


# --------------------------------------------------------------------------
# T-004 — rendering (REQ-004)
# --------------------------------------------------------------------------

def test_render_budget_drops_lowest_ranked_AC_005():
    """A budget admitting two of three keeps the top two and says so."""
    high = _record(id="A", confidence="high", statement="alpha")
    med = _record(id="B", confidence="medium", statement="bravo")
    low = _record(id="C", confidence="low", statement="charlie")
    records = [low, high, med]

    full = render_context(records, budget_chars=10_000)
    assert full.index("[A]") < full.index("[B]") < full.index("[C]")
    assert "omitted" not in full

    header = "Known:"
    budget = len(header) + 1 + sum(
        len(format_record_line(r)) + 1 for r in (high, med))
    out = render_context(records, budget_chars=budget, header=header)
    assert "[A]" in out and "[B]" in out
    assert "[C]" not in out                     # lowest-ranked is the one dropped
    assert "1 further record(s) omitted" in out


def test_render_states_omission_even_when_nothing_fits():
    """A budget too small for any record still says what was withheld.

    Silently returning an empty block is how a workflow reasons from a store
    it thinks was empty.
    """
    out = render_context([_record(id="A")], budget_chars=5)
    assert "1 further record(s) omitted" in out


def test_render_empty_input_is_empty():
    assert render_context([]) == ""


def test_render_shows_last_confirmed_on_every_line():
    """Decay is advisory, so the date is how a reader discounts a stale record."""
    out = render_context(_committed_records(), budget_chars=10_000)
    body = [ln for ln in out.splitlines() if ln.startswith("- [")]
    assert len(body) == 10
    assert all("confirmed 20" in ln for ln in body)


# --------------------------------------------------------------------------
# T-014 — corroboration consistency (REQ-010)
# --------------------------------------------------------------------------

def test_corroboration_mismatch_reported_as_warn():
    """Declared count higher than derived is a warn — never an error or silent."""
    rec = _record(id="X", corroboration_count=5,
                  evidence=({"source_run": "r1"},))
    findings = validate([rec])
    assert any(f.severity == "warn" and "corroboration_count" in f.message
               for f in findings)


def test_high_confidence_single_run_warned():
    """confidence=high with only one distinct run is a warn."""
    rec = _record(id="Y", confidence="high", corroboration_count=1,
                  evidence=({"source_run": "r1"},))
    findings = validate([rec])
    assert any(f.severity == "warn" and "confidence=high" in f.message
               for f in findings)


def test_high_confidence_multi_run_no_warn():
    """Two distinct runs at confidence=high produce no corroboration warn."""
    rec = _record(id="Z", confidence="high", corroboration_count=2,
                  evidence=({"source_run": "r1"}, {"source_run": "r2"}))
    findings = [f for f in validate([rec]) if "corroboration" in f.message
                or "confidence=high" in f.message]
    assert findings == []


def test_no_evidence_no_corroboration_warn():
    """Records with no evidence entries and non-high confidence are not warned."""
    rec = _record(id="W", corroboration_count=1, confidence="low")  # no evidence → ()
    findings = [f for f in validate([rec])
                if "corroboration" in f.message or "confidence=high" in f.message]
    assert findings == []


# --------------------------------------------------------------------------
# T-015 — supersession integrity (REQ-015)
# --------------------------------------------------------------------------

def test_superseded_without_superseded_by_is_error():
    """status=superseded with no superseded_by field is an error."""
    rec = _record(id="OLD", status="superseded")
    findings = validate([rec])
    assert any(f.severity == "error" and "superseded_by" in f.message
               for f in findings)


def test_superseded_by_dangling_ref_is_error():
    """superseded_by pointing at a non-existent id is an error."""
    rec = _record(id="OLD", status="superseded", superseded_by="MEM-GHOST")
    findings = validate([rec])
    assert any(f.severity == "error" and "does not resolve" in f.message
               for f in findings)


def test_valid_supersession_no_error():
    """A resolved superseded_by chain produces no supersession error."""
    old = _record(id="OLD", status="superseded", superseded_by="NEW")
    new = _record(id="NEW", status="active")
    errors = [f for f in validate([old, new]) if f.severity == "error"
              and "superseded" in f.message]
    assert errors == []


def test_supersession_cycle_is_error():
    """A → B → A cycle is flagged as an error."""
    a = _record(id="A", status="superseded", superseded_by="B")
    b = _record(id="B", status="superseded", superseded_by="A")
    findings = validate([a, b])
    assert any(f.severity == "error" and "cyclic" in f.message for f in findings)


# --------------------------------------------------------------------------
# T-016 — contradiction candidates (REQ-016)
# --------------------------------------------------------------------------

def test_same_scope_type_without_coexists_is_info():
    """Two active records with the same scope+type draw an info finding."""
    r1 = _record(id="R1", scope="field:close_adj", type="quirk")
    r2 = _record(id="R2", scope="field:close_adj", type="quirk")
    findings = validate([r1, r2])
    assert any(f.severity == "info" and "shares scope" in f.message
               for f in findings)


def test_coexists_silences_contradiction_info():
    """coexists on either record suppresses the contradiction finding."""
    r1 = _record(id="R1", scope="field:close_adj", type="quirk", coexists=("R2",))
    r2 = _record(id="R2", scope="field:close_adj", type="quirk")
    findings = [f for f in validate([r1, r2])
                if "shares scope" in f.message]
    assert findings == []


def test_different_type_no_contradiction():
    """Same scope but different types are not a contradiction."""
    r1 = _record(id="R1", scope="field:x", type="quirk")
    r2 = _record(id="R2", scope="field:x", type="pattern")
    findings = [f for f in validate([r1, r2]) if "shares scope" in f.message]
    assert findings == []


# --------------------------------------------------------------------------
# T-006 — check_decay, T-008 — store_version
# --------------------------------------------------------------------------

def test_check_decay_flags_old_record():
    """A record confirmed 200 days ago is stale at 90-day freshness."""
    stale_date = datetime.date.today() - datetime.timedelta(days=200)
    rec = _record(id="STALE", last_confirmed=stale_date,
                  first_seen=stale_date, status="active")
    findings = check_decay([rec], freshness_days=90)
    assert len(findings) == 1
    assert findings[0].record_id == "STALE"
    assert findings[0].severity == "info"


def test_check_decay_fresh_record_not_flagged():
    """A recently confirmed record produces no finding."""
    fresh_date = datetime.date.today() - datetime.timedelta(days=10)
    rec = _record(id="FRESH", last_confirmed=fresh_date,
                  first_seen=fresh_date, status="active")
    assert check_decay([rec], freshness_days=90) == []


def test_check_decay_retired_not_flagged():
    """Retired or superseded records are not subject to decay."""
    old = datetime.date(2020, 1, 1)
    rec = _record(id="RET", last_confirmed=old, first_seen=old, status="retired")
    assert check_decay([rec], freshness_days=90) == []


def test_store_version_stable_across_order():
    """Same records in different order produce the same hash."""
    records = _committed_records()
    v1 = store_version(records)
    v2 = store_version(list(reversed(records)))
    assert v1 == v2
    assert len(v1) == 16


def test_store_version_changes_on_update():
    """A change to any record's statement changes the hash."""
    r1 = _record(id="A", statement="original")
    r2 = _record(id="A", statement="updated")
    assert store_version([r1]) != store_version([r2])
