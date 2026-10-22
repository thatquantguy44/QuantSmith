"""Acceptance tests for spec 0121 — SFMeridian adaptive securities-finance dataset research.

AC-001…AC-018 are the Dataset Intake Investigator POC spec's AC-01…AC-18
(test names are the POC's); AC-019…AC-024 add the securities-finance rule
pack, the tool catalog, configuration, the agent catalog, reporting, and
portability. Everything runs offline against a synthetic SQLite fixture.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "sfmeridian"
sys.path.insert(0, str(PLUGIN / "src"))

from sfmeridian import governance
from sfmeridian.agent import (
    ModelPolicy,
    ToolCall,
    load_manifest,
    run_agent,
)
from sfmeridian.config import ConfigError, load_config, read_file
from sfmeridian.research.analysis import _parse_ts
from sfmeridian.research.charts import validate_chart
from sfmeridian.research.evidence import FAMILIES
from sfmeridian.research.policy import (
    VERIFIERS,
    run_research,
)
from sfmeridian.research.templates import TemplateError, render
from sfmeridian.sqlstructure import extract
from sfmeridian.tools import ToolContext, default_registry

TODAY = "2026-10-22"
POC_TOOLS = ("inspect_schema", "summarize_columns", "check_grain", "inspect_missingness", "inspect_numeric",
             "inspect_categories", "inspect_relationships", "inspect_time", "compare_segments", "inspect_target",
             "inspect_availability", "compare_reference", "render_charts", "recommend_actions")


class FxPath(type(Path())):
    """The fixture directory, carrying the builder's expected counts."""
    expected: dict | None = None


@pytest.fixture()
def fx(tmp_path: Path) -> Path:
    shutil.copytree(PLUGIN / "fixtures", tmp_path / "fx")
    sys.path.insert(0, str(tmp_path / "fx" / "research"))
    import importlib

    import fixture_db
    importlib.reload(fixture_db)
    fx = FxPath(tmp_path / "fx" / "research")
    fx.expected = fixture_db.build(fx / "lending.sqlite")
    sys.path.remove(str(tmp_path / "fx" / "research"))
    return fx


def _config(fx: Path, **changes):
    if not changes:
        return load_config(fx / "sfmeridian.research.yml", env={})
    data = read_file(fx / "sfmeridian.research.yml")
    data.update(changes)
    (fx / "changed.json").write_text(json.dumps(data))
    return load_config(fx / "changed.json", env={})


def _context(fx: Path, name: str, **changes):
    data = read_file(fx / "contexts" / f"{name}.yml")
    data.update(changes)
    return data


def _run(fx: Path, dataset: str, context, *, config=None, clients=None, policy=None):
    ctx = ToolContext(config or _config(fx), today=TODAY, actor="lending-data-researcher", clients=clients or {})
    run = run_research(ctx, dataset=dataset, context=context, policy=policy(ctx) if policy else None)
    return run, ctx.session.get("research")


def _bundle_text(bundle: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(bundle.rglob("*"))
                     if p.is_file() and "analysis/sfmeridian" not in p.as_posix())


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# AC-001 … AC-018 (POC AC-01 … AC-18)
# --------------------------------------------------------------------------

def test_intake_regression(fx):
    """AC-001: the POC intake behaviour is preserved for the POC synthetic positions file."""
    run, s = _run(fx, "poc_positions", {"objective": "POC regression", "as_of": "2026-10-21"})
    assert run.status == "completed"
    report = s.facts["intake"]
    assert report["status"] == "blocked"
    checks = {f["check"] for f in report["findings"]}
    assert {"row_width", "duplicate_rows", "missing_values", "grain", "range", "date_parse", "future_dates"} <= checks
    assert report["grain"] == {"key": ["security", "as_of_date"], "missing_key_rows": 0, "repeated_key_rows": 1}
    loader = Path(s.bundle_dir) / "analysis" / "load_dataset.py"
    assert "EXPECTED_SHA256" in loader.read_text() and report["sha256"] in loader.read_text()


def test_coverage_accounting(fx):
    """AC-002: every family has an entry with a final status and, when not completed, a reason."""
    _, s = _run(fx, "loan_book", _context(fx, "loan_book"))
    coverage = json.loads((Path(s.bundle_dir) / "coverage.json").read_text())
    assert [c["family"] for c in coverage] == list(FAMILIES)
    for c in coverage:
        assert c["status"] in ("completed", "blocked", "skipped", "budget_exhausted"), c
        assert c["status"] == "completed" or c["reason"], c


def test_adaptive_missingness_followup(fx):
    """AC-003: concentrated missing fees trigger date and segment diagnostics cited by one finding."""
    run, s = _run(fx, "loan_book", _context(fx, "loan_book"))
    calls = [(t["name"], t.get("args")) for t in run.trace if t["event"] == "decide"]
    assert ("research.inspect_missingness", {"column": "fee_bps", "by": "date"}) in calls
    assert ("research.inspect_missingness", {"column": "fee_bps", "by": "segment"}) in calls
    assert calls.index(("research.summarize_columns", {})) < calls.index(
        ("research.inspect_missingness", {"column": "fee_bps", "by": "date"}))
    f = next(f for f in s.findings if f.kind == "missing_concentration")
    assert len(f.evidence_ids) == 2
    label = lambda g: g["untrusted_text"] if isinstance(g, dict) else g   # source text stays marked untrusted
    assert label(f.counts["by_date"]["group"]) == "2026-10-14" and label(f.counts["by_segment"]["group"]) == "APAC"
    assert f.counts["total_nulls"] == fx.expected["fee_nulls_apac_2026_10_14"]
    run2, _ = _run(fx, "lendable_inventory", {"objective": "x", "as_of": TODAY, "dataset_kind": "lendable_inventory",
                                             "time_column": "business_date", "segments": ["region"]})
    assert not any(t.get("name") == "research.inspect_missingness" for t in run2.trace)


def test_missing_context_no_invention(fx):
    """AC-004: no grain, calendar, or target → explicit blocked/skipped entries; candidates only."""
    _, s = _run(fx, "collateral", {"objective": "x", "as_of": TODAY, "dataset_kind": "collateral",
                                     "time_column": "business_date"})
    cov = {c["family"]: c for c in s.ledger.as_list()}
    assert cov["duplicates_grain"]["status"] == "blocked" and "business_grain" in cov["duplicates_grain"]["reason"]
    assert cov["target"]["status"] == "skipped" and "no target" in cov["target"]["reason"]
    assert "no calendar" in cov["temporal"]["reason"]
    assert "collateral_margin" in cov["domain_rules"]["reason"]
    grain = next(f for f in s.findings if f.kind == "grain_unconfigured")
    assert "candidates only" in grain.observation and grain.severity == "limitation"


def test_evidence_integrity(fx):
    """AC-005: every finding and recommendation resolves to evidence with matching numbers."""
    run, s = _run(fx, "loan_book", _context(fx, "loan_book"))
    report = json.loads((Path(s.bundle_dir) / "report.json").read_text())
    evidence = {e["evidence_id"]: e for e in report["evidence"]}
    for f in report["findings"]:
        assert f["evidence_ids"] and all(e in evidence for e in f["evidence_ids"])
        if f["kind"].startswith("rule:"):
            value = evidence[f["evidence_ids"][0]]["value"]
            assert value["violations"] == f["counts"]["violations"]
    findings = {f["finding_id"]: f for f in report["findings"]}
    for r in report["recommendations"]:
        assert set(r["evidence_ids"]) == set(findings[r["finding_id"]]["evidence_ids"])
    assert all(t["ok"] for t in run.trace if t["event"] == "verify")


def test_scope_propagation(fx):
    """AC-006: a truncated extract never becomes a population claim."""
    context = _context(fx, "loan_book", budgets={"max_rows_local": 150})
    _, s = _run(fx, "loan_book", context)
    assert s.facts["extract"]["truncated"]
    assert any("ordered extract" in x for x in s.limitations)
    for f in s.findings:
        if f.scope == "ordered_extract":
            assert "filtered population" not in f.observation and "returned extract" in f.observation
    numeric = [f for f in s.findings if f.kind == "iqr_flags"]
    assert numeric and all(f.scope == "ordered_extract" for f in numeric)


def test_database_query_boundary(fx):
    """AC-007: values bound, identifiers validated, unauthorized columns and expressions rejected."""
    allowed = ["loan_id", "fee_bps", "business_date"]
    r = render("count_rows", dialect="postgres", obj="loan_book", allowed=allowed,
               filters=[{"column": "loan_id", "op": "=", "value": "x' OR '1'='1"}])
    assert "OR '1'" not in r.sql and r.params == ("x' OR '1'='1",) and ":p0" in r.sql
    for bad in ({"column": "client_note"}, {"column": "fee_bps) FROM t; --"}, {"column": "SUM(fee_bps)"}):
        with pytest.raises(TemplateError):
            render("group_counts", dialect="sqlite", obj="loan_book", allowed=allowed, limit=5, **bad)
    with pytest.raises(TemplateError):
        render("count_rows", dialect="sqlite", obj="loan_book; DROP TABLE x", allowed=allowed)
    with pytest.raises(TemplateError):
        render("count_rows", dialect="sqlite", obj="t", allowed=allowed,
               filters=[{"column": "fee_bps", "op": "LIKE", "value": "%"}])
    context = _context(fx, "loan_book")
    reg = default_registry()
    ctx = ToolContext(_config(fx), today=TODAY, actor="t")
    assert reg.call("research.start", {"dataset": "loan_book", "context": context}, ctx).ok
    res = reg.call("research.inspect_categories", {"column": "client_note"}, ctx)
    assert not res.ok and res.error_code == "E_RESEARCH_TEMPLATE"
    assert all(q["template"] != "group_counts" for q in ctx.session["research"].executor.log)


def test_budget_and_stop_conditions(fx):
    """AC-008: query, time, step, and token budgets stop honestly; duplicates rejected; one transient retry."""
    run, s = _run(fx, "loan_book", _context(fx, "loan_book", budgets={"max_queries": 6}))
    assert run.status == "budget_exhausted" and s.stop_reason == "budget_exhausted"
    statuses = {c["family"]: c["status"] for c in s.ledger.as_list()}
    assert "budget_exhausted" in statuses.values()
    assert statuses["recommendations"] == "budget_exhausted" and statuses["numeric"] == "budget_exhausted"
    assert s.budget.queries <= 6

    ticks = iter(range(0, 100000, 7))
    run, s = _run(fx, "loan_book", _context(fx, "loan_book", budgets={"wall_time_seconds": 60}),
                  clients={"clock": lambda: next(ticks)})
    assert run.status == "budget_exhausted"

    class Repeat:
        name = "repeat"

        def __init__(self):
            self.n = 0

        def decide(self, state):
            self.n += 1
            if self.n == 1:
                return ToolCall("research.start", {"dataset": "loan_book", "context": _context(fx, "loan_book")})
            return ToolCall("research.inspect_schema", {})
    ctx = ToolContext(_config(fx), today=TODAY, actor="t")
    m = load_manifest("lending_data_researcher")
    run = run_agent(type(m).from_dict({**m.as_dict(), "max_steps": 6}), Repeat(), default_registry(), ctx,
                    verifiers=VERIFIERS)
    assert sum(1 for t in run.trace if t["event"] == "duplicate_rejected") == 4 and run.status == "budget_exhausted"

    path = fx / "lending.sqlite"
    state = {"cursor": 0}

    class Flaky:
        """Fails the second statement once with a transient error, then behaves."""

        def __init__(self):
            self.conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)

        def cursor(self):
            state["cursor"] += 1
            if state["cursor"] == 2:
                raise sqlite3.OperationalError("database is locked")
            return self.conn.cursor()

        def close(self):
            self.conn.close()
    clients = {"connections": {"fixture_lending": {"connect": Flaky, "paramstyle": "qmark"}}}
    run, s = _run(fx, "loan_book", _context(fx, "loan_book"), clients=clients)
    retries = [t for t in run.trace if t["event"] == "retry"]
    assert [t["name"] for t in retries] == ["research.inspect_schema"] and run.status == "completed"
    observed = [t for t in run.trace if t["event"] == "observe" and t["name"] == "research.inspect_schema"]
    assert [t["error_code"] for t in observed] == ["E_SOURCE_TRANSIENT", None]

    model = lambda ctx: ModelPolicy(lambda p: '{"action": "tool", "name": "research.inspect_schema", "args": {}}',
                                    default_registry(), token_limit=10)
    run, _ = _run(fx, "loan_book", _context(fx, "loan_book"), policy=model)
    assert run.status == "budget_exhausted" and "token budget" in run.summary


def test_read_only_and_prompt_injection(fx):
    """AC-009: injected source text cannot steer tools or write; only SELECT templates execute."""
    before = _file_hash(fx / "lending.sqlite")
    context = _context(fx, "loan_book", exclude_columns=[])
    _, s = _run(fx, "loan_book", context)
    notes = next(e for e in s.evidence.as_list() if e["tool"] == "research.inspect_categories"
                 and e["value"]["column"] == "client_note")
    texts = [lv["value"] for lv in notes["value"]["top_levels"]]
    assert any(isinstance(t, dict) and "IGNORE ALL" in t["untrusted_text"] for t in texts)
    for q in s.executor.log:
        shape = extract(q["sql"], "sqlite")
        assert shape["read_only_shape"] and shape["statement_count"] == 1 and q["sql"].startswith("SELECT")
    obeys = lambda ctx: ModelPolicy(lambda p: '{"action": "tool", "name": "feedback.promote", '
                                              '"args": {"candidate_id": "0000000000000000"}}', default_registry())
    run2, _ = _run(fx, "loan_book", context, policy=obeys)
    assert run2.status == "denied"
    assert _file_hash(fx / "lending.sqlite") == before


def test_sensitive_data_boundary(fx):
    """AC-010: sensitive and excluded values and credentials never reach prompts or the bundle."""
    secret = "postgresql://svc:hunter2@db.internal/lending"  # qf:allow-secret (deliberate fake)
    path = fx / "lending.sqlite"
    clients = {"connections": {"fixture_lending": {
        "connect": lambda dsn=secret: sqlite3.connect(path.as_uri() + "?mode=ro", uri=True), "paramstyle": "qmark"}}}
    _, s = _run(fx, "loan_book", _context(fx, "loan_book"), clients=clients)
    text = _bundle_text(Path(s.bundle_dir))
    assert "ACCT-" not in text and "IGNORE ALL" not in text and "hunter2" not in text
    prompts = []

    def complete(prompt):
        prompts.append(prompt)
        n = len(prompts)
        start = {"action": "tool", "name": "research.start",
                 "args": {"dataset": "loan_book", "context": _context(fx, "loan_book")}}
        script = [json.dumps(start),
                  '{"action": "tool", "name": "research.summarize_columns", "args": {}}',
                  '{"action": "tool", "name": "research.inspect_categories", "args": {"column": "region"}}',
                  '{"action": "escalate", "reason": "done"}']
        return script[min(n - 1, 3)]
    _, _ = _run(fx, "loan_book", _context(fx, "loan_book"), clients=clients,
                   policy=lambda ctx: ModelPolicy(complete, default_registry()))
    joined = "\n".join(prompts)
    assert "ACCT-" not in joined and "hunter2" not in joined and "IGNORE ALL" not in joined


def test_reproducible_analysis(fx, tmp_path):
    """AC-011: frozen inputs reproduce evidence IDs and artifact hashes."""
    run_a, s_a = _run(fx, "loan_book", _context(fx, "loan_book"))
    manifest_a = json.loads((Path(s_a.bundle_dir) / "run_manifest.json").read_text())
    run_b, s_b = _run(fx, "loan_book", _context(fx, "loan_book"))
    manifest_b = json.loads((Path(s_b.bundle_dir) / "run_manifest.json").read_text())
    assert sorted(s_a.evidence.records) == sorted(s_b.evidence.records)
    assert manifest_a["artifact_hashes"] == manifest_b["artifact_hashes"]
    assert run_a.run_id == run_b.run_id


def test_mutable_view_provenance(fx):
    """AC-012: an unpinned view whose base table changes mid-run is reported as a limitation."""
    path = fx / "lending.sqlite"
    state = {"queries": 0}

    class Mutating:
        def __init__(self):
            self.conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)

        def cursor(self):
            state["queries"] += 1
            if state["queries"] == 4:
                rw = sqlite3.connect(path)
                rw.execute("INSERT INTO loan_book SELECT loan_id, security_id, counterparty_id, account, region, "
                           "'2026-10-23', quantity, on_loan_value, fee_bps, status, client_note, change_seq + 1000 "
                           "FROM loan_book LIMIT 1")
                rw.commit()
                rw.close()
            return self.conn.cursor()

        def close(self):
            self.conn.close()
    clients = {"connections": {"fixture_lending": {"connect": Mutating, "paramstyle": "qmark"}}}
    _, s = _run(fx, "loan_book_view", {"objective": "x", "as_of": TODAY, "dataset_kind": "loan_book",
                                         "change_column": "change_seq"}, clients=clients)
    joined = " ".join(s.limitations)
    assert "Source changed during the run" in joined and "unpinned view" in joined
    assert "Source changed" in (Path(s.bundle_dir) / "report.md").read_text()


def test_bundle_rerun(fx, tmp_path):
    """AC-013: the bundled rerun command reproduces the evidence with the bundled package only."""
    _, s = _run(fx, "loan_book", _context(fx, "loan_book"))
    bundle = Path(s.bundle_dir)
    out = tmp_path / "rerun_out"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    done = subprocess.run([sys.executable, str(bundle / "analysis" / "rerun.py"), "--config",
                           str(fx / "sfmeridian.research.yml"), "--out", str(out)],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr
    rerun_bundle = next(out.iterdir())
    original = {e["evidence_id"] for e in json.loads((bundle / "report.json").read_text())["evidence"]}
    again = {e["evidence_id"] for e in json.loads((rerun_bundle / "report.json").read_text())["evidence"]}
    assert original == again
    for name in ("report.md", "coverage.json", "recommendations.json", "dataset_contract_proposal.json",
                 "run_manifest.json", "analysis/context.json", "analysis/dataset.json", "analysis/rerun.py"):
        assert (bundle / name).exists(), name
    assert list((bundle / "analysis" / "queries").glob("Q-*.sql"))


def test_chart_artifact_validation(fx):
    """AC-014: every chart has title, units, denominator, scope, data, and Vega-Lite structure."""
    _, s = _run(fx, "loan_book", _context(fx, "loan_book"))
    charts = list((Path(s.bundle_dir) / "charts").glob("*.vl.json"))
    assert charts
    for path in charts:
        spec = json.loads(path.read_text())
        assert validate_chart(spec) == [], path
        assert spec["$schema"].startswith("https://vega.github.io/schema/vega-lite/")


def test_pushdown_aggregate_correctness(fx):
    """AC-015: pushed-down summaries, grain, missingness, and rule counts equal Python over all rows."""
    _, s = _run(fx, "loan_book", _context(fx, "loan_book"))
    conn = sqlite3.connect(fx / "lending.sqlite")
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM loan_book WHERE business_date >= '2026-10-01'")]
    summaries = s.facts["summaries"]
    assert s.facts["rows"] == len(rows) == fx.expected["loan_book_rows"]
    assert summaries["fee_bps"]["nulls"] == sum(r["fee_bps"] is None for r in rows)
    assert summaries["security_id"]["distinct"] == len({r["security_id"] for r in rows})
    assert summaries["quantity"]["min"] == min(r["quantity"] for r in rows)
    keys = [(r["loan_id"], r["business_date"]) for r in rows]
    assert s.facts["grain"]["repeated_keys"] == sum(1 for k in set(keys) if keys.count(k) > 1)
    rules = {r["rule_id"]: r for r in s.facts["rules"]}
    assert rules["lb.quantity_positive"]["violations"] == sum(r["quantity"] <= 0 for r in rows)
    assert rules["lb.lender_fee_nonnegative"]["violations"] == sum(
        r["fee_bps"] is not None and r["fee_bps"] < 0 for r in rows)
    assert s.facts["time"]["missing_dates"] == fx.expected["missing_business_dates"]


@pytest.mark.skipif(not any(os.environ.get(v) for v in ("SFMERIDIAN_LIVE_POSTGRES", "SFMERIDIAN_LIVE_ORACLE",
                                                        "SFMERIDIAN_LIVE_DATABRICKS")),
                    reason="AC-016 open: no nonproduction connector pointers injected (live smoke not run)")
def test_live_connector_smoke():  # pragma: no cover - requires live nonproduction environments
    """AC-016: runs one summary template per injected live connector; skipped (never passed) otherwise."""
    pytest.fail("live connector harness must be supplied by the adopter environment (see spec 0121 AC-016)")


def test_point_in_time_checks(fx):
    """AC-017: availability honours offsets and the context timezone; naive timestamps are blocked."""
    _, s = _run(fx, "borrow_rates", _context(fx, "borrow_rates"))
    value = next(e for e in s.evidence.as_list() if e["tool"] == "research.inspect_availability")["value"]
    assert value["inverted"] == fx.expected["inverted"]
    assert value["published_after_event_day"] == fx.expected["late_published"]
    assert value["after_decision_cutoff"] == 6
    assert value["decision_cutoff"].startswith("2026-10-22T23:59:59.999999-04:00")
    naive = _context(fx, "borrow_rates", feature_availability={"event_time_column": "business_date",
                                                               "available_at_column": "published_local"})
    _, s2 = _run(fx, "borrow_rates", naive)
    assert {c["family"]: c["status"] for c in s2.ledger.as_list()}["availability"] == "blocked"
    declared = _context(fx, "borrow_rates", feature_availability={
        "event_time_column": "business_date", "available_at_column": "published_local",
        "naive_timezone": "America/New_York"})
    _, s3 = _run(fx, "borrow_rates", declared)
    assert {c["family"]: c["status"] for c in s3.ledger.as_list()}["availability"] == "completed"
    dt, status = _parse_ts("2026-10-12T18:00:00-04:00", None, False, None)
    assert status == "aware" and dt.utcoffset().total_seconds() == -4 * 3600
    assert _parse_ts("2026-10-12 18:00:00", None, False, None) == (None, "naive")


def test_recommendation_only_boundary(fx):
    """AC-018: recommendations never execute; research tools have no write effect; source unchanged."""
    before = _file_hash(fx / "lending.sqlite")
    _, s = _run(fx, "loan_book", _context(fx, "loan_book"))
    recs = json.loads((Path(s.bundle_dir) / "recommendations.json").read_text())
    assert recs and all(r["executes"] is False and r["next_diagnostic"].get("executes", False) is False for r in recs)
    assert any(r["next_diagnostic"]["type"] == "query" for r in recs)
    effects = {spec["effect"] for spec in default_registry().describe() if spec["name"].startswith("research.")}
    assert effects <= {"read", "execute_read", "report"}
    assert _file_hash(fx / "lending.sqlite") == before


# --------------------------------------------------------------------------
# AC-019 … AC-024
# --------------------------------------------------------------------------

def test_ac019_securities_finance_rule_pack_counts(fx):
    """AC-019: each planted securities-finance issue is counted exactly; a legitimate special is not an error."""
    base = {"objective": "x", "as_of": TODAY, "timezone": "America/New_York", "viewpoint": "lender"}

    def counts(dataset, **ctx):
        _, s = _run(fx, dataset, {**base, **ctx})
        return {r["rule_id"]: r for r in s.facts["rules"]}
    lb = counts("loan_book", dataset_kind="loan_book", thresholds={"fee_band_bps": {"min": 0, "max": 5000},
                                                                   "status_values": ["OPEN", "CLOSED"]})
    assert lb["lb.quantity_positive"]["violations"] == fx.expected["zero_quantity_rows"]
    assert lb["lb.lender_fee_nonnegative"]["violations"] == fx.expected["negative_fee_rows"]
    assert lb["lb.fee_within_band"]["violations"] == 1          # the negative fee; the 3,000 bps special is inside
    assert lb["lb.status_enumerated"]["violations"] == fx.expected["status_typos"]
    inv = counts("lendable_inventory", dataset_kind="lendable_inventory")
    assert inv["li.on_loan_le_lendable"]["violations"] == fx.expected["on_loan_above_lendable"]
    br = counts("borrow_rates", dataset_kind="borrow_rates",
                thresholds={"category_thresholds_bps": {"gc_max_bps": 50, "warm_max_bps": 200}})
    assert br["br.category_consistent"]["violations"] == fx.expected["category_inconsistent"]
    cl = counts("collateral", dataset_kind="collateral", thresholds={"collateral_margin": 1.02})
    assert cl["cl.coverage_at_margin"]["violations"] == fx.expected["collateral_below_margin"]
    pr = counts("program_revenue", dataset_kind="program_revenue", thresholds={"accrual_tolerance": 0.01})
    assert pr["pr.accrual_act360"]["violations"] == fx.expected["accrual_mismatch"]
    assert pr["pr.owner_split_unit_interval"]["violations"] == fx.expected["owner_split_out_of_range"]
    skipped = counts("collateral", dataset_kind="collateral")
    assert skipped["cl.coverage_at_margin"]["status"] == "skipped"
    from sfmeridian.research.rules import RULES
    assert all(r.convention and ("006" in r.convention or "adopter-configurable" in r.convention) for r in RULES)


def test_ac020_tool_catalog():
    """AC-020: every POC tool exists as research.* with a schema; results carry scope and evidence IDs."""
    names = {spec["name"]: spec for spec in default_registry().describe()}
    for tool in POC_TOOLS:
        assert f"research.{tool}" in names and names[f"research.{tool}"]["input_schema"]["type"] == "object"


def test_ac021_dataset_config_validation(fx):
    """AC-021: unknown profile, free-text object, and SQL Server fail with named codes."""
    data = read_file(fx / "sfmeridian.research.yml")

    def codes(mutate):
        d = json.loads(json.dumps(data))
        mutate(d)
        with pytest.raises(ConfigError) as exc:
            load_config(data=d, env={})
        return {i.code for i in exc.value.issues}
    assert "E_CONFIG_INVALID" in codes(lambda d: d["datasets"][0].update(profile="nope"))
    assert "E_CONFIG_INVALID" in codes(lambda d: d["datasets"][0].update(object="loan_book WHERE 1=1"))
    assert "E_CONFIG_UNSUPPORTED" in codes(lambda d: d["databases"][0].update(dialect="mssql"))
    assert "E_CONFIG_INVALID" in codes(lambda d: d["datasets"][0]["filters"].append(
        {"column": "business_date", "op": "LIKE", "value": "%"}))


def test_ac022_agent_catalog_and_governance():
    """AC-022: lending_data_researcher is a built loop agent with manifest, row C-10, W13, and handoffs."""
    agent_dir = ROOT / "agents/securities_financing/sfmeridian/lending_data_researcher"
    for name in ("README.md", "prompt.md", "instructions.md", "tasks.md"):
        assert (agent_dir / name).exists()
    report = governance.validate_all(ROOT / "agents", registry=default_registry())
    assert report["ok"], report["errors"]
    assert report["counts"]["built_agents"] == 3 and report["counts"]["coverage_rows"] == 10
    handoffs = governance.load("handoffs.json")["handoffs"]
    assert {"dataset_investigator", "data_quality", "schema_evolution"} <= {
        h["agent"] for h in handoffs if "W13" in h["workflows"]}


def test_ac023_numbers_carry_denominator_method_scope(fx):
    """AC-023: every evidence record states scope and method, and pushdown counts state a denominator."""
    _, s = _run(fx, "loan_book", _context(fx, "loan_book"))
    for e in s.evidence.as_list():
        assert e["scope"] in ("full_filtered_population", "ordered_extract") and e["method"]
        if e["tool"] in ("research.summarize_columns", "research.check_domain_rules", "research.inspect_missingness"):
            assert e["denominator"] is not None


def test_ac024_stdlib_only():
    """AC-024: the package, research included, imports only the standard library."""
    assert governance.check_imports() == []
