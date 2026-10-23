"""Acceptance tests for spec 0116 — governed SQL composition and execution.

The initial slice covers AC-001: the deterministic, fully synthetic executable
SQLite fixture on which the verifier, executor, Reader, and ``ask`` tests build.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "sfmeridian"
FIXTURES = PLUGIN / "fixtures"
EXECUTION = FIXTURES / "execution"
sys.path.insert(0, str(PLUGIN / "src"))

from sfmeridian import catalog as catalog_mod
from sfmeridian.access import caller as resolve_caller
from sfmeridian.agent import Finish, ToolCall
from sfmeridian.catalog import load_declared
from sfmeridian.compose import CompositionError, CompositionRequest, compose
from sfmeridian.composer_agent import run_composer
from sfmeridian.config import ConfigError, apply_call_overrides, load_config, read_file
from sfmeridian.execute import ExecutionError, adapt_query_source, execute, replay
from sfmeridian.frontmatter import split_front_matter
from sfmeridian.governed import packs as packs_mod
from sfmeridian.governed.ask import AskRequest, ask
from sfmeridian.governed.reader import MetricSourceUnavailable, Reader, fact_batch_hash
from sfmeridian.handoff import HandoffError, validate_handoff
from sfmeridian.index import build_index, load_index
from sfmeridian.mapping import Vocabulary, validate_mapping
from sfmeridian.orchestrator import prepare_handoff, run_orchestrator
from sfmeridian.tools import ToolContext, default_registry
from sfmeridian.verify import (
    TokenError,
    VerificationRequest,
    trusted_predicate_literals,
    validate_token,
    verify,
)

from quantsmith.nl_analytics.execute import execute as execute_plan
from quantsmith.nl_analytics.plan import Filter, QueryPlan, TimeWindow

NOW = 1_792_742_400
SIGNING_KEY = b"0116 synthetic verification key!!"


def _fixture_module():
    spec = importlib.util.spec_from_file_location("sfmeridian_execution_fixture", EXECUTION / "fixture_db.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sort_rows(rows, keys):
    return sorted(rows, key=lambda row: tuple((row.get(key) is None, row.get(key)) for key in keys))


def _normalize(rows):
    normalized = []
    for row in rows:
        normalized.append({key: round(value, 10) if isinstance(value, float) else value
                           for key, value in dict(row).items()})
    return normalized


def test_ac001_fixture_matches_catalog_exemplars_and_manifest(tmp_path: Path):
    fixture = _fixture_module()
    first_path = tmp_path / "first.sqlite"
    second_path = tmp_path / "second.sqlite"
    first = fixture.build(first_path)
    second = fixture.build(second_path)

    assert first == second
    assert len(first["logical_sha256"]) == 64
    assert first["row_counts"] == {
        "lending.counterparties": 3,
        "lending.recalls": 4,
        "main.borrow_rates": 6,
        "main.collateral": 8,
        "main.counterparties": 3,
        "main.lendable_inventory": 6,
        "main.program_revenue": 6,
        "main.sec_lending_book": 8,
    }

    catalog = json.loads((FIXTURES / "catalog" / "fixture_db.catalog.json").read_text())
    conn = fixture.connect(first_path)
    assert conn.execute("PRAGMA query_only").fetchone()[0] == 1

    actual_objects = set()
    for table in catalog["tables"]:
        schema, name = table["schema"], table["name"]
        actual_objects.add(f"{schema}.{name}")
        kind = conn.execute(
            f'SELECT type FROM "{schema}".sqlite_master WHERE name = ?', (name,)).fetchone()
        assert kind and kind[0] == table["kind"]
        info = conn.execute(f'PRAGMA "{schema}".table_info("{name}")').fetchall()
        assert [(row[1], row[2].upper(), not bool(row[3])) for row in info] == [
            (column["name"], column["type"], column["nullable"]) for column in table["columns"]]
        primary_key = [row[1] for row in sorted(info, key=lambda row: row[5]) if row[5]]
        assert primary_key == table["primary_key"]
    assert actual_objects == set(first["row_counts"])

    expected = json.loads((EXECUTION / "expected_results.json").read_text())
    seen = set()
    for case in expected["queries"]:
        query_path = FIXTURES / "query_repo" / case["path"]
        meta, sql, _ = split_front_matter(query_path.read_text(), str(query_path))
        assert meta and meta["id"] == case["id"] and meta["review_status"] == "reviewed"
        rows = _normalize(conn.execute(sql, case["params"]).fetchall())
        assert _sort_rows(rows, case["sort_by"]) == _sort_rows(case["rows"], case["sort_by"])
        seen.add(case["id"])
    assert seen == {case["id"] for case in expected["queries"]}
    assert len(seen) == 7
    conn.close()

    disclosure = (FIXTURES / "README.md").read_text()
    assert all(name in disclosure for name in (
        "execution/fixture_db.py", "execution/expected_results.json", "execution/dialect_queries.json"))
    assert "SYNTHETIC" in (EXECUTION / "fixture_db.py").read_text()


def _verification_inputs(tmp_path: Path):
    fx = tmp_path / "fx"
    shutil.copytree(FIXTURES, fx)
    config = load_config(fx / "sfmeridian.mapping.yml", env={})
    report = build_index(config)
    assert report.errors == []
    snapshot = load_declared(fx / "catalog" / "fixture_db.catalog.json", config.profile("fixture_db"))
    graph = json.loads((fx / ".sfmeridian" / "index" / "join_graph.json").read_text())
    return config, snapshot, graph


def _verify(config, snapshot, graph, sql, params=None, **request):
    return verify(
        VerificationRequest(sql=sql, params=params or {}, profile="fixture_db", **request),
        profile=config.profile("fixture_db"),
        snapshot=snapshot,
        join_graph=graph,
        config_hash=config.hash,
        key_id="fixture-key",
        signing_key=SIGNING_KEY,
        now=NOW,
        ttl_s=config.data["verification"]["token_ttl_s"],
    )


def _codes(outcome):
    return {finding.code for finding in outcome.findings}


class _SQLiteQuerySource:
    read_only = True
    profile = "fixture_db"
    dialect = "sqlite"

    def __init__(self, connection):
        self.connection = connection
        self.calls = []

    def query(self, sql, params, *, timeout_s, row_limit):
        self.calls.append({"sql": sql, "params": dict(params), "timeout_s": timeout_s,
                           "row_limit": row_limit})
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]


def _execution_case(tmp_path: Path, *, clearance="public"):
    config, snapshot, graph = _verification_inputs(tmp_path)
    fixture = _fixture_module()
    db_path = tmp_path / "execution.sqlite"
    fixture.build(db_path)
    query_path = FIXTURES / "query_repo" / "lending" / "on_loan_value_by_counterparty.sql"
    _, sql, _ = split_front_matter(query_path.read_text(), str(query_path))
    request = VerificationRequest(
        sql=sql, params={"as_of": "2026-10-22"}, profile="fixture_db",
        as_of="2026-10-22", require_pit=True,
        pit_columns=("sec_lending_book.business_date",), clearance=clearance,
        composition_path="reuse", query_id="sl.on_loan_value.by_counterparty.as_of",
        trusted_literal_hashes=trusted_predicate_literals(sql, "sqlite"),
    )
    outcome = verify(
        request, profile=config.profile("fixture_db"), snapshot=snapshot, join_graph=graph,
        config_hash=config.hash, key_id="fixture-key", signing_key=SIGNING_KEY, now=NOW,
        ttl_s=config.data["verification"]["token_ttl_s"],
    )
    assert outcome.ok and outcome.verified
    return config, snapshot, graph, fixture, db_path, request, outcome.verified


def _reader_inputs(tmp_path: Path, *, mutate_config=None, draft_source=False):
    fx = tmp_path / "fx"
    shutil.copytree(FIXTURES, fx)
    if draft_source:
        path = fx / "query_repo" / "lending" / "on_loan_value_by_counterparty.sql"
        path.write_text(path.read_text().replace("review_status: reviewed", "review_status: draft"))
    if mutate_config is None:
        config = load_config(fx / "sfmeridian.mapping.yml", env={})
    else:
        data = read_file(fx / "sfmeridian.mapping.yml")
        mutate_config(data)
        changed = fx / "changed.json"
        changed.write_text(json.dumps(data))
        config = load_config(changed, env={})
    report = build_index(config)
    assert report.errors == []
    index_dir = config.resolve_path(config.data["index"]["dir"])
    catalog_path = config.resolve_path(config.data["catalog"]["fixture_db"]["file"])
    snapshot = load_declared(catalog_path, config.profile("fixture_db"))
    catalog_mod.store(index_dir, snapshot, "2026-10-22")
    exemplars = [json.loads(line) for line in (index_dir / "exemplars.jsonl").read_text().splitlines()]
    repo_profiles = {item["id"]: item.get("database_profile")
                     for item in config.data["query_repositories"]}
    drift = catalog_mod.reconcile(
        {"fixture_db": snapshot}, exemplars,
        {"fixture_db": config.data["catalog"]["fixture_db"]["drift_policy"]},
        repo_profiles,
    )
    catalog_mod.write_drift(index_dir, drift)
    mapping_report = validate_mapping(config, index_dir, Vocabulary.load(config))
    graph = json.loads((index_dir / "join_graph.json").read_text())
    return config, snapshot, graph, load_index(index_dir), mapping_report


def test_ac002_composition_reuse_adapt_generate_with_evidence(tmp_path: Path):
    config, snapshot, graph = _verification_inputs(tmp_path)
    index_dir = config.resolve_path(config.data["index"]["dir"])
    index = load_index(index_dir)
    before = {path.name: path.read_bytes() for path in index_dir.iterdir() if path.is_file()}
    profile = config.profile("fixture_db")

    reuse_request = CompositionRequest(
        question="on loan value by counterparty as of", profile="fixture_db", params={},
        as_of="2026-10-22",
    )
    reuse = compose(reuse_request, index=index, profile=profile, snapshot=snapshot)
    assert reuse.path == "reuse" and reuse.query_id == "sl.on_loan_value.by_counterparty.as_of"
    assert reuse.params == {"as_of": "2026-10-22"}
    assert reuse.as_dict()["params"] == {"as_of": "2026-10-22"}
    assert len(reuse.source_exemplars) == 1 and reuse.catalog_objects == (
        "main.counterparties", "main.sec_lending_book")
    base = index.get(str(reuse.source_exemplars[0]["id"]))
    assert base and reuse.sql == base["sql"]
    assert compose(reuse_request, index=index, profile=profile, snapshot=snapshot).content_hash == reuse.content_hash

    calls = []

    def scripted(context):
        calls.append(context)
        if context["mode"] == "adapt":
            return {
                "sql": (
                    "SELECT bk.counterparty_id, SUM(bk.on_loan_qty) AS on_loan_qty "
                    "FROM sec_lending_book bk WHERE bk.business_date = :as_of "
                    "GROUP BY bk.counterparty_id LIMIT 500"
                ),
                "source_exemplar_ids": [context["exemplars"][0]["exemplar_id"]],
                "limitations": ["Synthetic fixture adaptation."],
            }
        assert context["mode"] == "generate" and context["exemplars"] == []
        return {
            "sql": (
                "SELECT br.security_id, AVG(br.fee_bps) AS avg_fee_bps "
                "FROM borrow_rates br WHERE br.business_date = :as_of "
                "GROUP BY br.security_id LIMIT 100"
            ),
            "source_exemplar_ids": [],
            "limitations": ["Generated candidate; verification is still required."],
        }

    adapt = compose(
        CompositionRequest(
            question="on loan totals by borrower", profile="fixture_db", params={},
            as_of="2026-10-22",
        ),
        index=index, profile=profile, snapshot=snapshot, completer=scripted,
    )
    assert adapt.path == "adapt" and adapt.query_id is None and len(adapt.source_exemplars) == 1
    assert adapt.limitations == ("Synthetic fixture adaptation.",)
    adapted_verification = verify(
        adapt.verification_request(), profile=profile, snapshot=snapshot, join_graph=graph,
        config_hash=config.hash, key_id="fixture-key", signing_key=SIGNING_KEY, now=NOW,
    )
    assert adapted_verification.ok, adapted_verification.as_dict()

    generated = compose(
        CompositionRequest(
            question="zeta frobnicator report", profile="fixture_db", params={},
            as_of="2026-10-22", pit_columns=("borrow_rates.business_date",),
        ),
        index=index, profile=profile, snapshot=snapshot, completer=scripted,
    )
    assert generated.path == "generate" and generated.source_exemplars == ()
    assert generated.catalog_objects == ("main.borrow_rates",)
    generated_verification = verify(
        generated.verification_request(), profile=profile, snapshot=snapshot, join_graph=graph,
        config_hash=config.hash, key_id="fixture-key", signing_key=SIGNING_KEY, now=NOW,
    )
    assert generated_verification.ok, generated_verification.as_dict()
    assert [call["mode"] for call in calls] == ["adapt", "generate"]
    completion_payload = json.dumps(calls, sort_keys=True)
    assert "secret_ref" not in completion_payload and "expected_results" not in completion_payload

    after = {path.name: path.read_bytes() for path in index_dir.iterdir() if path.is_file()}
    assert after == before
    assert all(generated.sql not in data.decode("utf-8", errors="ignore") for data in after.values())

    with pytest.raises(CompositionError, match="not in catalog"):
        compose(
            CompositionRequest(
                question="omega unindexed request", profile="fixture_db", params={},
                as_of="2026-10-22", pit_columns=("borrow_rates.business_date",),
            ),
            index=index, profile=profile, snapshot=snapshot,
            completer=lambda _context: {
                "sql": "SELECT invented FROM borrow_rates WHERE business_date = :as_of LIMIT 5",
                "source_exemplar_ids": [], "limitations": ["fixture rejection"],
            },
        )
    with pytest.raises(CompositionError, match="no-governed-match"):
        compose(
            CompositionRequest(
                question="on loan value", profile="fixture_db", params={},
                route_outcome="governed_answer",
            ),
            index=index, profile=profile, snapshot=snapshot,
        )


def test_ac003_verifier_rejects_adversarial_queries_without_execution(tmp_path: Path):
    config, snapshot, graph = _verification_inputs(tmp_path)
    safe = """
        SELECT bk.loan_id, cp.credit_tier
        FROM sec_lending_book bk
        JOIN counterparties cp ON cp.counterparty_id = bk.counterparty_id
        WHERE bk.business_date = :as_of
        LIMIT 50
    """
    good = _verify(config, snapshot, graph, safe, {"as_of": "2026-10-22"},
                   as_of="2026-10-22", require_pit=True,
                   pit_columns=("sec_lending_book.business_date",))
    assert good.ok and good.verified and good.findings == ()
    assert good.verified.public()["parameter_names"] == ["as_of"]
    assert "2026-10-22" not in good.verified.token

    cases = [
        ("SELECT made_up FROM sec_lending_book LIMIT 5", {}, "E_VERIFY_UNKNOWN_IDENTIFIER"),
        ("SELECT security_id FROM invented_table LIMIT 5", {}, "E_VERIFY_UNKNOWN_IDENTIFIER"),
        ("DELETE FROM sec_lending_book", {}, "E_VERIFY_NOT_READ_ONLY"),
        ("WITH gone AS (DELETE FROM sec_lending_book RETURNING loan_id) SELECT * FROM gone LIMIT 5", {},
         "E_VERIFY_NOT_READ_ONLY"),
        ("SELECT loan_id FROM sec_lending_book LIMIT 5; SELECT loan_id FROM collateral LIMIT 5", {},
         "E_VERIFY_MULTI_STATEMENT"),
        ("SELECT loan_id FROM sec_lending_book WHERE status = 'OPEN' LIMIT 5", {},
         "E_VERIFY_UNBOUND_PARAM"),
        ("SELECT loan_id FROM sec_lending_book WHERE business_date = :as_of LIMIT 5", {},
         "E_VERIFY_UNBOUND_PARAM"),
        ("SELECT loan_id FROM sec_lending_book WHERE business_date = :as_of LIMIT 5",
         {"as_of": "2026-10-22", "extra": 1}, "E_VERIFY_UNBOUND_PARAM"),
        ("SELECT loan_id FROM sec_lending_book", {}, "E_VERIFY_NO_LIMIT"),
        ("SELECT loan_id FROM sec_lending_book LIMIT 10001", {}, "E_VERIFY_NO_LIMIT"),
        ("PRAGMA table_info(sec_lending_book)", {}, "E_VERIFY_NOT_READ_ONLY"),
        ("SELECT security_id, SUM(on_loan_value) FROM sec_lending_book GROUP BY invented LIMIT 5", {},
         "E_VERIFY_UNKNOWN_IDENTIFIER"),
        ("SELECT loan_id FROM sec_lending_book UNION SELECT loan_id FROM collateral LIMIT 5", {},
         "E_VERIFY_UNKNOWN_IDENTIFIER"),
    ]
    for sql, params, code in cases:
        outcome = _verify(config, snapshot, graph, sql, params)
        assert not outcome.ok and outcome.verified is None and code in _codes(outcome), (sql, outcome.as_dict())

    wrong_join = """
        SELECT bk.loan_id, cp.credit_tier
        FROM sec_lending_book bk
        JOIN counterparties cp ON cp.credit_tier = bk.status
        LIMIT 50
    """
    assert "E_VERIFY_JOIN_KEY" in _codes(_verify(config, snapshot, graph, wrong_join))

    missing_pit = _verify(config, snapshot, graph,
                          "SELECT loan_id FROM sec_lending_book LIMIT 5", {},
                          as_of="2026-10-22", require_pit=True,
                          pit_columns=("sec_lending_book.business_date",))
    assert "E_VERIFY_MISSING_PIT" in _codes(missing_pit)

    denied = dict(config.profile("fixture_db"))
    denied["tables_allowlist"] = ["borrow_rates"]
    outcome = verify(
        VerificationRequest("SELECT loan_id FROM sec_lending_book LIMIT 5", {}, "fixture_db"),
        profile=denied,
        snapshot=snapshot,
        join_graph=graph,
        config_hash=config.hash,
        key_id="fixture-key",
        signing_key=SIGNING_KEY,
        now=NOW,
    )
    assert "E_VERIFY_TABLE_NOT_ALLOWED" in _codes(outcome)

    reviewed = "SELECT loan_id FROM sec_lending_book WHERE status = 'OPEN' LIMIT 5"
    allowed = _verify(
        config, snapshot, graph, reviewed, {},
        trusted_literal_hashes=trusted_predicate_literals(reviewed, "sqlite"),
    )
    assert allowed.ok

    # The two reviewed as-of exemplars used by the governed mapping pass with
    # only their reviewed structural literals trusted.
    reviewed_cases = [
        ("lending/on_loan_value_by_counterparty.sql", {"as_of": "2026-10-22"},
         ("sec_lending_book.business_date",)),
        ("lending/utilization_by_security.sql", {"as_of": "2026-10-22", "min_lendable": 0},
         ("lendable_inventory.business_date", "sec_lending_book.business_date")),
    ]
    for relative, params, pit_columns in reviewed_cases:
        _, exemplar_sql, _ = split_front_matter(
            (FIXTURES / "query_repo" / relative).read_text(), relative)
        outcome = _verify(
            config, snapshot, graph, exemplar_sql, params,
            as_of="2026-10-22", require_pit=True, pit_columns=pit_columns,
            trusted_literal_hashes=trusted_predicate_literals(exemplar_sql, "sqlite"),
        )
        assert outcome.ok, (relative, outcome.as_dict())


def test_ac004_dialect_limits_pit_timeout_and_cost_guard(tmp_path: Path):
    config, snapshot, graph = _verification_inputs(tmp_path)
    fixtures = json.loads((EXECUTION / "dialect_queries.json").read_text())
    assert fixtures["synthetic"] is True
    assert {case["dialect"] for case in fixtures["queries"]} == {
        "sqlite", "postgres", "oracle", "databricks"}

    calls = []

    def explain(sql, params, *, timeout_s):
        calls.append((sql, params, timeout_s))
        return {"cost": 99, "notes": ["synthetic normalized fixture cost"]}

    for case in fixtures["queries"]:
        profile = dict(config.profile("fixture_db"))
        profile.update(dialect=case["dialect"], explain_cost_limit=100)
        outcome = verify(
            VerificationRequest(
                sql=case["sql"], params={"as_of": "2026-10-22"}, profile="fixture_db",
                as_of="2026-10-22", require_pit=True,
                pit_columns=("borrow_rates.business_date",),
            ),
            profile=profile,
            snapshot=snapshot,
            join_graph=graph,
            config_hash=config.hash,
            key_id="fixture-key",
            signing_key=SIGNING_KEY,
            now=NOW,
            ttl_s=config.data["verification"]["token_ttl_s"],
            explainer=explain,
        )
        assert outcome.ok and outcome.verified, (case["dialect"], outcome.as_dict())
        assert outcome.verified.record.timeout_s == 30
        assert outcome.verified.record.explain_cost == 99.0
        assert "notes" not in outcome.verified.public()
    assert len(calls) == 4
    assert all(params == {"as_of": "2026-10-22"} and timeout == 30
               for _, params, timeout in calls)

    by_dialect = {case["dialect"]: case["sql"] for case in fixtures["queries"]}
    invalid = [
        ("postgres", by_dialect["postgres"].replace("%(as_of)s", ":as_of"),
         "E_VERIFY_UNBOUND_PARAM"),
        ("oracle", by_dialect["oracle"].replace("FETCH FIRST 5 ROWS ONLY", "LIMIT 5"),
         "E_VERIFY_NO_LIMIT"),
        ("databricks", by_dialect["databricks"].replace("`", '"'),
         "E_VERIFY_UNKNOWN_IDENTIFIER"),
    ]
    for dialect, sql, code in invalid:
        profile = dict(config.profile("fixture_db"))
        profile["dialect"] = dialect
        outcome = verify(
            VerificationRequest(sql, {"as_of": "2026-10-22"}, "fixture_db"),
            profile=profile, snapshot=snapshot, join_graph=graph, config_hash=config.hash,
            key_id="fixture-key", signing_key=SIGNING_KEY, now=NOW,
        )
        assert not outcome.ok and code in _codes(outcome)

    guarded = dict(config.profile("fixture_db"))
    guarded["explain_cost_limit"] = 100
    request = VerificationRequest(
        by_dialect["sqlite"], {"as_of": "2026-10-22"}, "fixture_db",
        as_of="2026-10-22", require_pit=True, pit_columns=("borrow_rates.business_date",),
    )
    missing = verify(
        request, profile=guarded, snapshot=snapshot, join_graph=graph, config_hash=config.hash,
        key_id="fixture-key", signing_key=SIGNING_KEY, now=NOW,
    )
    assert not missing.ok and missing.verified is None and _codes(missing) == {"E_VERIFY_COST"}
    over = verify(
        request, profile=guarded, snapshot=snapshot, join_graph=graph, config_hash=config.hash,
        key_id="fixture-key", signing_key=SIGNING_KEY, now=NOW,
        explainer=lambda *_args, **_kwargs: {"cost": 101, "notes": []},
    )
    assert not over.ok and over.verified is None and _codes(over) == {"E_VERIFY_COST"}

    def failed_explain(*_args, **_kwargs):
        raise RuntimeError("credential=synthetic-secret-must-not-leak")

    failed = verify(
        request, profile=guarded, snapshot=snapshot, join_graph=graph, config_hash=config.hash,
        key_id="fixture-key", signing_key=SIGNING_KEY, now=NOW, explainer=failed_explain,
    )
    assert not failed.ok and _codes(failed) == {"E_VERIFY_COST"}
    assert "synthetic-secret-must-not-leak" not in json.dumps(failed.as_dict())

    source = read_file(FIXTURES / "sfmeridian.mapping.yml")
    source["verification"] = {"token_ttl_s": 45}
    short = load_config(data=source, env={})
    assert short.data["verification"]["token_ttl_s"] == 45
    assert apply_call_overrides(short, {"token_ttl_s": 20}) == {"token_ttl_s": 20}
    with pytest.raises(ConfigError, match="may only be lowered"):
        apply_call_overrides(short, {"token_ttl_s": 46})
    for invalid_ttl in (0, 3601):
        source["verification"] = {"token_ttl_s": invalid_ttl}
        with pytest.raises(ConfigError, match="verification.token_ttl_s"):
            load_config(data=source, env={})

    source = read_file(FIXTURES / "sfmeridian.mapping.yml")
    source["databases"][0]["explain_cost_limit"] = 0
    with pytest.raises(ConfigError, match="explain_cost_limit"):
        load_config(data=source, env={})


def test_ac005_token_binds_every_context_field_and_expires(tmp_path: Path):
    config, snapshot, graph = _verification_inputs(tmp_path)
    sql = "SELECT loan_id FROM sec_lending_book WHERE business_date = :as_of LIMIT 5"
    outcome = _verify(config, snapshot, graph, sql, {"as_of": "2026-10-22"},
                      as_of="2026-10-22", require_pit=True,
                      pit_columns=("sec_lending_book.business_date",), clearance="internal")
    assert outcome.ok and outcome.verified
    verified = outcome.verified
    assert validate_token(verified.token, verified, keys={"fixture-key": SIGNING_KEY}, now=NOW) == verified.record

    signature_tampered = verified.token[:-1] + ("A" if verified.token[-1] != "A" else "B")
    with pytest.raises(TokenError):
        validate_token(signature_tampered, verified, keys={"fixture-key": SIGNING_KEY}, now=NOW)
    with pytest.raises(TokenError, match="unknown verification key"):
        validate_token(verified.token.replace(".fixture-key.", ".missing-key."), verified,
                       keys={"fixture-key": SIGNING_KEY}, now=NOW)
    with pytest.raises(TokenError, match="validity window"):
        validate_token(verified.token, verified, keys={"fixture-key": SIGNING_KEY}, now=NOW + 301)

    mutations = [
        replace(verified, sql=sql.replace("LIMIT 5", "LIMIT 4")),
        replace(verified, params_json=json.dumps({"as_of": "2026-10-21"}, separators=(",", ":"))),
        replace(verified, record=replace(verified.record, profile="other")),
        replace(verified, record=replace(verified.record, snapshot_id="other")),
        replace(verified, record=replace(verified.record, config_hash="other")),
        replace(verified, record=replace(verified.record, policy_version="sql-verify/2")),
        replace(verified, record=replace(verified.record, clearance="restricted")),
        replace(verified, record=replace(verified.record, composition_path="generate")),
        replace(verified, record=replace(verified.record, timeout_s=29)),
        replace(verified, record=replace(verified.record, explain_cost=1.0)),
    ]
    for changed in mutations:
        with pytest.raises(TokenError, match="context mismatch"):
            validate_token(verified.token, changed, keys={"fixture-key": SIGNING_KEY}, now=NOW)

    public = verified.public()
    rendered = json.dumps(public, sort_keys=True)
    assert "2026-10-22" not in rendered and SIGNING_KEY.decode() not in rendered


def test_ac006_query_only_execution_redacts_and_scrubs(tmp_path: Path):
    config, snapshot, _, fixture, db_path, _, verified = _execution_case(tmp_path)
    who = resolve_caller(config, "public-reader")
    connection = fixture.connect(db_path)
    raw_source = _SQLiteQuerySource(connection)
    source = adapt_query_source(raw_source, profile="fixture_db", dialect="sqlite")
    assert not hasattr(source, "execute") and not hasattr(source, "transaction")

    ticks = iter((1_000_000_000, 1_000_000_000))
    result = execute(
        verified, token=verified.token, params={"as_of": "2026-10-22"},
        keys={"fixture-key": SIGNING_KEY}, now=NOW, config=config,
        snapshot_id=snapshot["snapshot_id"], caller=who, source=source,
        source_exemplars=("sl.on_loan_value.by_counterparty.as_of",),
        monotonic_ns=lambda: next(ticks),
    )
    assert len(raw_source.calls) == 1
    assert raw_source.calls[0]["timeout_s"] == 30 and raw_source.calls[0]["row_limit"] == 500
    assert result.provenance.elapsed_ms == 0 and result.provenance.row_count == 3
    assert result.provenance.withheld_columns == ("counterparty_id",)
    assert {row["counterparty_id"] for row in result.rows} == {"<redacted>"}
    assert result.provenance.parameters == {"as_of": "2026-10-22"}
    assert result.provenance.source_exemplars == ("sl.on_loan_value.by_counterparty.as_of",)
    connection.close()

    calls_before = len(raw_source.calls)
    with pytest.raises(ExecutionError, match="E_EXEC_TOKEN"):
        execute(
            verified, token=verified.token, params={"as_of": "2026-10-21"},
            keys={"fixture-key": SIGNING_KEY}, now=NOW, config=config,
            snapshot_id=snapshot["snapshot_id"], caller=who, source=source,
        )
    assert len(raw_source.calls) == calls_before
    with pytest.raises(ExecutionError, match="query-only adapter"):
        execute(
            verified, token=verified.token, params=verified.params,
            keys={"fixture-key": SIGNING_KEY}, now=NOW, config=config,
            snapshot_id=snapshot["snapshot_id"], caller=who, source=raw_source,
        )

    class WritableSource:
        read_only = False

        def query(self, *_args, **_kwargs):  # pragma: no cover - must not be reachable
            raise AssertionError("query should not be called")

    with pytest.raises(ExecutionError, match="not declared read-only"):
        adapt_query_source(WritableSource(), profile="fixture_db", dialect="sqlite")

    class BrokenSource:
        read_only = True
        profile = "fixture_db"
        dialect = "sqlite"

        def query(self, *_args, **_kwargs):
            raise RuntimeError("password=synthetic-secret-must-not-leak")

    broken = adapt_query_source(BrokenSource(), profile="fixture_db", dialect="sqlite")
    with pytest.raises(ExecutionError) as failure:
        execute(
            verified, token=verified.token, params=verified.params,
            keys={"fixture-key": SIGNING_KEY}, now=NOW, config=config,
            snapshot_id=snapshot["snapshot_id"], caller=who, source=broken,
        )
    assert failure.value.code == "E_EXEC_TIMEOUT"
    assert "synthetic-secret-must-not-leak" not in str(failure.value)

    # Non-as-of inputs are always redacted in provenance, even when harmless
    # fixture values are used, and selected restricted columns stay masked.
    sql = ("SELECT loan_id, counterparty_id FROM sec_lending_book "
           "WHERE business_date = :as_of AND counterparty_id = :counterparty LIMIT 5")
    request = VerificationRequest(
        sql, {"as_of": "2026-10-22", "counterparty": "CP-A"}, "fixture_db",
        as_of="2026-10-22", require_pit=True,
        pit_columns=("sec_lending_book.business_date",), clearance="public",
    )
    outcome = verify(
        request, profile=config.profile("fixture_db"), snapshot=snapshot, join_graph=[],
        config_hash=config.hash, key_id="fixture-key", signing_key=SIGNING_KEY, now=NOW,
    )
    assert outcome.ok and outcome.verified
    connection = fixture.connect(db_path)
    source = adapt_query_source(_SQLiteQuerySource(connection), profile="fixture_db", dialect="sqlite")
    sensitive = execute(
        outcome.verified, token=outcome.verified.token, params=request.params,
        keys={"fixture-key": SIGNING_KEY}, now=NOW, config=config,
        snapshot_id=snapshot["snapshot_id"], caller=who, source=source,
    )
    rendered = json.dumps(sensitive.as_dict(), sort_keys=True)
    assert sensitive.provenance.parameters["counterparty"] == "<redacted>"
    assert "CP-A" not in rendered and SIGNING_KEY.decode() not in rendered
    connection.close()


def test_ac007_execution_provenance_envelope_and_replay(tmp_path: Path):
    config, snapshot, graph, fixture, db_path, request, verified = _execution_case(tmp_path)
    who = resolve_caller(config, "public-reader")

    def run_source():
        connection = fixture.connect(db_path)
        raw = _SQLiteQuerySource(connection)
        return connection, adapt_query_source(raw, profile="fixture_db", dialect="sqlite")

    connection, source = run_source()
    ticks = iter((2_000_000_000, 2_000_000_000))
    first = execute(
        verified, token=verified.token, params=request.params,
        keys={"fixture-key": SIGNING_KEY}, now=NOW, config=config,
        snapshot_id=snapshot["snapshot_id"], caller=who, source=source,
        source_exemplars=(request.query_id,), monotonic_ns=lambda: next(ticks),
    )
    connection.close()
    provenance = first.provenance.as_dict()
    required = {
        "run_id", "query_id", "sql_hash", "params_hash", "path", "source_exemplars",
        "profile", "dialect", "snapshot_id", "config_hash", "policy_version", "as_of",
        "parameter_names", "parameters", "row_count", "truncated", "elapsed_ms",
        "explain_cost", "clearance", "withheld_columns", "rows_hash",
    }
    assert required <= set(provenance)
    envelope = first.envelope()
    assert envelope["schema_version"] == "quantsmith.orchestration.run.v1"
    assert envelope["run_id"] == provenance["run_id"]
    assert envelope["replay"]["expected_rows_hash"] == provenance["rows_hash"]
    assert [event["event"] for event in envelope["audit_events"]] == [
        "gate_result", "data_source_read", "run_completed"]

    connection, source = run_source()
    ticks = iter((3_000_000_000, 3_000_000_000))
    same = replay(
        first, request, profile=config.profile("fixture_db"), snapshot=snapshot,
        join_graph=graph, config=config, key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW, source=source, caller=who,
        source_exemplars=(request.query_id,),
        ttl_s=config.data["verification"]["token_ttl_s"], monotonic_ns=lambda: next(ticks),
    )
    connection.close()
    assert same.status == "replayed" and same.mismatches == () and same.current
    assert same.current.rows == first.rows and same.current.provenance.rows_hash == first.provenance.rows_hash

    writer = fixture.connect(db_path, query_only=False)
    writer.execute(
        "UPDATE sec_lending_book SET on_loan_value = on_loan_value + 1 "
        "WHERE loan_id = 'LOAN-A-A' AND business_date = '2026-10-22'")
    writer.commit()
    writer.close()
    connection, source = run_source()
    changed_rows = replay(
        first, request, profile=config.profile("fixture_db"), snapshot=snapshot,
        join_graph=graph, config=config, key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW, source=source, caller=who,
        source_exemplars=(request.query_id,),
        ttl_s=config.data["verification"]["token_ttl_s"],
    )
    connection.close()
    assert changed_rows.status == "mismatch" and "rows_hash" in changed_rows.mismatches

    fixture.build(db_path)
    changed_snapshot = copy.deepcopy(snapshot)
    changed_snapshot["snapshot_id"] = "changed-snapshot"
    connection, source = run_source()
    changed_catalog = replay(
        first, request, profile=config.profile("fixture_db"), snapshot=changed_snapshot,
        join_graph=graph, config=config, key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW, source=source, caller=who,
        source_exemplars=(request.query_id,),
        ttl_s=config.data["verification"]["token_ttl_s"],
    )
    connection.close()
    assert changed_catalog.status == "mismatch"
    assert {"run_id", "snapshot_id"} <= set(changed_catalog.mismatches)


def test_ac008_reader_facts_reproduce_sources_and_drift_is_unavailable(tmp_path: Path):
    config, snapshot, graph, index, mapping_report = _reader_inputs(tmp_path / "available")
    fixture = _fixture_module()
    db_path = tmp_path / "reader.sqlite"
    fixture.build(db_path)
    connection = fixture.connect(db_path)
    raw_source = _SQLiteQuerySource(connection)
    source = adapt_query_source(raw_source, profile="fixture_db", dialect="sqlite")
    reader = Reader(
        config=config, index=index, mapping_report=mapping_report, snapshot=snapshot,
        join_graph=graph, caller=resolve_caller(config, "lending-lead"), source=source,
        key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW,
    )

    revenue_plan = QueryPlan(
        metric="lending_revenue", dimensions=("security",),
        filters=(Filter("security", "eq", ("SEC-B",)),),
        window=TimeWindow(20261021, 20261022, "day"), comparison=None, rank=None,
        defaults_applied=(), interpreter="fixture",
    )
    revenue_facts = tuple(reader(revenue_plan))
    assert sum(fact.measures["lending_revenue"] for fact in revenue_facts) == 125.0
    assert {fact.period for fact in revenue_facts} == {20261022}
    assert {tuple(sorted(fact.dims)) for fact in revenue_facts} == {
        ("borrow_category", "security")}
    assert raw_source.calls[-1]["params"] == {
        "start_date": "2026-10-21", "end_date": "2026-10-22"}
    layer, compiled = packs_mod.compile_layer(mapping_report["bindings"])
    assert any(item["metric"] == "lending_revenue" and item["compiled"] for item in compiled)
    filtered = execute_plan(revenue_plan, layer, reader=lambda _plan: revenue_facts, as_of=20261022)
    assert filtered.total == 45.0 and filtered.row_count == 2

    exposure_plan = QueryPlan(
        metric="on_loan_value", dimensions=("counterparty",), filters=(),
        window=TimeWindow(20261022, 20261022, "day"), comparison=None, rank=None,
        defaults_applied=("window",), interpreter="fixture",
    )
    exposure_facts = tuple(reader(exposure_plan))
    assert sum(fact.measures["on_loan_value"] for fact in exposure_facts) == 7801.5
    assert {fact.dims["counterparty"] for fact in exposure_facts} == {"CP-A", "CP-B", "CP-C"}
    assert raw_source.calls[-1]["params"] == {"as_of": "2026-10-22"}
    evidence = reader.evidence.for_plan(exposure_plan)
    assert evidence and evidence.batch_hash == fact_batch_hash(exposure_facts)
    assert evidence.source_query_id == "sl.on_loan_value.by_counterparty.as_of"
    assert evidence.provenance.run_id.startswith("sfm-")
    assert evidence.provenance.snapshot_id == snapshot["snapshot_id"]
    assert evidence.provenance.config_hash == config.hash
    calls_before = len(raw_source.calls)
    public_reader = Reader(
        config=config, index=index, mapping_report=mapping_report, snapshot=snapshot,
        join_graph=graph, caller=resolve_caller(config, "public-reader"), source=source,
        key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW,
    )
    with pytest.raises(MetricSourceUnavailable, match="caller-unauthorized"):
        public_reader(exposure_plan)
    assert len(raw_source.calls) == calls_before
    connection.close()

    def use_v2(data):
        data["catalog"]["fixture_db"]["file"] = "catalog/fixture_db.catalog.v2.json"

    v2_config, v2_snapshot, v2_graph, v2_index, v2_mapping = _reader_inputs(
        tmp_path / "drifted", mutate_config=use_v2)
    connection = fixture.connect(db_path)
    v2_raw = _SQLiteQuerySource(connection)
    v2_reader = Reader(
        config=v2_config, index=v2_index, mapping_report=v2_mapping, snapshot=v2_snapshot,
        join_graph=v2_graph, caller=resolve_caller(v2_config, "lending-lead"),
        source=adapt_query_source(v2_raw, profile="fixture_db", dialect="sqlite"),
        key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW,
    )
    with pytest.raises(MetricSourceUnavailable) as drifted:
        v2_reader(exposure_plan)
    assert drifted.value.code == "E_METRIC_SOURCE_UNAVAILABLE" and v2_raw.calls == []
    connection.close()

    draft_config, draft_snapshot, draft_graph, draft_index, draft_mapping = _reader_inputs(
        tmp_path / "draft", draft_source=True)
    connection = fixture.connect(db_path)
    draft_raw = _SQLiteQuerySource(connection)
    draft_reader = Reader(
        config=draft_config, index=draft_index, mapping_report=draft_mapping,
        snapshot=draft_snapshot, join_graph=draft_graph,
        caller=resolve_caller(draft_config, "lending-lead"),
        source=adapt_query_source(draft_raw, profile="fixture_db", dialect="sqlite"),
        key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW,
    )
    with pytest.raises(MetricSourceUnavailable):
        draft_reader(exposure_plan)
    assert draft_raw.calls == []
    connection.close()

    def mismatch_source(data):
        metric_source = next(item for item in data["governed_tier"]["metric_sources"]
                             if item["metric"] == "on_loan_value")
        metric_source["measure_columns"] = {"wrong_measure": "on_loan_value"}

    bad_config, bad_snapshot, bad_graph, bad_index, bad_mapping = _reader_inputs(
        tmp_path / "mismatch", mutate_config=mismatch_source)
    connection = fixture.connect(db_path)
    bad_raw = _SQLiteQuerySource(connection)
    bad_reader = Reader(
        config=bad_config, index=bad_index, mapping_report=bad_mapping, snapshot=bad_snapshot,
        join_graph=bad_graph, caller=resolve_caller(bad_config, "lending-lead"),
        source=adapt_query_source(bad_raw, profile="fixture_db", dialect="sqlite"),
        key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW,
    )
    with pytest.raises(MetricSourceUnavailable):
        bad_reader(exposure_plan)
    assert bad_raw.calls == []
    connection.close()


def test_ac009_governed_first_routing_and_terminal_clarification(tmp_path: Path):
    config, snapshot, graph, index, mapping_report = _reader_inputs(tmp_path)
    fixture = _fixture_module()
    db_path = tmp_path / "ask.sqlite"
    fixture.build(db_path)
    connection = fixture.connect(db_path)
    raw_source = _SQLiteQuerySource(connection)
    source = adapt_query_source(raw_source, profile="fixture_db", dialect="sqlite")

    def forbidden_completer(_context):  # pragma: no cover - must not be called
        raise AssertionError("governed routes must not call composition")

    common = {
        "config": config, "index": index, "mapping_report": mapping_report,
        "snapshot": snapshot, "join_graph": graph, "source": source,
        "key_id": "fixture-key", "signing_key": SIGNING_KEY,
        "keys": {"fixture-key": SIGNING_KEY}, "now": NOW,
    }
    governed = ask(
        AskRequest(
            question="on loan value by counterparty today", as_of="2026-10-22",
            caller="lending-lead", profile="fixture_db",
        ),
        completer=forbidden_completer, **common,
    )
    assert governed.route == "governed_answer" and governed.tier == "governed"
    assert governed.answer and governed.answer.status == "answered"
    assert governed.governed_evidence
    assert f"run:{governed.governed_evidence.provenance.run_id}" in governed.citations
    assert [event.event for event in governed.trace] == ["governed_started", "governed_completed"]
    calls_after_governed = len(raw_source.calls)

    ambiguous = ask(
        AskRequest(
            question="on loan value and lending revenue today", as_of="2026-10-22",
            caller="lending-lead", profile="fixture_db",
        ),
        completer=forbidden_completer, **common,
    )
    assert ambiguous.route == "governed_clarification" and ambiguous.tier == "governed"
    assert ambiguous.answer and ambiguous.answer.status == "clarification_needed"
    assert len(raw_source.calls) == calls_after_governed
    assert [event.event for event in ambiguous.trace] == [
        "governed_started", "governed_clarification"]

    unavailable = ask(
        AskRequest(
            question="lendable value today", as_of="2026-10-22",
            caller="lending-lead", profile="fixture_db",
        ),
        completer=forbidden_completer, **common,
    )
    assert unavailable.route == "governed_unavailable" and unavailable.tier == "governed"
    assert unavailable.error_code == "E_METRIC_SOURCE_UNAVAILABLE"
    assert len(raw_source.calls) == calls_after_governed

    tail = ask(
        AskRequest(
            question="Collateral coverage ratio by loan", as_of="2026-10-22",
            caller="lending-lead", profile="fixture_db",
        ),
        **common,
    )
    assert tail.route == "no_governed_match" and tail.tier == "reuse"
    assert tail.answer is None and tail.composition and tail.execution
    assert tail.composition.query_id == "sl.collateral.coverage.by_loan"
    assert len(tail.execution.rows) == 4
    assert tail.execution.envelope()["run_id"] == tail.execution.provenance.run_id
    assert [event.event for event in tail.trace] == [
        "governed_started", "no_governed_match", "composed", "verified", "executed"]
    connection.close()


def test_ac010_tail_trace_repair_citations_and_envelope(tmp_path: Path):
    config, snapshot, graph, index, mapping_report = _reader_inputs(tmp_path)
    fixture = _fixture_module()
    db_path = tmp_path / "repair.sqlite"
    fixture.build(db_path)
    connection = fixture.connect(db_path)
    raw_source = _SQLiteQuerySource(connection)
    contexts = []

    def scripted(context):
        contexts.append(context)
        if context["attempt"] == 1:
            return {
                "sql": (
                    "SELECT br.security_id, br.fee_bps FROM borrow_rates br "
                    "WHERE br.business_date = :as_of AND br.borrow_category = 'HTB' LIMIT 10"
                ),
                "source_exemplar_ids": [],
                "limitations": ["First fixture candidate must fail verification."],
            }
        assert context["repair"] == {"stage": "verify", "code": "E_VERIFY_UNBOUND_PARAM"}
        return {
            "sql": (
                "SELECT br.security_id, AVG(br.fee_bps) AS avg_fee_bps FROM borrow_rates br "
                "WHERE br.business_date = :as_of GROUP BY br.security_id LIMIT 10"
            ),
            "source_exemplar_ids": [],
            "limitations": ["Synthetic shadow-mode aggregate."],
        }

    outcome = ask(
        AskRequest(
            question="zeta frobnicator report", as_of="2026-10-22",
            caller="lending-lead", profile="fixture_db",
            pit_columns=("borrow_rates.business_date",), max_repairs=1,
        ),
        config=config, index=index, mapping_report=mapping_report, snapshot=snapshot,
        join_graph=graph,
        source=adapt_query_source(raw_source, profile="fixture_db", dialect="sqlite"),
        key_id="fixture-key", signing_key=SIGNING_KEY,
        keys={"fixture-key": SIGNING_KEY}, now=NOW, completer=scripted,
    )
    assert outcome.route == "no_governed_match" and outcome.tier == "generate"
    assert len(contexts) == 2 and [context["attempt"] for context in contexts] == [1, 2]
    assert [event.event for event in outcome.trace] == [
        "governed_started", "no_governed_match", "composed", "verification_rejected",
        "repair_started", "composed", "verified", "executed",
    ]
    assert len(raw_source.calls) == 1
    assert "borrow_category = 'HTB'" not in raw_source.calls[0]["sql"]
    assert outcome.execution and len(outcome.execution.rows) == 3
    assert outcome.execution.envelope()["replay"]["expected_rows_hash"] == \
        outcome.execution.provenance.rows_hash
    assert any(citation.startswith("run:sfm-") for citation in outcome.citations)
    assert any("Shadow-mode" in caveat for caveat in outcome.caveats)
    rendered = json.dumps(outcome.as_dict(), sort_keys=True)
    assert SIGNING_KEY.decode() not in rendered and "fixture/sqlite-in-memory" not in rendered
    connection.close()


def test_ac011_writeback_always_refused_and_no_write_tool(tmp_path: Path):
    def enable_writeback(data):
        data["governed_tier"]["writeback"] = {
            "enabled": True, "target": {"name": "fixture-insights", "class": "analytics"}}

    config, _snapshot, _graph, _index, _mapping = _reader_inputs(
        tmp_path, mutate_config=enable_writeback)
    fixture = _fixture_module()
    db_path = tmp_path / "writeback.sqlite"
    fixture.build(db_path)
    connection = fixture.connect(db_path)
    raw_source = _SQLiteQuerySource(connection)
    context = ToolContext(
        config=config, today="2026-10-22", actor="lending-lead",
        clients={
            "query_sources": {"fixture_db": raw_source},
            "verification": {
                "key_id": "fixture-key", "signing_key": SIGNING_KEY,
                "keys": {"fixture-key": SIGNING_KEY}, "now": NOW,
            },
        },
    )
    registry = default_registry()
    assert config.data["governed_tier"]["writeback"]["enabled"] is True
    for action in ("publish", "persist", "submit", "reverse"):
        refused = registry.call("ask", {
            "question": "on loan value today", "as_of": "2026-10-22",
            "profile": "fixture_db", "action": action,
        }, context)
        assert not refused.ok and refused.error_code == "E_WRITEBACK_DISABLED"
        assert refused.error
    assert raw_source.calls == []
    assert "write" not in {registry.get(name).effect for name in registry.names()}
    assert not any("writeback" in name for name in registry.names())
    connection.close()


def test_ac012_shared_registry_schemas_effects_and_no_raw_execute(tmp_path: Path):
    config, _snapshot, _graph, _index, _mapping = _reader_inputs(tmp_path)
    fixture = _fixture_module()
    db_path = tmp_path / "tools.sqlite"
    fixture.build(db_path)
    connection = fixture.connect(db_path)
    raw_source = _SQLiteQuerySource(connection)
    context = ToolContext(
        config=config, today="2026-10-22", actor="lending-lead",
        clients={
            "query_sources": {"fixture_db": raw_source},
            "verification": {
                "key_id": "fixture-key", "signing_key": SIGNING_KEY,
                "keys": {"fixture-key": SIGNING_KEY}, "now": NOW,
            },
        },
    )
    registry = default_registry()
    assert {name: registry.get(name).effect for name in (
        "sql.compose", "sql.verify", "sql.execute", "ask")} == {
            "sql.compose": "read", "sql.verify": "read",
            "sql.execute": "execute_read", "ask": "execute_read",
        }
    execute_schema = registry.get("sql.execute").input_schema
    assert set(execute_schema["properties"]) == {"token", "params", "caller"}
    assert "sql" not in execute_schema["properties"]
    assert "writeback" not in registry.get("ask").input_schema["properties"]

    composed = registry.call("sql.compose", {
        "question": "Collateral coverage ratio by loan", "profile": "fixture_db",
        "as_of": "2026-10-22", "route_outcome": "no_governed_match",
    }, context)
    assert composed.ok and composed.output["path"] == "reuse"
    checked = registry.call("sql.verify", {
        "composition_id": composed.output["composition_id"],
    }, context)
    assert checked.ok and checked.output["ok"] is True
    token = checked.output["token"]
    ran = registry.call("sql.execute", {
        "token": token, "params": {"as_of": "2026-10-22"},
    }, context)
    assert ran.ok and len(ran.output["rows"]) == 4 and len(raw_source.calls) == 1
    governed = registry.call("ask", {
        "question": "on loan value by counterparty today", "as_of": "2026-10-22",
        "profile": "fixture_db",
    }, context)
    assert governed.ok and governed.output["route"] == "governed_answer"
    assert governed.output["tier"] == "governed" and len(raw_source.calls) == 2

    for tool_name, payload in (
        ("sql.verify", {"composition_id": composed.output["composition_id"], "sql": "SELECT 1"}),
        ("sql.execute", {"token": token, "params": {"as_of": "2026-10-22"}, "sql": "SELECT 1"}),
        ("ask", {"question": "x", "as_of": "2026-10-22", "profile": "fixture_db",
                 "writeback": {"enabled": True}}),
    ):
        rejected = registry.call(tool_name, payload, context)
        assert not rejected.ok and rejected.error_code == "E_TOOL_INPUT"
    assert len(raw_source.calls) == 2
    connection.close()


class _AgentScript:
    name = "scripted"

    def __init__(self, actions):
        self.actions = list(actions)

    def decide(self, _state):
        return self.actions.pop(0)


def test_ac013_sql_composer_loop_boundaries_and_verifiers(tmp_path: Path):
    config, _snapshot, _graph, _index, _mapping = _reader_inputs(tmp_path)
    context = ToolContext(
        config=config, today="2026-10-22", actor="lending-lead",
        clients={"verification": {
            "key_id": "fixture-key", "signing_key": SIGNING_KEY,
            "keys": {"fixture-key": SIGNING_KEY}, "now": NOW,
            "monotonic_ns": lambda: 0,
        }},
        agents_root=ROOT / "agents",
    )
    inputs = {
        "question": "Collateral coverage ratio by loan", "as_of": "2026-10-22",
        "profile": "fixture_db", "route_outcome": "no_governed_match",
    }
    registry = default_registry()
    run = run_composer(context, registry=registry, inputs=inputs)
    assert run.status == "completed", run.summary
    assert run.outputs["composition"]["path"] == "reuse"
    assert run.outputs["verification"]["ok"] is True
    assert run.outputs["verification"]["token"]
    called = [item["name"] for item in run.trace if item["event"] == "decide"]
    assert called == ["queries.search", "sql.compose", "queries.get", "sql.verify"]
    assert "sql.execute" not in called and "ask" not in called

    wrong_route = run_composer(context, registry=registry, inputs={**inputs, "route_outcome": "governed_answer"})
    assert wrong_route.status == "escalated" and wrong_route.tool_calls == 0

    denied = run_composer(
        context, registry=registry, inputs=inputs,
        policy=_AgentScript([ToolCall("sql.execute", {"token": "forged", "params": {}})]),
    )
    assert denied.status == "denied"
    human_only = run_composer(
        context, registry=registry, inputs=inputs,
        policy=_AgentScript([ToolCall("feedback.promote", {"candidate_id": "0" * 16})]),
    )
    assert human_only.status == "denied"

    forged = Finish("forged", {
        "route_outcome": "no_governed_match",
        "composition": {"path": "generate", "source_exemplars": [], "query_id": None},
        "verification": {"ok": True, "token": "forged", "query_id": None},
    })
    failed = run_composer(
        context, registry=registry, inputs=inputs,
        policy=_AgentScript([forged, forged]),
    )
    assert failed.status == "failed"
    assert any(item["event"] == "verify" and not item["ok"] for item in failed.trace)


def test_ac014_orchestrator_routes_repairs_escalates_and_replays(tmp_path: Path):
    config, _snapshot, _graph, _index, _mapping = _reader_inputs(tmp_path)
    fixture = _fixture_module()
    db_path = tmp_path / "orchestrator.sqlite"
    fixture.build(db_path)
    connection = fixture.connect(db_path)
    raw_source = _SQLiteQuerySource(connection)
    context = ToolContext(
        config=config, today="2026-10-22", actor="lending-lead",
        clients={
            "query_sources": {"fixture_db": raw_source},
            "verification": {
                "key_id": "fixture-key", "signing_key": SIGNING_KEY,
                "keys": {"fixture-key": SIGNING_KEY}, "now": NOW,
                "monotonic_ns": lambda: 0,
            },
        },
        agents_root=ROOT / "agents",
    )
    registry = default_registry()
    base = {"as_of": "2026-10-22", "caller": "lending-lead", "profile": "fixture_db"}

    governed_inputs = {**base, "question": "on loan value by counterparty today"}
    governed = run_orchestrator(context, registry=registry, inputs=governed_inputs)
    assert governed.status == "completed" and governed.outputs["route"] == "governed_answer"
    assert governed.outputs["tier"] == "governed"
    assert any(item.startswith("run:") for item in governed.outputs["citations"])

    replayed = run_orchestrator(context, registry=registry, inputs=governed_inputs)
    assert replayed.run_id == governed.run_id and replayed.trace == governed.trace

    ambiguous = run_orchestrator(context, registry=registry, inputs={
        **base, "question": "on loan value and lending revenue today"})
    assert ambiguous.status == "completed"
    assert ambiguous.outputs["route"] == "governed_clarification"
    assert not any(event.get("name") == "sql.compose" for event in ambiguous.trace)

    tail = run_orchestrator(context, registry=registry, inputs={
        **base, "question": "Collateral coverage ratio by loan"})
    assert tail.status == "completed" and tail.outputs["tier"] == "reuse"
    assert tail.outputs["execution"]["envelope"]["run_id"].startswith("sfm-")

    unavailable = run_orchestrator(context, registry=registry, inputs={
        **base, "question": "lendable value today"})
    assert unavailable.status == "escalated"
    assert unavailable.outputs["route"] == "governed_unavailable"

    refused = run_orchestrator(context, registry=registry, inputs={
        **base, "question": "on loan value today", "action": "publish"})
    assert refused.status == "completed"
    assert refused.outputs["route"] == "writeback_requested"
    assert refused.outputs["error_code"] == "E_WRITEBACK_DISABLED"
    connection.close()


def test_ac015_specialist_handoffs_are_bounded_and_redacted(tmp_path: Path):
    config, _snapshot, _graph, _index, _mapping = _reader_inputs(tmp_path)
    fixture = _fixture_module()
    db_path = tmp_path / "handoff.sqlite"
    fixture.build(db_path)
    connection = fixture.connect(db_path)
    raw_source = _SQLiteQuerySource(connection)
    context = ToolContext(
        config=config, today="2026-10-22", actor="lending-lead",
        clients={
            "query_sources": {"fixture_db": raw_source},
            "verification": {
                "key_id": "fixture-key", "signing_key": SIGNING_KEY,
                "keys": {"fixture-key": SIGNING_KEY}, "now": NOW,
                "monotonic_ns": lambda: 0,
            },
        },
        agents_root=ROOT / "agents",
    )
    run = run_orchestrator(context, registry=default_registry(), inputs={
        "question": "on loan value by counterparty today", "as_of": "2026-10-22",
        "caller": "lending-lead", "profile": "fixture_db",
    })
    assert run.status == "completed"
    catalog = json.loads((PLUGIN / "src/sfmeridian/data/handoffs.json").read_text())
    built = []
    for workflow in ("W7", "W8", "W9", "W10", "W11", "W12"):
        receiver = next(item for item in catalog["handoffs"] if workflow in item["workflows"])
        prompt = ROOT / "agents" / receiver["path"] / "prompt.md"
        before = prompt.read_bytes()
        handoff = prepare_handoff(
            run,
            workflow=workflow,
            receiver=receiver["agent"],
            request="Review the cited synthetic panel; password=hunter2 must not escape.",
            pit_basis="Every cited execution bound :as_of before the source read.",
        )
        payload = handoff.as_dict()
        assert validate_handoff(payload) == ()
        assert payload["receiver_path"] == receiver["path"]
        assert payload["requested_output"] == receiver["output"]
        assert payload["never"] == receiver["never"]
        assert payload["point_in_time"] == {
            "attested": True, "as_of": "2026-10-22",
            "basis": "Every cited execution bound :as_of before the source read.",
        }
        assert payload["redaction"]["withheld_columns_included"] is False
        assert payload["redaction"]["parameters_redacted"] is True
        assert "hunter2" not in json.dumps(payload) and "<redacted>" in payload["request"]
        assert {ref["role"] for ref in payload["evidence_references"]} == {"originating", "execution"}
        assert all(ref["schema_version"] == "quantsmith.orchestration.run.v1"
                   for ref in payload["evidence_references"])
        assert before == prompt.read_bytes()  # the builder never invokes or mutates the receiver
        built.append(payload["content_hash"])
    assert len(set(built)) == 6 and len(raw_source.calls) == 1

    forged = copy.deepcopy(payload)
    forged["receiver"] = "not_an_agent"
    forged["never"] = "may take actions"
    assert {problem for problem in validate_handoff(forged)
            if "receiver" in problem or "never" in problem}
    with pytest.raises(HandoffError) as err:
        prepare_handoff(
            run, workflow="W7", receiver="counterparty_credit_risk", request="solve",
            pit_basis="as-of bound",
        )
    assert err.value.code == "E_HANDOFF_RECEIVER"
    connection.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
