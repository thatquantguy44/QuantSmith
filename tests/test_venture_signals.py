"""Acceptance tests for spec 0089 -- venture signal analysts and sourcing agents."""

from __future__ import annotations

import copy
from pathlib import Path
import re

from quantsmith.pipelines.venture_pack import load_pack, validate_pack

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "agents/venture_intelligence"
AGENTS = ("patent_ip_analyst", "hiring_signal_analyst", "narrative_news_analyst",
          "technology_landscape_analyst", "deal_sourcing", "company_diligence")
FILES = ("README.md", "instructions.md", "tasks.md", "prompt.md")


def _readme(name):
    return (BASE / name / "README.md").read_text(encoding="utf-8")


def test_ac001_patent_agent():
    t = _readme("patent_ip_analyst")
    assert "patent family" in t.lower() or "families" in t
    assert "publication or grant date" in t
    assert "legal validity" in t


def test_ac002_hiring_agent_person_adjacent():
    t = _readme("hiring_signal_analyst")
    assert "`person_adjacent`" in t
    assert "organization level" in t or "organization-level" in t
    assert "profile" in t and "individual" in t


def test_ac003_news_agent():
    t = _readme("narrative_news_analyst")
    assert "Syndication" in t or "syndication" in t
    assert "indicators" in t and "attribute" in t


def test_ac004_landscape_agent():
    t = _readme("technology_landscape_analyst")
    assert "single-channel" in t.lower()
    assert "assign a readiness level" in t


def test_ac005_sourcing_agent():
    t = _readme("deal_sourcing")
    assert "caller" in t and "formula" in t
    assert "rank companies by overall merit" in t


def test_ac006_diligence_agent():
    t = _readme("company_diligence")
    for section in ("Evidence", "Assumptions", "Judgement", "Open Gaps"):
        assert section in t
    assert "claim-versus-evidence" in t
    assert "approve, reject" in t


def test_ac007_workflow_class_must_cover_agent_classes():
    pack = load_pack(ROOT)
    assert validate_pack(pack, ROOT) == []
    bad = copy.deepcopy(pack)
    wf = next(w for w in bad["workflows"]["workflows"] if w["id"] == "workflow.signal_to_thesis")
    assert wf["decision_path_class"] == "person_adjacent"
    wf["decision_path_class"] = "analytic_support"
    assert any("stricter-class agent" in e for e in validate_pack(bad, ROOT))
    bad = copy.deepcopy(pack)
    wf = next(w for w in bad["workflows"]["workflows"] if w["id"] == "workflow.counter_diligence")
    wf["decision_path_class"] = "person_adjacent"
    assert any("must be sovereign_adjacent" in e for e in validate_pack(bad, ROOT))


def test_ac008_built_indexed_and_four_files():
    pack = load_pack(ROOT)
    cov = {a["id"]: a for a in pack["coverage"]["agents"]}
    catalog = (ROOT / "agents/README.md").read_text(encoding="utf-8")
    group = (BASE / "README.md").read_text(encoding="utf-8")
    standard = (ROOT / "instructions/venture_intelligence.md").read_text(encoding="utf-8")
    for name in AGENTS:
        assert cov[name]["status"] == "built" and cov[name]["creating_spec"] == "0089"
        for f in FILES:
            assert (BASE / name / f).is_file()
        assert f"venture_intelligence/{name}/" in catalog
        assert f"{name}/" in group and f"`{name}`" in standard
    assert cov["hiring_signal_analyst"]["decision_path_class"] == "person_adjacent"


def test_ac010_no_credentials_or_real_identifiers_in_new_agents():
    pattern = re.compile(r"AKIA[0-9A-Z]{16}|ghp_[0-9A-Za-z]{36}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
    for name in AGENTS:
        for f in FILES:
            assert not pattern.search((BASE / name / f).read_text(encoding="utf-8"))
