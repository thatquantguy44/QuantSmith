"""Acceptance tests for spec 0086 -- Central Asia regional lead.

All values are synthetic (spec 0025).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantsmith.pipelines.venture_ingestion import normalize_name, resolve_entities, script_of
from quantsmith.pipelines.venture_pack import (
    load_pack, localized_number, run_golden_cases, validate_pack,
)

ROOT = Path(__file__).resolve().parents[1]
LEAD = ROOT / "agents/venture_intelligence/central_asia/regional_lead"


def test_ac001_lead_contract():
    for f in ("README.md", "instructions.md", "tasks.md", "prompt.md"):
        assert (LEAD / f).is_file()
    t = (LEAD / "README.md").read_text(encoding="utf-8")
    for m in ("Kazakhstan", "Uzbekistan", "Kyrgyzstan", "Tajikistan", "Turkmenistan"):
        assert m in t
    assert "never does the following" in t


def test_ac002_cyrillic_cross_script_and_suffixes():
    assert script_of("ООО «Ромашка»") == "cyrillic"
    r = resolve_entities({"name": "ТОО Алем Технологии", "jurisdiction": "KZ"},
                         {"name": "Alem Technologies LLP", "jurisdiction": "KZ"})
    assert r["decision"] == "candidate_cross_script"
    for original, expected in {"ООО «Ромашка»": "ромашка", "ТОО Алем Технологии": "алем технологии",
                               "Alem Technologies LLP": "alem technologies",
                               "MChJ Yangi Texnologiya": "yangi texnologiya"}.items():
        before = original
        assert normalize_name(original) == expected and original == before
    same = resolve_entities({"name": "ТОО Алем", "jurisdiction": "KZ", "registry_id": "SYN-9"},
                            {"name": "Alem Technologies LLP", "jurisdiction": "KZ", "registry_id": "SYN-9"})
    assert same["decision"] == "match"


def test_ac003_russian_locale_numbers():
    conv = load_pack(ROOT)["conventions"]
    assert localized_number("1 250 000,5", "ru", conv) == 1250000.5
    assert localized_number("2 000 000", "kk", conv) == 2_000_000
    assert localized_number("2 000", "uz", conv) == 2000
    with pytest.raises(ValueError):
        localized_number("1 250", "xx", conv)


def test_ac004_pack_conventions_and_validator():
    pack = load_pack(ROOT)
    assert validate_pack(pack, ROOT) == []
    assert run_golden_cases(pack) == []
    ids = {c["id"] for c in pack["golden_cases"]["cases"]}
    assert {"golden.ru_locale", "golden.ru_locale_nbsp"} <= ids
    assert "script_variant_rule" in pack["conventions"]["normalization"]
    assert "Script Variant" in {t["term"] for t in pack["glossary"]["terms"]}


def test_ac005_coverage_and_roadmap():
    cov = load_pack(ROOT)["coverage"]
    agents = {a["id"]: a for a in cov["agents"]}
    assert agents["central_asia_lead"]["status"] == "built"
    assert agents["central_asia_lead"]["creating_spec"] == "0086"
    assert agents["caucasus_lead"]["status"] == "planned"
    assert agents["caucasus_lead"]["creating_spec"] == "0087"
    closes = [c for r in cov["roadmap"] for c in r["closes"]]
    assert len(closes) == len(set(closes)) == len(agents)


def test_ac006_indexes():
    assert "central_asia/regional_lead/" in (ROOT / "agents/README.md").read_text(encoding="utf-8")
    assert "central_asia" in (ROOT / "instructions/venture_intelligence.md").read_text(encoding="utf-8")
    assert "### Script Variant" in (ROOT / "agentic_dictionary.md").read_text(encoding="utf-8")


def test_ac008_latin_lookalikes_not_stripped():
    assert normalize_name("Too Good Company") == "too good company"
    assert normalize_name("Ao Ventures") == "ao ventures"
