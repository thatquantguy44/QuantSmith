"""Acceptance tests for spec 0085 -- Greater China & East Asia, South Asia.

All values are synthetic arithmetic examples (spec 0025).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantsmith.pipelines.venture_pack import (
    cn_number, era_to_gregorian, load_pack, run_golden_cases, validate_pack,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "agents/venture_intelligence"
FILES = ("README.md", "instructions.md", "tasks.md", "prompt.md")


def _text(rel):
    return (BASE / rel / "README.md").read_text(encoding="utf-8")


def test_ac001_east_asia_lead():
    for f in FILES:
        assert (BASE / "greater_china_east_asia/regional_lead" / f).is_file()
    t = _text("greater_china_east_asia/regional_lead")
    for market in ("Mainland China", "Hong Kong", "Taiwan", "Japan", "South Korea"):
        assert market in t
    assert "CNH" in t and "CNY" in t


def test_ac002_structure_analyst_boundaries():
    for f in FILES:
        assert (BASE / "greater_china_east_asia/entity_structure_analyst" / f).is_file()
    t = _text("greater_china_east_asia/entity_structure_analyst")
    assert "sovereign_adjacent" in t and "decision_support_only" in t
    assert "contractual" in t and "source span" in t
    assert "conclude that any government or party controls" in t


def test_ac003_south_asia_lead():
    for f in FILES:
        assert (BASE / "south_asia/regional_lead" / f).is_file()
    t = _text("south_asia/regional_lead")
    assert "lakh" in t and "crore" in t and "fiscal" in t.lower()


def test_ac004_conventions_present_and_draft():
    n = load_pack(ROOT)["conventions"]["normalization"]
    symbols = {u["symbol"] for u in n["numeral_units"]}
    assert {"萬", "億", "만", "억", "조", "lakh", "crore"} <= symbols
    eras = {e["id"] for e in n["calendar_offsets"]}
    assert {"norm.reiwa", "norm.heisei", "norm.showa"} <= eras
    assert {f["market"] for f in n["fiscal_year_conventions"]} >= {"India", "Japan"}
    assert any(a["symbol"] == "兆" for a in n["ambiguous_symbols"])
    for rec in n["numeral_units"] + n["calendar_offsets"] + n["fiscal_year_conventions"]:
        assert rec["citation"].strip() and rec["review_status"] == "draft"


def test_ac005_parsing_and_ambiguity():
    assert cn_number("2.5億") == 250_000_000
    assert cn_number("350억") == 35_000_000_000
    assert cn_number("1.2조") == 1_200_000_000_000
    assert cn_number("5.2 lakh") == 520_000
    assert cn_number("12 crore") == 120_000_000
    conv = load_pack(ROOT)["conventions"]
    assert era_to_gregorian("norm.reiwa", 6, conv) == 2024
    assert era_to_gregorian("norm.heisei", 30, conv) == 2018
    with pytest.raises(ValueError):
        cn_number("3兆")
    with pytest.raises(ValueError):
        cn_number("3 zorkmids")
    with pytest.raises(ValueError):
        era_to_gregorian("norm.nonesuch", 1, conv)
    assert run_golden_cases(load_pack(ROOT)) == []


def test_ac006_indexes_and_validator():
    pack = load_pack(ROOT)
    assert validate_pack(pack, ROOT) == []
    built = {a["id"] for a in pack["coverage"]["agents"] if a["status"] == "built"}
    assert {"greater_china_east_asia_lead", "south_asia_lead",
            "greater_china_east_asia_entity_structure_analyst"} <= built
    catalog = (ROOT / "agents/README.md").read_text(encoding="utf-8")
    for p in ("greater_china_east_asia/regional_lead/", "greater_china_east_asia/entity_structure_analyst/",
              "south_asia/regional_lead/"):
        assert p in catalog
    terms = {t["term"] for t in pack["glossary"]["terms"]}
    assert {"VIE Structure", "Era Year", "Fiscal Year-End Convention"} <= terms


def test_ac008_new_conventions_cited_or_unverified_and_synthetic():
    pack = load_pack(ROOT)
    assert pack["golden_cases"]["synthetic"] is True
    for t in pack["glossary"]["terms"]:
        assert t["citation"].strip()
