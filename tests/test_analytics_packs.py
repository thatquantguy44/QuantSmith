"""Acceptance tests for spec 0081 — analytics domain packs.

Each test names the acceptance criterion it proves. Rejection criteria are
proved by mutating an in-memory copy of a real pack and showing the validator
actually fails it; a test that only shows the committed catalog passing would
not prove the rule exists.
"""

from __future__ import annotations

import ast
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from quantsmith.pipelines import analytics_packs as ap

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def packs():
    return ap.load_packs(ROOT)


def _by_id(packs, pid):
    return copy.deepcopy(next(p for p in packs if p["pack_id"] == pid))


def _errors(findings):
    return [f for f in findings if f.severity == "error"]


def test_ac001_catalog_validates_clean(packs):
    """AC-001: the committed catalog has no errors and every pack is complete at 0081.1."""
    assert packs, "no packs loaded"
    assert _errors(ap.validate_catalog(packs, ROOT)) == []
    for p in packs:
        assert p["schema_version"] == ap.SCHEMA_VERSION
        assert all(k in p for k in ap._REQUIRED)
    bad = _by_id(packs, "market_risk")
    bad["schema_version"] = "0081.0"
    assert any("schema_version" in f.message for f in _errors(ap.validate_pack(bad, ROOT)))


COVERAGE = {
    "business_line": {"retail_deposits", "cards_consumer_lending", "mortgages_home_lending",
                      "commercial_banking", "treasury_cash_management", "trade_finance",
                      "investment_banking", "wealth_private_banking", "asset_management",
                      "payments", "custody_securities_services", "insurance"},
    "markets": {"equities_markets", "rates_fixed_income", "credit_markets", "fx_markets",
                "commodities_markets", "derivatives_structured", "digital_assets",
                "short_term_markets_funding", "securities_financing_prime", "sales_trading_execution"},
    "risk": {"credit_risk", "counterparty_risk_xva", "market_risk", "liquidity_risk",
             "treasury_alm_irrbb", "operational_risk", "model_risk", "climate_esg_risk"},
    "finance_treasury": {"finance_performance", "regulatory_capital_reporting"},
    "control_compliance": {"aml_financial_crime", "fraud", "consumer_compliance"},
    "operations": {"operations_settlement", "collections_recovery"},
    "cross_cutting": {"customer_marketing_analytics", "economics_macro", "portfolio_management_performance"},
}


def test_ac002_coverage_table_and_family_coverage(packs):
    """AC-002: every area in the spec's Coverage table has a pack; dropping a family errors."""
    fam_of = {p["pack_id"]: p["family"] for p in packs}
    for fam, ids in COVERAGE.items():
        for pid in ids:
            assert fam_of.get(pid) == fam, f"{pid} missing or not in {fam}"
    assert set(fam_of.values()) == set(ap.FAMILIES)
    without_ops = [p for p in packs if p["family"] != "operations"]
    msgs = [f.message for f in _errors(ap.validate_catalog(without_ops, ROOT))]
    assert any("family 'operations'" in m for m in msgs)


def test_ac003_rate_like_unit_needs_rationale_to_be_additive(packs):
    """AC-003: a pct metric declared additive errors unless it states a rationale."""
    p = _by_id(packs, "retail_deposits")
    m = next(x for x in p["metrics"] if x["name"] == "deposit_rate")
    m["additivity"] = "additive"
    # Keep golden cases consistent so only the additivity rule can fire.
    p["golden_cases"] = [g for g in p["golden_cases"] if g.get("metric") != "deposit_rate"]
    errs = _errors(ap.validate_pack(p, ROOT, file_stem=p["pack_id"]))
    assert any("deposit_rate" in f.message and "additivity_rationale" in f.message for f in errs)
    m["additivity_rationale"] = "test: declared on purpose"
    assert not any("additivity_rationale" in f.message
                   for f in _errors(ap.validate_pack(p, ROOT, file_stem=p["pack_id"])))


def test_ac004_can_sum_and_contributor_suppression(packs):
    """AC-004: additivity classes govern summing; non-additive metrics never get contributors."""
    assert (ap.can_sum({"additivity": "additive"}, "dimension"), ap.can_sum({"additivity": "additive"}, "time")) == (True, True)
    assert (ap.can_sum({"additivity": "semi_additive"}, "dimension"), ap.can_sum({"additivity": "semi_additive"}, "time")) == (True, False)
    assert (ap.can_sum({"additivity": "non_additive"}, "dimension"), ap.can_sum({"additivity": "non_additive"}, "time")) == (False, False)
    for p in packs:
        for m in p["metrics"]:
            if m["additivity"] == "non_additive":
                assert "contributor" in ap.suppressed_insights(p, m["name"]), (p["pack_id"], m["name"])
    mr = _by_id(packs, "market_risk")
    assert "contributor" in ap.suppressed_insights(mr, "var")
    assert "contributor" not in ap.suppressed_insights(mr, "stress_loss")


def test_ac005_selection_by_source_domain(packs):
    """AC-005: tags select intersecting packs in file-name order; unknown tags are reported."""
    sel = ap.select_packs(["macro", "fixed_income_rates"], packs)
    assert sel.pack_ids == ("economics_macro", "rates_fixed_income")
    assert sel.unmatched_domains == ()
    assert ap.select_packs(["macro", "fixed_income_rates"], packs) == sel
    none = ap.select_packs(["no_such_domain"], packs)
    assert none.pack_ids == () and none.unmatched_domains == ("no_such_domain",)


def test_ac006_term_conflicts_reported(packs):
    """AC-006: one term meaning different metrics in two selected packs is a conflict."""
    sel = ap.select_packs(["equities", "fx"], packs)
    assert {"equities_markets", "fx_markets"} <= set(sel.pack_ids)
    terms = dict(sel.synonym_conflicts)
    assert "vol" in terms
    assert terms["vol"] == ("equities_markets.realized_volatility", "fx_markets.implied_volatility")


def test_ac007_review_gate(packs):
    """AC-007: 'reviewed' needs reviewer and date; only all-reviewed selections allow write-back."""
    p = _by_id(packs, "fraud")
    p["review"]["status"] = "reviewed"
    msgs = [f.message for f in _errors(ap.validate_pack(p, ROOT))]
    assert any("named reviewer" in m for m in msgs) and any("reviewed_on" in m for m in msgs)
    p["review"].update(reviewer="Named Reviewer", reviewed_on="2026-09-24")
    assert not any("review" in f.message for f in _errors(ap.validate_pack(p, ROOT)))

    assert all(pk["review"]["status"] == "draft" for pk in packs)
    assert not ap.select_packs(["fraud"], packs).all_reviewed
    assert ap.select_packs(["fraud"], [p]).all_reviewed
    assert not ap.select_packs(["nothing"], [p]).all_reviewed


def test_ac008_reviewer_and_builds_on_must_exist(packs):
    """AC-008: nonexistent reviewer agents and builds_on paths are errors."""
    for p in packs:
        assert p["reviewer_agents"], p["pack_id"]
        for a in p["reviewer_agents"]:
            assert (ROOT / a / "prompt.md").is_file(), a
    p = _by_id(packs, "payments")
    p["reviewer_agents"].append("agents/no_such_agent")
    p["builds_on"].append("specs/9999-missing")
    msgs = [f.message for f in _errors(ap.validate_pack(p, ROOT))]
    assert any("no_such_agent" in m for m in msgs)
    assert any("9999-missing" in m for m in msgs)


def test_ac009_deep_packs_referenced(packs):
    """AC-009: analytics packs defer to the existing deep knowledge packs."""
    assert "knowledge/credit_risk" in _by_id(packs, "credit_risk")["builds_on"]
    assert "knowledge/short_term_markets" in _by_id(packs, "short_term_markets_funding")["builds_on"]


def test_ac010_golden_cases_are_checked(packs):
    """AC-010: wrong bps, wrong ratio, or a contradicting additivity claim each error."""
    for p in packs:
        assert p["golden_cases"], p["pack_id"]
    p = _by_id(packs, "rates_fixed_income")
    p["golden_cases"] = [
        {"id": "bad.bps", "kind": "bps_change", "from_pct": 4.0, "to_pct": 4.2, "expected_bps": 5.0},
        {"id": "bad.ratio", "kind": "ratio", "numerator": 1, "denominator": 4, "scale": 100, "expected": 20.0},
        {"id": "bad.add", "kind": "additivity", "metric": "yield", "across": "dimension", "allowed": True},
    ]
    msgs = " ".join(f.message for f in _errors(ap.validate_pack(p, ROOT)))
    for gid in ("bad.bps", "bad.ratio", "bad.add"):
        assert gid in msgs


def test_ac011_cli_and_readme_sync(packs, tmp_path):
    """AC-011: the CLI exits zero on the catalog; a README missing a pack id errors."""
    run = subprocess.run([sys.executable, "-m", "quantsmith.pipelines.analytics_packs", "--root", str(ROOT)],
                         capture_output=True, text=True, cwd=ROOT,
                         env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""})
    assert run.returncode == 0, run.stdout + run.stderr
    readme = (ROOT / ap.PACKS_DIR / "README.md").read_text(encoding="utf-8")
    fake = tmp_path / ap.PACKS_DIR
    fake.mkdir(parents=True)
    (fake / "README.md").write_text(readme.replace("`fraud`", "fraud"), encoding="utf-8")
    msgs = [(f.pack_id, f.message) for f in ap.validate_catalog(packs, tmp_path) if f.severity == "error"
            and "README" in f.message]
    assert msgs == [("fraud", "not listed in knowledge/analytics_packs/README.md")]


def test_ac012_uncovered_tags_are_info_only(packs):
    """AC-012: only text/document source tags stay uncovered, reported as info."""
    uncovered = set(ap.uncovered_source_domains(packs, ROOT))
    assert uncovered <= {"market_commentary", "nlp_llm", "quant_text_intelligence", "text_intelligence",
                         "supervisory_guidance", "regulatory_context"}
    for f in ap.validate_catalog(packs, ROOT):
        if "selects no pack" in f.message:
            assert f.severity == "info"


def test_ac013_packs_only_restrict(packs):
    """AC-013: rules can only add suppressed kinds; no field enables insights or changes access."""
    allowed = set(ap._REQUIRED)
    for p in packs:
        assert set(p) <= allowed, set(p) - allowed
        for r in p["insight_rules"]:
            assert set(r) == {"id", "applies_to", "suppress_kinds", "reason"}
    p = _by_id(packs, "equities_markets")
    base = set(ap.suppressed_insights(p, "volume"))
    p["insight_rules"].append({"id": "x", "applies_to": "volume", "suppress_kinds": ["outlier"], "reason": "t"})
    assert base | {"outlier"} == set(ap.suppressed_insights(p, "volume"))


def test_ac014_stdlib_only_and_no_sensitive_content():
    """AC-014: the validator imports only the stdlib; packs hold no emails, secrets, or credentialed URLs."""
    tree = ast.parse((ROOT / "src/quantsmith/pipelines/analytics_packs.py").read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    stdlib = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
    assert mods <= stdlib, mods - stdlib
    pattern = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|(api[_-]?key|secret|password|token)\s*[:=]|://[^/\s]+:[^/\s]+@", re.I)
    for f in sorted((ROOT / ap.PACKS_DIR).glob("*.json")):
        assert not pattern.search(f.read_text(encoding="utf-8")), f.name


def test_ac015_review_sheet_covers_every_reviewable_line(packs):
    """AC-015: a family's review sheet lists every pack, metric, convention, rule, caveat, and golden case."""
    for fam in ap.FAMILIES:
        sheet = ap.review_sheet(packs, fam)
        assert sheet == ap.review_sheet(packs, fam)
        assert ap.FAMILY_REVIEWERS[fam] in sheet
        for p in (p for p in packs if p["family"] == fam):
            assert f"`{p['pack_id']}`" in sheet
            for m in p["metrics"]:
                assert f"`{m['name']}`" in sheet
            for key in ("conventions", "insight_rules", "caveats", "chart_conventions", "golden_cases"):
                for item in p[key]:
                    assert f"`{item['id']}`" in sheet, (p["pack_id"], item["id"])
    with pytest.raises(ValueError):
        ap.review_sheet(packs, "no_such_family")


def test_ac016_mark_reviewed_records_named_review_and_refuses_bad_input(tmp_path):
    """AC-016: marking writes reviewer, date, and status; missing name, bad date, unknown or invalid packs are refused."""
    import shutil

    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    shutil.copytree(ROOT / "knowledge", tmp_path / "knowledge")
    shutil.copytree(ROOT / "specs", tmp_path / "specs")
    (tmp_path / "instructions").mkdir()
    shutil.copy(ROOT / "instructions" / "portfolio_management.md", tmp_path / "instructions")

    for bad in (dict(reviewer="", reviewed_on="2026-09-24"), dict(reviewer="A Reviewer", reviewed_on="24/09/2026")):
        with pytest.raises(ap.PackValidationError):
            ap.mark_reviewed(tmp_path, "fraud", **bad)
    with pytest.raises(ap.PackValidationError):
        ap.mark_reviewed(tmp_path, "no_such_pack", "A Reviewer", "2026-09-24")

    pack = ap.mark_reviewed(tmp_path, "fraud", "A Reviewer", "2026-09-24")
    on_disk = json.loads((tmp_path / ap.PACKS_DIR / "fraud.json").read_text(encoding="utf-8"))
    assert on_disk == pack
    assert on_disk["review"]["status"] == "reviewed"
    assert on_disk["review"]["reviewer"] == "A Reviewer" and on_disk["review"]["reviewed_on"] == "2026-09-24"
    assert "not yet reviewed" not in on_disk["review"]["notes"]
    assert ap.select_packs(["fraud"], ap.load_packs(tmp_path)).all_reviewed

    broken = tmp_path / ap.PACKS_DIR / "payments.json"
    data = json.loads(broken.read_text(encoding="utf-8"))
    data["reviewer_agents"] = ["agents/no_such_agent"]
    broken.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ap.PackValidationError):
        ap.mark_reviewed(tmp_path, "payments", "A Reviewer", "2026-09-24")
    assert json.loads(broken.read_text(encoding="utf-8"))["review"]["status"] == "draft"
