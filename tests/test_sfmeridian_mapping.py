"""Acceptance tests for spec 0115 — SFMeridian schema catalog, semantic mapping & access.

Everything runs offline against the synthetic fixtures in
``plugins/sfmeridian/fixtures/`` (declared catalogs, the query repository, the
research SQLite database, and a fixture 0058 roster).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "sfmeridian"
sys.path.insert(0, str(PLUGIN / "src"))

from sfmeridian import access, catalog, governance
from sfmeridian.agent import Finish, LoopState, load_manifest
from sfmeridian.config import ConfigError, load_config, read_file
from sfmeridian.governed import packs as packs_mod
from sfmeridian.mapping import Vocabulary
from sfmeridian.steward import VERIFIERS, StewardPolicy, run_steward
from sfmeridian.tools import ToolContext, default_registry

TODAY = "2026-10-22"
PACK = ROOT / "knowledge" / "analytics_packs" / "securities_financing_prime.json"


@pytest.fixture()
def fx(tmp_path: Path) -> Path:
    shutil.copytree(PLUGIN / "fixtures", tmp_path / "fx")
    return tmp_path / "fx"


def _config(fx: Path, mutate=None, name: str = "sfmeridian.mapping.yml"):
    if mutate is None:
        return load_config(fx / name, env={})
    data = read_file(fx / name)
    mutate(data)
    changed = (fx / name).parent / "changed.json"             # next to the source, so relative paths still resolve
    changed.write_text(json.dumps(data))
    return load_config(changed, env={})


def _ctx(config, actor: str = "semantic_mapping_steward", **clients) -> ToolContext:
    return ToolContext(config, TODAY, actor=actor, clients=clients, agents_root=ROOT / "agents")


def _call(ctx, name, args=None, registry=None):
    result = (registry or default_registry()).call(name, args or {}, ctx)
    return result


def _prepared(fx: Path, mutate=None, actor="semantic_mapping_steward"):
    ctx = _ctx(_config(fx, mutate), actor)
    reg = default_registry()
    for tool in ("repos.index", "catalog.snapshot", "catalog.reconcile"):
        r = reg.call(tool, {}, ctx)
        assert r.ok, (tool, r.error)
    return ctx, reg


def _use_v2(data):
    data["catalog"]["fixture_db"]["file"] = "catalog/fixture_db.catalog.v2.json"


def _binding(data, concept):
    return next(b for b in data["semantic_mapping"]["fixture_db"] if b["concept"] == concept)


def _validated(ctx, reg, concept):
    out = reg.call("mapping.validate", {}, ctx).output
    return next(b for b in out["bindings"] if b["concept"] == concept), out


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------

def test_ac001_declared_snapshot_content_addressed_and_dated(fx):
    ctx = _ctx(_config(fx))
    first = _call(ctx, "catalog.snapshot").output["snapshots"][0]
    assert first["changed"] and first["previous_id"] is None and first["source"] == "file"
    assert first["tables"] == 8
    index = fx / ".sfmeridian" / "index" / "catalog" / "fixture_db"
    files = sorted(p.name for p in index.iterdir())
    assert files == [f"{first['snapshot_id']}.json", "history.json"]
    before = {p: p.stat().st_mtime_ns for p in index.iterdir()}
    again = _call(_ctx(_config(fx)), "catalog.snapshot").output["snapshots"][0]
    assert not again["changed"] and again["snapshot_id"] == first["snapshot_id"]
    assert {p: p.stat().st_mtime_ns for p in index.iterdir()} == before          # unchanged writes nothing
    assert json.loads((index / "history.json").read_text()) == [
        {"snapshot_id": first["snapshot_id"], "taken_on": TODAY, "source": "file"}]
    snap = json.loads((index / f"{first['snapshot_id']}.json").read_text())
    assert "taken_on" not in snap and snap["default_schema"] == "main"

    # Allowlists filter what the catalog may expose.
    def allow(data):
        data["databases"][0]["schemas_allowlist"] = ["lending"]
    allowed = _call(_ctx(_config(fx, allow)), "catalog.snapshot").output["snapshots"][0]
    assert allowed["tables"] == 2 and allowed["changed"]


def _research_db(fx: Path) -> Path:
    sys.path.insert(0, str(fx / "research"))
    try:
        import importlib

        import fixture_db
        importlib.reload(fixture_db)
        fixture_db.build(fx / "research" / "lending.sqlite")
    finally:
        sys.path.remove(str(fx / "research"))
    return fx / "research" / "lending.sqlite"


def test_ac002_sqlite_introspection_and_dialect_dictionary_queries(fx):
    _research_db(fx)

    def introspect(data):
        data["catalog"] = {"fixture_lending": {"source": "introspect"}}
    ctx = _ctx(_config(fx, introspect, name="research/sfmeridian.research.yml"))
    out = _call(ctx, "catalog.snapshot").output
    assert out["errors"] == [] and out["snapshots"][0]["source"] == "introspect"
    described = _call(ctx, "catalog.describe", {"profile": "fixture_lending"}).output
    tables = {t["name"]: t for t in described["tables"]}
    assert set(tables) == {"loan_book", "lendable_inventory", "borrow_rates", "collateral", "program_revenue",
                           "loan_book_v"}
    assert tables["loan_book_v"]["kind"] == "view"
    assert [c["name"] for c in tables["collateral"]["columns"]][:2] == ["loan_id", "business_date"]

    # PostgreSQL, Databricks, Oracle: only the fixed dictionary SELECTs, through an injected connection.
    rows = [("lending", "RECALLS", "BASE TABLE", "RECALL_ID", "VARCHAR2", "N", 1),
            ("lending", "RECALLS", "BASE TABLE", "RECALL_QTY", "NUMBER", "Y", 2),
            ("lending", "V_OPEN", "VIEW", "RECALL_ID", "VARCHAR2", "Y", 1)]

    class Cursor:
        def __init__(self, log, deny_keys):
            self.log, self.deny_keys, self.rows = log, deny_keys, []

        def execute(self, sql, params=None):
            self.log.append(sql)
            if "PRIMARY KEY" in sql or "constraint_type = 'P'" in sql:
                if self.deny_keys:
                    raise PermissionError("ORA-01031 insufficient privileges password=hunter2")
                self.rows = [("lending", "RECALLS", "RECALL_ID")]
            else:
                self.rows = rows

        def fetchall(self):
            return list(self.rows)

        def close(self):
            pass

    for dialect, deny in (("postgres", False), ("databricks", False), ("oracle", True)):
        log: list[str] = []

        class Conn:
            def cursor(self, _log=log, _deny=deny):
                return Cursor(_log, _deny)

            def close(self):
                pass

        snap = catalog.introspect(Conn(), {"id": "p", "dialect": dialect})
        assert log == [q for q in catalog.INTROSPECTION_SQL[dialect] if q]
        assert all(q.startswith("SELECT ") and ";" not in q for q in log)
        recalls = next(t for t in snap["tables"] if t["name"] == "RECALLS")
        assert recalls["columns"][0] == {"name": "RECALL_ID", "type": "VARCHAR2", "nullable": False, "comment": None}
        assert next(t for t in snap["tables"] if t["name"] == "V_OPEN")["kind"] == "view"
        if deny:
            assert snap["notes"] == ["primary keys unavailable: PermissionError"] and recalls["primary_key"] == []
        else:
            assert recalls["primary_key"] == ["RECALL_ID"]
        # Oracle reports upper case; resolution is case-insensitive.
        assert catalog.Resolver(snap).column("lending.recalls.recall_qty").ok

    class Broken:
        def cursor(self):
            raise RuntimeError("connect failed: postgresql://svc:hunter2@db/lending")  # qf:allow-secret (deliberate fake)

    with pytest.raises(catalog.CatalogError) as err:
        catalog.introspect(Broken(), {"id": "p", "dialect": "postgres"})
    assert err.value.code == "E_CATALOG_INTROSPECT" and "hunter2" not in err.value.message


def test_ac003_diff_classifies_and_hands_off(fx):
    ctx = _ctx(_config(fx))
    _call(ctx, "catalog.snapshot")
    assert _call(ctx, "catalog.diff", {"profile": "fixture_db"}).output["classification"] == "initial"
    ctx2 = _ctx(_config(fx, _use_v2))
    _call(ctx2, "catalog.snapshot")
    d = _call(ctx2, "catalog.diff", {"profile": "fixture_db"}).output
    assert d["classification"] == "breaking"
    kinds = {(c["change"], c["table"], c.get("column")) for c in d["changes"]}
    assert kinds == {("column_removed", "main.sec_lending_book", "status"),
                     ("column_retyped", "main.borrow_rates", "fee_bps"),
                     ("column_added", "main.lendable_inventory", "region")}
    assert d["handoff"]["agent"] == "schema_evolution"
    assert any(h["agent"] == "schema_evolution" for h in governance.load("handoffs.json")["handoffs"])
    same = catalog.load_snapshot(fx / ".sfmeridian" / "index", "fixture_db", d["from"])
    assert catalog.diff(same, same)["classification"] == "unchanged"


def test_ac004_drift_excludes_from_retrieval_until_clean(fx):
    ctx, reg = _prepared(fx)
    hits = reg.call("queries.search", {"query": "on loan value by counterparty"}, ctx).output["hits"]
    assert "sl.on_loan_value.by_counterparty.as_of" in [h["query_id"] for h in hits]

    ctx2, reg2 = _prepared(fx, _use_v2)
    drift = reg2.call("catalog.reconcile", {}, ctx2).output
    drifted = {d["query_id"]: d for d in drift["drifted"]}
    assert set(drifted) == {"sl.on_loan_value.by_counterparty.as_of", "sl.utilization.by_security.as_of",
                            "sl.utilization.legacy"}
    assert drifted["sl.on_loan_value.by_counterparty.as_of"]["missing_columns"] == ["sec_lending_book.status"]
    assert drifted["sl.utilization.legacy"]["missing_tables"] == ["legacy_utilization"]
    hits = reg2.call("queries.search", {"query": "on loan value by counterparty"}, ctx2).output["hits"]
    assert "sl.on_loan_value.by_counterparty.as_of" not in [h["query_id"] for h in hits]

    # warn keeps the exemplar searchable and still reports it.
    def warn(data):
        _use_v2(data)
        data["catalog"]["fixture_db"]["drift_policy"] = "warn"
    ctx3 = _ctx(_config(fx, warn))
    out = reg.call("catalog.reconcile", {}, ctx3).output
    assert {d["status"] for d in out["drifted"]} == {"warned"}
    hits = reg.call("queries.search", {"query": "on loan value by counterparty"}, ctx3).output["hits"]
    assert "sl.on_loan_value.by_counterparty.as_of" in [h["query_id"] for h in hits]

    # Restoring the catalog clears the exclusion.
    ctx4, reg4 = _prepared(fx)
    remaining = {d["query_id"] for d in reg4.call("catalog.reconcile", {}, ctx4).output["drifted"]}
    assert remaining == {"sl.utilization.legacy"}


# --------------------------------------------------------------------------
# Vocabulary and pack amendments
# --------------------------------------------------------------------------

def test_ac005_pack_vocabulary_amendments_and_caveat(fx):
    pack_bytes = PACK.read_bytes()
    ctx, reg = _prepared(fx)
    listed = reg.call("metrics.list", {}, ctx).output
    pack = json.loads(pack_bytes)
    assert {(m["name"], m["unit"], m["additivity"]) for m in listed["metrics"]} == \
        {(m["name"], m["unit"], m["additivity"]) for m in pack["metrics"]}
    assert len(listed["metrics"]) == 5
    assert listed["pack"]["source"]["mode"] == "quantsmith"
    assert listed["pack"]["review_status"] == "draft" and "unreviewed-pack caveat" in listed["pack"]["caveat"]
    assert listed["pack"]["assigned_reviewer"] == "Joshua Lutkemuller, CFA"
    assert listed["pack"]["reviewer"] is None                       # assigned, not reviewed
    assert {m["status"] for m in listed["proposed_metrics"]} == {"proposed"}
    assert {m["name"] for m in listed["proposed_metrics"]} >= {"rebate_rate", "lendable_value", "on_loan_quantity",
                                                               "lendable_quantity", "recall_quantity",
                                                               "collateral_value", "days_to_cover"}
    amend = reg.call("mapping.amendments", {}, ctx).output
    assert amend["validation"] == {"checked_with": "quantsmith.pipelines.analytics_packs.validate_pack", "errors": []}
    needed = {a["name"] for a in amend["amendments"] if a["needed_by"]}
    assert needed == {"lendable_value", "on_loan_quantity", "lendable_quantity", "recall_quantity",
                      "collateral_value", "counterparty"}
    staged = reg.call("mapping.propose_amendment", {"amendment_id": "amend.rebate_rate"}, ctx).output
    assert staged["created"] and staged["proposal"]["status"] == "proposed"
    assert staged["proposal"]["reviewer"] == "Joshua Lutkemuller, CFA"
    assert not reg.call("mapping.propose_amendment", {"amendment_id": "amend.rebate_rate"}, ctx).output["created"]
    assert reg.call("mapping.propose_amendment", {"amendment_id": "amend.private"}, ctx).error_code == "E_NOT_FOUND"
    assert PACK.read_bytes() == pack_bytes                          # the pack file is never edited

    # Glossary: the 0063 ambiguity rule for "special" and fee/rebate kept apart.
    special = reg.call("glossary.lookup", {"term": "special"}, ctx).output
    assert special["ambiguous"] and special["ambiguity_rules"][0]["requires"] == ["product_id", "viewpoint_id"]
    rebate = reg.call("glossary.lookup", {"term": "rebate"}, ctx).output["matches"]
    assert [m["name"] for m in rebate] == ["rebate_rate"] and rebate[0]["source"] == "proposed_amendment"


# --------------------------------------------------------------------------
# Binding validation
# --------------------------------------------------------------------------

def test_ac006_binding_validation_codes(fx):
    ctx, reg = _prepared(fx)
    out = reg.call("mapping.validate", {}, ctx).output
    assert out["counts"] == {"bindings": 9, "bound": 9, "invalid": 0}
    bound = {b["concept"]: b for b in out["bindings"]}
    assert bound["on_loan_value"]["columns"] == ["main.sec_lending_book.on_loan_value"]
    assert bound["recall_quantity"]["pit_column"] == "lending.recalls.recall_date"
    assert "confirmation of lending-lead" in " ".join(bound["lendable_value"]["caveats"])

    cases = {
        "E_MAP_CONCEPT_UNKNOWN": lambda d: d["semantic_mapping"]["fixture_db"].append(
            {**_binding(d, "collateral_value"), "concept": "house_spread"}),
        "E_MAP_UNRESOLVED": lambda d: _binding(d, "collateral_value").update(expression="collateral.haircut_value"),
        "E_MAP_MULTI_TABLE": lambda d: _binding(d, "collateral_value").update(
            expression="collateral.collateral_value - sec_lending_book.on_loan_value"),
        "E_MAP_EXPRESSION": lambda d: _binding(d, "collateral_value").update(
            expression="sum(collateral.collateral_value)"),
        "E_MAP_PIT": lambda d: _binding(d, "collateral_value").update(pit_column="sec_lending_book.business_date"),
        "E_MAP_UNIT": lambda d: _binding(d, "lending_revenue").update(unit="bps"),
        "E_MAP_ADDITIVITY": lambda d: _binding(d, "borrow_fee").update(aggregation="sum"),
        "E_MAP_QUOTE": lambda d: _binding(d, "borrow_fee").update(quote="rebate"),
        "E_MAP_DAY_COUNT": lambda d: _binding(d, "borrow_fee").pop("day_count"),
        "E_MAP_DIMENSION": lambda d: _binding(d, "lending_revenue")["dimensions"].update(desk="program_revenue.fund_id"),
        "E_MAP_EVIDENCE": lambda d: _binding(d, "lending_revenue").update(
            evidence={"exemplars": ["sl.utilization.portfolio.draft"]}),
        "E_MAP_DUPLICATE": lambda d: d["semantic_mapping"]["fixture_db"].append(dict(_binding(d, "borrow_fee"))),
        "E_MAP_VIEWPOINT": lambda d: _binding(d, "collateral_value").update(viewpoint="desk"),
    }
    for code, mutate in cases.items():
        ctx2 = _ctx(_config(fx, mutate))
        out = reg.call("mapping.validate", {}, ctx2).output
        codes = {p["code"] for b in out["bindings"] for p in b["problems"]}
        assert code in codes, (code, codes)

    # Evidence that does not read the column, and confirmations by non-promoters, are refused.
    def wrong_evidence(d):
        _binding(d, "collateral_value")["evidence"] = {"exemplars": ["sl.rates.specials_migration"]}
        _binding(d, "lendable_value")["evidence"] = {"owner_confirmation": "desk-analytics"}
    out = reg.call("mapping.validate", {}, _ctx(_config(fx, wrong_evidence))).output
    msgs = {b["concept"]: " ".join(p["message"] for p in b["problems"]) for b in out["bindings"]}
    assert "does not read main.collateral.collateral_value" in msgs["collateral_value"]
    assert "not a configured promoter" in msgs["lendable_value"]

    # fee vs rebate: evidence computing a non-interchangeable concept is refused (0063).
    def rebate(d):
        d["semantic_mapping"]["fixture_db"].append({
            "concept": "rebate_rate", "expression": "borrow_rates.fee_bps", "aggregation": "none",
            "pit_column": "borrow_rates.business_date", "viewpoint": "lender", "unit": "bps", "quote": "rebate",
            "day_count": "ACT/360", "owner": "lending-lead", "evidence": {"exemplars": ["sl.rates.specials_migration"]}})
    out = reg.call("mapping.validate", {}, _ctx(_config(fx, rebate))).output
    codes = {p["code"] for b in out["bindings"] if b["concept"] == "rebate_rate" for p in b["problems"]}
    assert codes == {"E_MAP_NON_INTERCHANGEABLE"}


def test_ac007_ratio_over_the_same_rows(fx):
    from quantsmith.pipelines.metrics_semantic_layer import Fact, GovernanceError

    ctx, reg = _prepared(fx)
    out = reg.call("mapping.validate", {}, ctx).output
    bound = [b for b in out["bindings"] if b["status"] == "bound"]
    layer, compiled = packs_mod.compile_layer(bound)
    by = {c["metric"]: c for c in compiled}
    assert by["utilization"] == {"metric": "utilization", "kind": "ratio", "compiled": True, "dimensions": ["security"]}
    assert not by["borrow_fee"]["compiled"] and "not a 0008 governed sum" in by["borrow_fee"]["reason"]

    facts = [Fact(period=d, dims={"security": s}, measures={"on_loan_value": ol, "lendable_value": lv})
             for d, s, ol, lv in [(20261021, "S1", 30.0, 100.0), (20261021, "S2", 10.0, 200.0),
                                  (20261022, "S1", 40.0, 100.0), (20261022, "S2", 50.0, 250.0)]]
    for day in (20261021, 20261022):
        total = layer.compute("utilization", facts, period=day)
        slices = layer.compute("on_loan_value", facts, period=day, group_by="security")
        denoms = layer.compute("lendable_value", facts, period=day, group_by="security")
        assert sum(slices.values()) == layer.compute("on_loan_value", facts, period=day)
        assert total == pytest.approx(sum(slices.values()) / sum(denoms.values()))
        by_sec = layer.compute("utilization", facts, period=day, group_by="security")
        assert by_sec == {s: pytest.approx(slices[s] / denoms[s]) for s in slices}
    with pytest.raises(GovernanceError):
        layer.compute("utilization", facts, group_by="counterparty")

    def by_counterparty(d):
        _binding(d, "utilization")["dimensions"] = ["security", "counterparty"]
    b, _ = _validated(_ctx(_config(fx, by_counterparty)), reg, "utilization")
    assert [p["code"] for p in b["problems"]] == ["E_MAP_RATIO_DIMENSION"]
    assert "lendable_value has no counterparty dimension" in b["problems"][0]["message"]

    def mixed(d):
        _binding(d, "lendable_value")["viewpoint"] = "beneficial_owner"
    b, _ = _validated(_ctx(_config(fx, mixed)), reg, "utilization")
    assert "E_MAP_VIEWPOINT_MIX" in {p["code"] for p in b["problems"]}

    def summed_rate(d):
        _binding(d, "utilization").update(numerator="borrow_fee")
    b, _ = _validated(_ctx(_config(fx, summed_rate)), reg, "utilization")
    assert any("must be a summed measure" in p["message"] for p in b["problems"])


def test_ac008_metric_sources_available_or_unavailable(fx):
    ctx, reg = _prepared(fx)
    sources = {s["metric"]: s for s in reg.call("mapping.validate", {}, ctx).output["metric_sources"]}
    assert {m: s["status"] for m, s in sources.items()} == {"lending_revenue": "available", "on_loan_value": "available"}

    ctx2, reg2 = _prepared(fx, _use_v2)
    sources = {s["metric"]: s for s in reg2.call("mapping.validate", {}, ctx2).output["metric_sources"]}
    assert sources["on_loan_value"]["status"] == "unavailable"
    assert "E_SOURCE_DRIFTED" in {r["code"] for r in sources["on_loan_value"]["reasons"]}

    def broken(d):
        d["governed_tier"]["metric_sources"] = [
            {"metric": "utilization", "exemplar_id": "sl.utilization.portfolio.draft", "period_column": "as_of",
             "measure_columns": {"on_loan_value": "on_loan_qty"}},
            {"metric": "lending_revenue", "exemplar_id": "sl.revenue.by_security.period",
             "period_column": "business_date", "dimension_columns": {"fund": "fund_id"},
             "measure_columns": {"lending_revenue": "revenue"}},
            {"metric": "recall_quantity", "exemplar_id": "sl.recalls.open.by_counterparty",
             "period_column": "recall_date", "measure_columns": {"recall_quantity": "recall_qty"}}]
    ctx3, reg3 = _prepared(fx, broken)
    sources = reg3.call("mapping.validate", {}, ctx3).output["metric_sources"]
    codes = [{r["code"] for r in s["reasons"]} for s in sources]
    assert {"E_SOURCE_UNREVIEWED", "E_SOURCE_COLUMN", "E_SOURCE_MEASURES"} <= codes[0]
    assert {"E_SOURCE_DIMENSION", "E_SOURCE_COLUMN"} <= codes[1]
    assert "E_SOURCE_METRIC" in codes[2]                     # only pack metrics are governed
    assert {s["status"] for s in sources} == {"unavailable"}


# --------------------------------------------------------------------------
# Access
# --------------------------------------------------------------------------

def test_ac009_clearance_from_the_roster(fx):
    cfg = _config(fx)
    assert access.caller(cfg, "lending-lead").clearance == "restricted"
    assert access.caller(cfg, "desk-analytics").clearance == "internal"
    stranger = access.caller(cfg, "someone-else")
    assert stranger.active and stranger.clearance == "public"
    (fx / "access" / "roster.yml").write_text("default_clearance: public\npeople:\n")
    assert not access.caller(cfg, "someone-else").active          # empty roster: enforcement inactive (0058)
    (fx / "access" / "roster.yml").write_text("people: [unclosed\n")
    broken = access.caller(cfg, "lending-lead")
    assert broken.active and broken.clearance == "public" and "failing closed" in broken.notes[0]
    assert not access.caller(_config(fx, lambda d: d["access"].update(clearance_source=None)), "x").active

    ctx, reg = _prepared(fx, actor="desk-analytics")
    (fx / "access" / "roster.yml").write_text((PLUGIN / "fixtures" / "access" / "roster.yml").read_text())
    desc = reg.call("access.describe", {}, ctx).output
    assert desc["caller"]["clearance"] == "internal"
    assert {c["column"] for c in desc["columns"] if not c["values_visible"]} == {
        "sec_lending_book.counterparty_id", "counterparties.counterparty_id", "lending.recalls.counterparty_id"}
    cols = reg.call("catalog.describe", {"profile": "fixture_db", "table": "sec_lending_book"}, ctx).output
    hidden = [c["name"] for c in cols["tables"][0]["columns"] if not c["values_visible"]]
    assert hidden == ["counterparty_id"]
    lead = _ctx(ctx.config, "lending-lead")
    cols = reg.call("catalog.describe", {"profile": "fixture_db", "table": "sec_lending_book"}, lead).output
    assert all(c["values_visible"] for c in cols["tables"][0]["columns"])
    assert access.redact_rows([{"counterparty_id": "CP1", "v": 1}], ["counterparty_id"]) == [
        {"counterparty_id": "<redacted>", "v": 1}]


def _research_ctx(fx: Path, actor: str, segments=None):
    _research_db(fx)
    shutil.copy(fx / "access" / "roster.yml", fx / "research" / "roster.yml")

    def classes(d):
        d["access"] = {"clearance_source": "roster.yml",
                       "redaction_classes": {"counterparty_identity": "restricted", "account": "restricted"},
                       "column_classes": {"loan_book.counterparty_id": "counterparty_identity",
                                          "loan_book.account": "account"}}
    return _ctx(_config(fx, classes, name="research/sfmeridian.research.yml"), actor)


def test_ac010_research_withholds_columns_above_clearance(fx):
    from sfmeridian.research.policy import run_research

    context = read_file(fx / "research" / "contexts" / "loan_book.yml")
    ctx = _research_ctx(fx, "desk-analytics")
    run = run_research(ctx, dataset="loan_book", context=context)
    assert run.status == "completed"
    s = ctx.session["research"]
    assert "counterparty_id" in s.context.sensitive_columns
    assert any("withheld at the caller's clearance" in x for x in s.limitations)
    bundle = Path(s.bundle_dir)
    text = "".join(p.read_text(errors="ignore") for p in bundle.rglob("*.json"))
    assert not re.search(r'"CP[123]"', text)                     # no counterparty identifier value in any artifact
    refused = default_registry().call("research.inspect_categories", {"column": "counterparty_id"}, ctx)
    assert refused.error_code == "E_RESEARCH_SENSITIVE"

    lead = _research_ctx(fx, "lending-lead")
    run = run_research(lead, dataset="loan_book", context=context)
    assert "counterparty_id" not in lead.session["research"].context.sensitive_columns

    clash = dict(context, segments=["counterparty_id"])
    ctx3 = _research_ctx(fx, "desk-analytics")
    start = default_registry().call("research.start", {"dataset": "loan_book", "context": clash}, ctx3)
    assert start.error_code == "E_ACCESS_CLEARANCE"


def test_ac011_no_credentials_in_traces_errors_or_artifacts(fx):
    assert access.scrub("postgresql://svc:hunter2@db/x") == "postgresql://svc:<redacted>@db/x"  # qf:allow-secret (deliberate fake)
    assert access.scrub("password=hunter2; token: abc123") == "password=<redacted>; token: <redacted>"
    assert access.scrub("Authorization: Bearer abcdefghijklmnop") == "Authorization: Bearer <redacted>"

    def broken(data):
        data["catalog"]["fixture_db"] = {"source": "introspect"}

    class Exploding:
        def cursor(self):
            raise RuntimeError("login failed for user svc password=hunter2")

    ctx = _ctx(_config(fx, broken), connections={"fixture_db": {"connect": Exploding}})
    run = run_steward(ctx)
    assert run.status == "escalated" and "no catalog snapshot" in run.summary
    blob = json.dumps(run.as_dict())

    class Policy(StewardPolicy):
        def decide(self, state):
            if not state.called("glossary.lookup"):
                from sfmeridian.agent import ToolCall
                return ToolCall("glossary.lookup", {"term": "fee password=hunter2"}, "why token=hunter2")
            return super().decide(state)

    ctx2, _ = _prepared(fx)
    blob += json.dumps(run_steward(ctx2, policy=Policy()).as_dict())
    assert "hunter2" not in blob
    pattern = re.compile(r"(?i)(password|passwd|token|api[_-]?key|secret)\s*[=:]\s*(?!<redacted>)\S")
    for path in (fx / ".sfmeridian").rglob("*"):
        if path.is_file():
            assert not pattern.search(path.read_text(errors="ignore")), path


# --------------------------------------------------------------------------
# Tools, agent, governance, portability
# --------------------------------------------------------------------------

def test_ac012_tools_registered_with_effects():
    reg = default_registry()
    effects = {n: reg.get(n).effect for n in reg.names()}
    assert {n: effects[n] for n in ("catalog.snapshot", "catalog.describe", "catalog.diff", "catalog.reconcile",
                                    "mapping.validate", "metrics.list", "glossary.lookup", "mapping.amendments",
                                    "mapping.propose_amendment", "access.describe")} == {
        "catalog.snapshot": "index", "catalog.describe": "read", "catalog.diff": "read",
        "catalog.reconcile": "index", "mapping.validate": "read", "metrics.list": "read",
        "glossary.lookup": "read", "mapping.amendments": "read", "mapping.propose_amendment": "propose",
        "access.describe": "read"}
    assert set(effects) <= governance.CONTRACT_TOOLS
    manifest = load_manifest("semantic_mapping_steward")
    assert all(effects[t] != "human_only" for t in manifest.tools)
    assert reg.call("catalog.describe", {"profile": 3}, None).error_code == "E_TOOL_INPUT"


def test_ac013_steward_loop(fx):
    ctx = _ctx(_config(fx))
    run = run_steward(ctx)
    assert run.status == "completed", run.summary
    out = run.outputs
    gov = {g["metric"]: g for g in out["governed_metrics"]}
    assert {m for m, g in gov.items() if g["status"] == "bound"} == {"on_loan_value", "borrow_fee", "utilization",
                                                                      "lending_revenue"}
    assert gov["client_debit_balance"]["status"] == "unbound" and gov["client_debit_balance"]["missing"]
    assert sum(1 for a in out["amendments"] if a["staged"]) == 6
    assert out["caveats"] and "unreviewed-pack caveat" in out["caveats"][0]
    staged = sorted(p.name for p in (fx / ".sfmeridian" / "inbox" / "pack_amendments").iterdir())
    assert len(staged) == 6 and "amend.dim.counterparty.json" in staged
    assert [v["name"] for v in run.trace if v["event"] == "verify" and v["ok"]] == list(VERIFIERS)

    fresh = shutil.copytree(PLUGIN / "fixtures", fx.parent / "fresh")
    again = run_steward(_ctx(_config(fresh)))
    assert again.outputs == out and again.run_id == run.run_id          # deterministic from the same inputs

    v2 = run_steward(_ctx(_config(fx, _use_v2)))
    assert v2.status == "completed"
    assert v2.outputs["handoffs"][0]["agent"] == "schema_evolution"
    kinds = {f["kind"] for f in v2.outputs["findings"]}
    assert {"breaking_catalog_change", "drifted_exemplar", "metric_source_unavailable"} <= kinds

    bad = run_steward(_ctx(_config(fx, lambda d: d["governed_tier"].update(domain_tags=["no_such_domain"]))))
    assert bad.status == "escalated" and "no 0081 pack" in bad.summary

    # Verifiers catch a forged finish.
    state = LoopState(load_manifest("semantic_mapping_steward"), {})
    forged = Finish("forged", {"bindings": [{"profile": "fixture_db", "concept": "house_spread", "status": "bound"}],
                               "amendments": [{"amendment_id": "amend.rebate_rate", "status": "accepted"}],
                               "governed_metrics": []})
    problems = [p for v in VERIFIERS.values() for p in v(state, forged).problems]
    assert any("not validated" in p or "did not bind" in p for p in problems)
    assert any("lacks viewpoint" in p for p in problems)
    assert any("only a person accepts" in p for p in problems)
    assert any("metrics.list was never consulted" in p for p in problems)


def test_ac014_agent_files_catalog_and_governance():
    base = ROOT / "agents" / "securities_financing" / "sfmeridian" / "semantic_mapping_steward"
    for f in ("prompt.md", "README.md", "instructions.md", "tasks.md"):
        assert (base / f).exists(), f
    assert "## Spec-Driven Role" in (base / "instructions.md").read_text()
    assert "semantic_mapping_steward" in (ROOT / "agents" / "README.md").read_text()
    assert "semantic_mapping_steward" in (ROOT / "agents" / "agent_registry.yaml").read_text()
    skills = json.loads((ROOT / ".claude" / "skills" / "registry.json").read_text())["skills"]
    assert any(k["agent"] == "securities_financing/sfmeridian/semantic_mapping_steward" for k in skills)
    report = governance.validate_all(ROOT / "agents", registry=default_registry())
    assert report["ok"], report["errors"]
    assert report["counts"]["built_agents"] == 5 and report["counts"]["manifests"] == 5


def test_ac015_portability_and_fallback(fx, monkeypatch):
    assert governance.check_imports() == []
    governed = [p for p in (PLUGIN / "src" / "sfmeridian").rglob("*.py")
                if "quantsmith" in p.read_text() and "import quantsmith" in p.read_text()]
    assert governed and all("governed" in p.parts for p in governed)
    monkeypatch.setattr(packs_mod, "sdk_available", lambda: False)
    packs, source = packs_mod.resolve(ROOT)
    assert source["mode"] == "files" and any(p["pack_id"] == "securities_financing_prime" for p in packs)
    cfg = _config(fx, lambda d: d["governed_tier"].update(packs_root=str(ROOT)))
    vocab = Vocabulary.load(cfg)
    assert vocab.pack["pack_id"] == "securities_financing_prime" and vocab.pack_source["mode"] == "files"
    with pytest.raises(LookupError):
        packs_mod.compile_layer([])


def test_ac016_config_shapes_and_template(fx):
    def bad(d):
        d["catalog"]["fixture_db"] = {"source": "crawl", "drift_policy": "ignore"}
        _binding(d, "borrow_fee")["quote"] = "spread"
        _binding(d, "borrow_fee")["definition"] = "a private meaning"
        _binding(d, "lending_revenue").pop("owner")
        d["governed_tier"]["metric_sources"][0].pop("measure_columns")
    with pytest.raises(ConfigError) as err:
        _config(fx, bad)
    found = {(i.code, i.path) for i in err.value.issues}
    assert ("E_CONFIG_INVALID", "catalog.fixture_db.source") in found
    assert ("E_CONFIG_INVALID", "catalog.fixture_db.drift_policy") in found
    assert any(c == "E_CONFIG_UNKNOWN_KEY" and p.endswith(".definition") for c, p in found)
    assert any(c == "E_CONFIG_INVALID" and p.endswith(".quote") for c, p in found)
    assert any(c == "E_CONFIG_MISSING" and p.endswith(".owner") for c, p in found)
    assert ("E_CONFIG_MISSING", "governed_tier.metric_sources[0].measure_columns") in found
    template = load_config(ROOT / "templates" / "sfmeridian" / "sfmeridian.yml", env={}, allow_placeholders=True)
    assert template.data["semantic_mapping"]


def test_ac017_fixtures_disclosed_and_deterministic(fx):
    disclosure = (PLUGIN / "fixtures" / "README.md").read_text()
    for name in ("catalog/fixture_db.catalog.json", "catalog/fixture_db.catalog.v2.json", "access/roster.yml",
                 "sfmeridian.mapping.yml"):
        assert name in disclosure, name
    ctx, reg = _prepared(fx)
    first = reg.call("mapping.validate", {}, ctx).output
    assert reg.call("mapping.validate", {}, _ctx(_config(fx))).output == first
