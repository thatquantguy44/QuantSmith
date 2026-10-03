"""Acceptance tests for spec 0088 -- venture sources, PIT ingestion, entity resolution.

All records are synthetic (spec 0025).
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from quantsmith.pipelines.venture_ingestion import (
    as_of_view, build_fact, cohort_rate, derive_known_at, form_cohort,
    normalize_name, resolve_entities, script_of,
)
from quantsmith.pipelines.venture_pack import FACT_FIELDS, load_pack

ROOT = Path(__file__).resolve().parents[1]
VENTURE_SOURCES = ("patentsview", "openalex", "usaspending", "sbir_gov", "gleif_lei",
                   "trade_csl", "opensanctions", "uk_companies_house", "gh_archive",
                   "gdelt", "venture_fixture")


def test_ac001_sources_declare_known_at_policy():
    policies = {p["id"] for p in load_pack(ROOT)["conventions"]["known_at_policies"]["policies"]}
    index = (ROOT / "sources/README.md").read_text(encoding="utf-8")
    for sid in VENTURE_SOURCES:
        text = (ROOT / "sources" / f"{sid}.yml").read_text(encoding="utf-8")
        m = re.search(r'known_at_policy: "(\w+)"', text)
        assert m and m.group(1) in policies, sid
        assert f"`{sid}`" in index


def test_ac002_derive_known_at_per_policy_and_missing_field():
    raw = {"event_time": "2026-01-01", "announced_time": "2026-01-05",
           "filed_time": "2026-01-10", "retrieved_time": "2026-02-01"}
    assert derive_known_at(raw, "filed")["known_at"] == "2026-01-10"
    assert derive_known_at(raw, "published")["known_at"] == "2026-01-05"
    assert derive_known_at(raw, "event")["known_at"] == "2026-01-01"
    assert derive_known_at(raw, "snapshot")["known_at"] == "2026-02-01"
    with pytest.raises(ValueError):
        derive_known_at({"event_time": "2026-01-01"}, "filed")
    with pytest.raises(ValueError):
        derive_known_at(raw, "guess")


def _fact(entity, known, retrieved, value=1, field="x"):
    raw = {"entity_id": entity, "value": value, "field": field, "filed_time": known,
           "retrieved_time": retrieved}
    return build_fact(raw, "filed", "synthetic.source", "B2")


def test_ac003_late_retrieval_flag_and_exclusion():
    late = _fact("synthetic.a", "2025-01-01", "2026-02-05")        # ~400 days
    ok = _fact("synthetic.b", "2025-01-01", "2025-01-03")
    assert late["late_retrieval"] is True and ok["late_retrieval"] is False
    view = as_of_view([late, ok], "2026-12-31", exclude_late=True)
    assert [f["entity_id"] for f in view] == ["synthetic.b"]
    assert len(as_of_view([late, ok], "2026-12-31")) == 2
    assert set(FACT_FIELDS) <= set(late)


def test_ac004_as_of_excludes_future_and_picks_latest():
    facts = [_fact("synthetic.a", "2026-01-01", "2026-01-01", value=1),
             _fact("synthetic.a", "2026-03-01", "2026-03-01", value=2),
             _fact("synthetic.a", "2026-06-01", "2026-06-01", value=3)]
    assert as_of_view(facts, "2026-04-01")[0]["value"] == 2
    assert as_of_view(facts, "2025-12-31") == []


def test_ac005_cohort_is_outcome_independent():
    universe = [{"entity_id": f"synthetic.c{i}", "first_known_at": "2020-01-01"} for i in range(10)]
    universe.append({"entity_id": "synthetic.late", "first_known_at": "2022-01-01"})
    cohort = form_cohort(universe, "2020-12-31")
    assert len(cohort) == 10 and "synthetic.late" not in cohort
    # six of the ten later vanish from a database; they stay in the denominator
    rate = cohort_rate(cohort, ["synthetic.c0", "synthetic.c1"])
    assert rate == {"numerator": 2, "denominator": 10, "rate": 0.2}


def test_ac006_resolution_decisions():
    a = {"name": "Acme Robotics Pte. Ltd.", "jurisdiction": "SG", "registry_id": "SYN-001"}
    assert resolve_entities(a, dict(a, name="ACME ROBOTICS"))["decision"] == "match"
    assert resolve_entities(a, dict(a, registry_id="SYN-002"))["decision"] == "no_match"
    n = {"name": "Acme Robotics Pte. Ltd.", "jurisdiction": "SG"}
    r = resolve_entities(n, {"name": "ACME ROBOTICS PTE LTD", "jurisdiction": "SG"})
    assert r["decision"] == "candidate" and r["reasons"]
    cross = resolve_entities({"name": "云舟科技有限公司", "jurisdiction": "CN"},
                             {"name": "Yunzhou Technology Co., Ltd.", "jurisdiction": "CN"})
    assert cross["decision"] == "candidate_cross_script"
    assert resolve_entities(n, {"name": "Acme Robotics", "jurisdiction": "MY"})["decision"] == "needs_registry_id"
    assert resolve_entities({"name": "X", "lei": "SYNLEI1"}, {"name": "Y", "lei": "SYNLEI1"})["decision"] == "match"
    assert resolve_entities({"name": "Alpha"}, {"name": "Beta"})["decision"] == "no_match"


def test_ac007_normalization_per_language_and_originals_untouched():
    cases = {"Acme Robotics Pte. Ltd.": "acme robotics", "PT Maju Jaya Tbk": "maju jaya",
             "深圳云舟科技有限公司": "深圳云舟科技", "บริษัท ตัวอย่าง จำกัด": "ตัวอย่าง",
             "Công ty cổ phần Ví Dụ": "ví dụ", "Sample Sdn. Bhd.": "sample"}
    for original, expected in cases.items():
        before = original
        assert normalize_name(original) == expected
        assert original == before
    assert script_of("深圳云舟") == "han" and script_of("ตัวอย่าง") == "thai"
    assert script_of("Acme") == "latin"


def test_ac008_entity_resolution_agent_contract():
    base = ROOT / "agents/venture_intelligence/entity_resolution"
    for f in ("README.md", "instructions.md", "tasks.md", "prompt.md"):
        assert (base / f).is_file()
    assert "never does the following" in (base / "README.md").read_text(encoding="utf-8")


def test_ac009_indexes_updated():
    pack = load_pack(ROOT)
    er = next(a for a in pack["coverage"]["agents"] if a["id"] == "entity_resolution_agent")
    assert er["status"] == "built"
    assert "entity_resolution" in (ROOT / "instructions/venture_intelligence.md").read_text(encoding="utf-8")
    assert "entity_resolution/" in (ROOT / "agents/README.md").read_text(encoding="utf-8")
    assert "Known-At Policy" in (ROOT / "agentic_dictionary.md").read_text(encoding="utf-8")


def test_ac010_deterministic():
    raw = {"entity_id": "synthetic.a", "value": 1, "filed_time": "2026-01-01", "retrieved_time": "2026-01-02"}
    assert build_fact(raw, "filed", "s", "B2") == build_fact(raw, "filed", "s", "B2")
    pair = ({"name": "A Pte. Ltd.", "jurisdiction": "SG"}, {"name": "A", "jurisdiction": "SG"})
    assert resolve_entities(*pair) == resolve_entities(*pair)


def test_ac011_sources_hold_no_credentials_and_label_unverified():
    for sid in VENTURE_SOURCES:
        text = (ROOT / "sources" / f"{sid}.yml").read_text(encoding="utf-8")
        assert 'credential_ref: "not_required_public_access"' in text
        assert "unverified" in text or sid == "venture_fixture"
