"""Acceptance tests for spec 0083 -- venture & non-traditional intelligence foundation.

Each test names the acceptance criterion it proves. Rejection criteria are
proven by showing an invalid configuration actually fails.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re

import pytest

from quantsmith.pipelines.venture_pack import (
    REQUIRED_CHANNELS, REQUIRED_MODELS, VenturePackError, buddhist_to_gregorian,
    cn_number, confidence_label, fund_metrics, irr, load_pack, localized_number,
    ownership_after, post_money, roc_to_gregorian, run_golden_cases,
    source_grade_valid, survivorship_rates, validate_fact_record,
    validate_overlay, validate_or_raise, validate_pack,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def pack():
    return load_pack(ROOT)


def test_ac001_standard_states_rule_and_never_table():
    text = (ROOT / "instructions/venture_intelligence.md").read_text(encoding="utf-8")
    assert "inform, never decide" in text.lower()
    assert "Lawful collection" in text and "Never-table" in text


def test_ac002_taxonomy_resolves_and_no_person_profile(pack):
    assert validate_pack(pack, ROOT) == []
    bad = copy.deepcopy(pack)
    bad["taxonomy"]["relationship_types"][0]["to"] = "entity.nowhere"
    assert any("does not resolve" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(pack)
    bad["taxonomy"]["entity_types"].append(
        {"id": "entity.founder", "name": "Founder", "definition": "x",
         "is_person_derived": True, "citation": "unverified"})
    assert any("person" in e for e in validate_pack(bad, ROOT))


def test_ac003_convention_arithmetic_reproduces(pack):
    assert post_money(8_000_000, 2_000_000) == 10_000_000
    assert ownership_after(0.10, 8_000_000, 2_000_000) == pytest.approx(0.08)
    m = fund_metrics(100, 40, 90)
    assert (m["dpi"], m["rvpi"], m["tvpi"]) == pytest.approx((0.4, 0.9, 1.3))
    assert irr([[0.0, -100.0], [2.0, 121.0]]) == pytest.approx(0.10, abs=1e-9)
    assert run_golden_cases(pack) == []
    bad = copy.deepcopy(pack)
    bad["golden_cases"]["cases"][1]["expect"]["tvpi"] = 9.9
    assert any("tvpi" in e for e in run_golden_cases(bad))


def test_ac004_known_at_required_and_survivorship_differs(pack):
    rec = {f: "x" for f in pack["conventions"]["fact_record"]["required_fields"]}
    assert validate_fact_record(rec) == []
    rec["known_at"] = ""
    assert validate_fact_record(rec)
    del rec["known_at"]
    assert any("known_at" in e for e in validate_fact_record(rec))
    rates = survivorship_rates(20, 4, 12, 4)
    assert rates["biased_rate"] > rates["corrected_rate"]
    bad = copy.deepcopy(pack)
    bad["conventions"]["data_time"]["contracts"] = bad["conventions"]["data_time"]["contracts"][:-1]
    assert any("missing" in e for e in validate_pack(bad, ROOT))


def test_ac005_grade_confidence_and_sections(pack):
    conv = pack["conventions"]
    assert source_grade_valid("B2", conv) and not source_grade_valid("G9", conv)
    bands = conv["confidence_language"]["bands"]
    assert confidence_label(0.70, bands) == "likely"
    assert confidence_label(0.97, bands) == "almost certain"
    assert {"Evidence", "Assumptions", "Judgement"} <= set(conv["analytic_product"]["required_sections"])
    bad = copy.deepcopy(pack)
    bad["conventions"]["confidence_language"]["bands"][2]["low"] = 0.30
    assert any("contiguous" in e for e in validate_pack(bad, ROOT))


def test_ac006_channels_complete(pack):
    ids = {c["id"].split(".", 1)[1] for c in pack["channels"]["channels"]}
    assert REQUIRED_CHANNELS <= ids and len(REQUIRED_CHANNELS) == 10
    bad = copy.deepcopy(pack)
    bad["channels"]["channels"][0]["point_in_time"] = ""
    assert any("point_in_time" in e for e in validate_pack(bad, ROOT))


def test_ac007_glossary_and_dictionary_agree(pack):
    dic = (ROOT / "agentic_dictionary.md").read_text(encoding="utf-8")
    section = dic[dic.index("## Venture & Intelligence"):]
    headings = re.findall(r"^### (.+)$", section, re.M)
    terms = [t["term"] for t in pack["glossary"]["terms"]]
    assert sorted(headings) == sorted(terms)
    assert len({t.lower() for t in terms}) == len(terms)
    bad = copy.deepcopy(pack)
    bad["glossary"]["terms"].append(dict(bad["glossary"]["terms"][0]))
    assert any("duplicate term" in e for e in validate_pack(bad, ROOT))


def test_ac008_coverage_distinct_and_bounded(pack):
    bad = copy.deepcopy(pack)
    bad["coverage"]["agents"][1]["workflow"] = bad["coverage"]["agents"][0]["workflow"]
    assert any("duplicate workflow" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(pack)
    bad["coverage"]["agents"][0]["never"] = ""
    assert any("never-boundary" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(pack)
    bad["coverage"]["agents"][0]["path"] = "agents/venture_intelligence/does_not_exist"
    assert any("built agent" in e for e in validate_pack(bad, ROOT))


def test_ac009_model_catalog_complete(pack):
    ids = {m["id"].split(".", 1)[1] for m in pack["models"]["models"]}
    assert REQUIRED_MODELS <= ids
    bad = copy.deepcopy(pack)
    bad["models"]["models"][0]["baseline"] = ""
    assert any("baseline" in e for e in validate_pack(bad, ROOT))


def test_ac010_non_analytic_workflows_are_decision_support_only(pack):
    bad = copy.deepcopy(pack)
    wf = next(w for w in bad["workflows"]["workflows"] if w["decision_path_class"] == "sovereign_adjacent")
    wf["decision_support_only"] = False
    assert any("decision_support_only" in e for e in validate_pack(bad, ROOT))
    wf["decision_support_only"], wf["human_review"] = True, []
    assert any("human review" in e for e in validate_pack(bad, ROOT))


def test_ac011_gaps_owned_and_golden_deterministic(pack):
    assert run_golden_cases(pack) == run_golden_cases(pack) == []
    bad = copy.deepcopy(pack)
    bad["gaps"]["gaps"][0]["owner_spec"] = "0999"
    assert any("owner_spec" in e for e in validate_pack(bad, ROOT))


def test_ac012_validator_reports_zero_errors_and_raises_on_bad(pack):
    validate_or_raise(pack, ROOT)
    bad = copy.deepcopy(pack)
    bad["taxonomy"]["schema_version"] = "x"
    with pytest.raises(VenturePackError):
        validate_or_raise(bad, ROOT)


def test_ac013_plan_names_reuse_points():
    plan = (ROOT / "specs/0083-venture-intelligence-foundation/plan.md").read_text(encoding="utf-8")
    spec = (ROOT / "specs/0083-venture-intelligence-foundation/spec.md").read_text(encoding="utf-8")
    for ref in ("0070", "0071", "0052", "0025", "0026"):
        assert ref in spec
    assert "Child-spec roadmap" in plan


def test_ac014_overlay_refuses_prohibited_sources(pack):
    conv = pack["conventions"]
    ok = {"enabled_source_classes": ["public_registry"]}
    assert validate_overlay(ok, conv) == []
    assert validate_overlay({"enabled_source_classes": ["deanonymization"]}, conv)
    assert validate_overlay({"vendor_api_key": "abc123"}, conv)
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/venture_overlay.yml" in text
    assert (ROOT / "config/venture_overlay.example.yml").is_file()


def test_ac015_roadmap_reserved_in_specs_readme(pack):
    readme = (ROOT / "specs/README.md").read_text(encoding="utf-8")
    assert "0083-venture-intelligence-foundation" in readme and "0084" in readme
    assert [r["spec"] for r in pack["coverage"]["roadmap"]] == [f"{n:04d}" for n in range(84, 93)]


def test_ac016_workflows_name_agents_gates_class(pack):
    for w in pack["workflows"]["workflows"]:
        assert w["agents"] and w["inputs"] and w["outputs"] and w["review_gates"]
        assert w["decision_path_class"]


def test_ac018_fixtures_flagged_synthetic(pack):
    assert pack["golden_cases"]["synthetic"] is True
    blob = json.dumps(pack["golden_cases"])
    assert "synthetic" in blob


def test_ac019_every_claim_cited_or_unverified(pack):
    for group in ("valuation", "fund_metrics"):
        for rec in pack["conventions"][group]:
            assert rec["citation"].strip()
    for c in pack["channels"]["channels"]:
        assert c["citation"].strip()
    bad = copy.deepcopy(pack)
    bad["channels"]["channels"][0]["citation"] = ""
    assert any("citation" in e for e in validate_pack(bad, ROOT))


def test_ac020_normalization_rules_and_cases(pack):
    assert cn_number("3.5亿") == 350_000_000
    assert cn_number("1,200万") == 12_000_000
    assert buddhist_to_gregorian(2567) == 2024
    assert roc_to_gregorian(113) == 2024
    conv = pack["conventions"]
    assert localized_number("1.250.000,5", "id", conv) == 1_250_000.5
    assert localized_number("2.000.000", "vi", conv) == 2_000_000
    with pytest.raises(ValueError):
        localized_number("1,5", "xx", conv)
    suffixes = {s["suffix"] for s in conv["normalization"]["legal_form_suffixes"]}
    assert {"有限公司", "Pte. Ltd.", "Sdn. Bhd.", "PT", "บริษัท จำกัด"} <= suffixes


def test_ac021_regions_leads_and_contract_files(pack):
    base = ROOT / "agents/venture_intelligence"
    assert (base / "README.md").is_file()
    for agent in [a for a in pack["coverage"]["agents"] if a["status"] == "built"]:
        for f in ("README.md", "instructions.md", "tasks.md", "prompt.md"):
            assert (ROOT / agent["path"] / f).is_file()
    regional = {a["id"] for a in pack["coverage"]["agents"] if a["group"] == "regional"}
    assert len([r for r in regional if r.endswith("_lead")]) == 10


def test_ac022_review_signoff_rules(pack):
    from quantsmith.pipelines.venture_pack import review_summary, validate_review
    assert review_summary(pack)["reviewed"] == 0 and review_summary(pack)["total"] > 50
    base = {"id": "x", "citation": "NVCA Model Legal Documents (public)", "review_status": "draft", "review": None}
    assert validate_review(base) == []
    good = dict(base, review_status="reviewed",
                review={"reviewer": "A. Reviewer", "review_date": "2026-10-02", "scope": "definition"})
    assert validate_review(good) == []
    assert validate_review(dict(good, review=None))
    assert validate_review(dict(good, review=dict(good["review"], reviewer="")))
    assert validate_review(dict(good, review=dict(good["review"], review_date="yesterday")))
    assert validate_review(dict(base, review=good["review"]))            # draft carrying a review
    unv = dict(good, citation="unverified")
    assert validate_review(unv)
    assert validate_review(dict(unv, review=dict(good["review"], accepts_unverified=True))) == []
    bad = copy.deepcopy(pack)
    bad["channels"]["channels"][0]["review_status"] = "reviewed"
    assert any("without a review record" in e for e in validate_pack(bad, ROOT))
