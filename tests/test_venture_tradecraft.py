"""Acceptance tests for spec 0090 -- tradecraft and screening-support agents.

All values are synthetic (spec 0025).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantsmith.pipelines.venture_pack import load_pack, validate_pack
from quantsmith.pipelines.venture_tradecraft import (
    ach_matrix, band_label, candidate_channel_check, check_statement,
    conclusion_language_findings, corroboration_status, crosses_threshold,
    effective_ownership, grade_without_basis, orphan_requirements, parse_grade,
    requirement_age_days, sensitivity, vague_terms,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "agents/venture_intelligence"
AGENTS = ("source_reliability_grader", "confidence_language_reviewer",
          "competing_hypotheses_analyst", "collection_gap_tracker",
          "ownership_screen", "dual_use_indicator")


@pytest.fixture()
def conv():
    return load_pack(ROOT)["conventions"]


def _readme(name):
    return (BASE / name / "README.md").read_text(encoding="utf-8")


def test_ac001_grades_and_contract(conv):
    assert parse_grade("B2", conv) == ("B", "2")
    for bad in ("G9", "B", "B22", "b2"):
        with pytest.raises(ValueError):
            parse_grade(bad, conv)
    assert grade_without_basis() == "F6"
    t = _readme("source_reliability_grader")
    assert "`F` or `6`" in t and "override or replace a human analyst's grade" in t


def test_ac002_corroboration_statuses():
    items = [
        {"claim_id": "c1", "origin_id": "o1", "channel": "news"},
        {"claim_id": "c1", "origin_id": "o1", "channel": "news"},          # syndicated copy
        {"claim_id": "c2", "origin_id": "o1", "channel": "news"},
        {"claim_id": "c3", "origin_id": "o1", "channel": "news"},
        {"claim_id": "c3", "origin_id": "o2", "channel": "news"},
        {"claim_id": "c4", "origin_id": "o1", "channel": "news"},
        {"claim_id": "c4", "origin_id": "o3", "channel": "patents"},
    ]
    s = corroboration_status(items)
    assert s["c1"]["status"] == "echo" and s["c1"]["independent_origins"] == 1
    assert s["c2"]["status"] == "single_source"
    assert s["c3"]["status"] == "single_channel"
    assert s["c4"]["status"] == "corroborated" and s["c4"]["channels"] == 2


def test_ac003_wording_checks(conv):
    assert band_label(0.70, conv) == "likely"
    assert check_statement("likely", 0.70, conv)["ok"] is True
    miss = check_statement("very likely", 0.60, conv)
    assert miss["ok"] is False and miss["expected"] == "likely"
    text = "This may indicate growth and could be real, perhaps."
    found = vague_terms(text)
    assert [f["term"].lower() for f in found] == ["may", "could", "perhaps"]
    assert all(text[f["start"]:f["end"]] == f["term"] for f in found)
    with pytest.raises(ValueError):
        band_label(1.5, conv)


HYP = [{"id": "H1", "kind": "real_change"}, {"id": "H2", "kind": "deception_or_artifact"}]
EVID = [{"id": "E1", "weight": 2.0}, {"id": "E2", "weight": 1.0}, {"id": "E3", "weight": 1.0}]
RAT = {("E1", "H1"): "C", ("E1", "H2"): "I", ("E2", "H1"): "C", ("E2", "H2"): "C",
       ("E3", "H1"): "I", ("E3", "H2"): "C"}


def test_ac004_matrix_requires_deception_hypothesis_and_reports_structure():
    with pytest.raises(ValueError):
        ach_matrix([{"id": "H1", "kind": "real_change"}, {"id": "H3", "kind": "other"}], EVID, RAT)
    out = ach_matrix(HYP, EVID, RAT)
    assert out["inconsistency"] == {"H1": 1.0, "H2": 2.0}
    assert out["ordering_by_fewest_inconsistencies"] == ["H1", "H2"]
    assert out["diagnostic_evidence"] == ["E1", "E3"] and out["non_diagnostic_evidence"] == ["E2"]
    assert "not a conclusion" in out["note"]
    with pytest.raises(ValueError):
        ach_matrix(HYP, EVID, {**RAT, ("E1", "H1"): "X"})


def test_ac005_shared_origin_counts_once_and_sensitivity():
    ev = [{"id": "E1", "weight": 1.0, "origin_id": "o"}, {"id": "E1b", "weight": 1.0, "origin_id": "o"},
          {"id": "E3", "weight": 1.0}]
    rat = {("E1", "H1"): "I", ("E1", "H2"): "C", ("E1b", "H1"): "I", ("E1b", "H2"): "C",
           ("E3", "H1"): "C", ("E3", "H2"): "I"}
    out = ach_matrix(HYP, ev, rat)
    assert out["inconsistency"]["H1"] == 1.0          # not 2.0: one origin
    # removing E3 leaves H2 ahead of H1, so E3 is the swing item
    assert "E3" in sensitivity(HYP, ev, rat)


def test_ac006_collection_register_helpers(conv):
    assert candidate_channel_check("public_registry", conv) == "public_registry"
    for prohibited in conv["prohibited_source_classes"]:
        with pytest.raises(ValueError):
            candidate_channel_check(prohibited, conv)
    reg = [{"id": "R1", "decision": "invest/no-invest"}, {"id": "R2", "decision": " "}, {"id": "R3"},
           {"id": "R4", "decision": None}]
    assert orphan_requirements(reg) == ["R2", "R3", "R4"]                  # None is not a decision
    assert requirement_age_days("2026-09-01", "2026-10-02") == 31


EDGES = [
    {"owner": "H", "owned": "A", "pct": 0.6, "mechanism": "equity", "as_of": "2026-01-01"},
    {"owner": "A", "owned": "T", "pct": 0.5, "mechanism": "equity", "as_of": "2026-01-01"},
    {"owner": "H", "owned": "B", "pct": 0.4, "mechanism": "equity", "as_of": "2026-01-01"},
    {"owner": "B", "owned": "T", "pct": 0.25, "mechanism": "equity", "as_of": "2026-01-01"},
    {"owner": "H", "owned": "T", "pct": 1.0, "mechanism": "contract", "as_of": "2026-01-01"},
]


def test_ac007_effective_ownership_exact_and_guarded():
    out = effective_ownership(EDGES, "H", "T")
    assert out["effective"] == pytest.approx(0.4)
    assert sorted(p["product"] for p in out["paths"]) == pytest.approx([0.1, 0.3])
    assert out["excluded_links"] == [{"owner": "H", "owned": "T", "mechanism": "contract"}]
    cyc = EDGES[:4] + [{"owner": "T", "owned": "H", "pct": 0.1, "mechanism": "equity", "as_of": "2026-01-01"}]
    assert effective_ownership(cyc, "H", "T")["effective"] == pytest.approx(0.4)
    with pytest.raises(ValueError):
        effective_ownership([{"owner": "H", "owned": "T", "pct": 0.5, "mechanism": "equity", "as_of": ""}], "H", "T")
    with pytest.raises(ValueError):
        effective_ownership([{"owner": "H", "owned": "T", "pct": 1.5, "mechanism": "equity", "as_of": "2026-01-01"}], "H", "T")
    over = [{"owner": "H", "owned": "T", "pct": 0.8, "mechanism": "equity", "as_of": "2026-01-01"},
            {"owner": "H", "owned": "X", "pct": 0.5, "mechanism": "equity", "as_of": "2026-01-01"},
            {"owner": "X", "owned": "T", "pct": 0.5, "mechanism": "equity", "as_of": "2026-01-01"}]
    assert effective_ownership(over, "H", "T")["exceeds_one"] is True


def test_ac008_threshold_is_the_callers():
    r = crosses_threshold(0.4, 0.25)
    assert r["at_or_above"] is True and r["threshold_source"] == "caller"
    assert crosses_threshold(0.2, 0.25)["at_or_above"] is False


def test_ac009_conclusion_language_lint():
    text = "The structure is evading review and may be unlawful."
    found = conclusion_language_findings(text)
    assert {f["term"] for f in found} == {"evad", "unlawful"}
    assert all(text[f["start"]:f["end"]].lower() == f["term"] for f in found)
    assert conclusion_language_findings("Indicator: unresolved nominee layer, confidence low.") == []


def test_ac010_dual_use_contract():
    t = _readme("dual_use_indicator")
    assert "caller" in t and "questions for counsel" in t.lower()
    assert "rule on export-control classification" in t


def test_ac011_agents_built_indexed_and_pack_valid():
    pack = load_pack(ROOT)
    assert validate_pack(pack, ROOT) == []
    cov = {a["id"]: a for a in pack["coverage"]["agents"]}
    catalog = (ROOT / "agents/README.md").read_text(encoding="utf-8")
    group = (BASE / "README.md").read_text(encoding="utf-8")
    standard = (ROOT / "instructions/venture_intelligence.md").read_text(encoding="utf-8")
    for name in AGENTS:
        assert cov[name]["status"] == "built" and cov[name]["creating_spec"] == "0090"
        for f in ("README.md", "instructions.md", "tasks.md", "prompt.md"):
            assert (BASE / name / f).is_file()
        assert f"venture_intelligence/{name}/" in catalog and f"{name}/" in group and f"`{name}`" in standard
    assert cov["ownership_screen"]["decision_path_class"] == "sovereign_adjacent"
    assert cov["dual_use_indicator"]["decision_path_class"] == "sovereign_adjacent"


def test_ac012_deterministic():
    assert ach_matrix(HYP, EVID, RAT) == ach_matrix(HYP, EVID, RAT)
    assert effective_ownership(EDGES, "H", "T") == effective_ownership(EDGES, "H", "T")
