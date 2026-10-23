"""Acceptance tests for spec 0116 — governed SQL composition and execution.

The initial slice covers AC-001: the deterministic, fully synthetic executable
SQLite fixture on which the verifier, executor, Reader, and ``ask`` tests build.
"""

from __future__ import annotations

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

from sfmeridian.catalog import load_declared
from sfmeridian.config import ConfigError, apply_call_overrides, load_config, read_file
from sfmeridian.frontmatter import split_front_matter
from sfmeridian.index import build_index
from sfmeridian.verify import (
    TokenError,
    VerificationRequest,
    trusted_predicate_literals,
    validate_token,
    verify,
)

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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
