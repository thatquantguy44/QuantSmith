"""Acceptance tests for spec 0114 — SFMeridian query repository connector & indexer.

Each test names the acceptance criterion it proves. The plugin is a separate
distributable (``plugins/sfmeridian``); these tests put its ``src`` on the path.
No test touches the network: Git is exercised with local repositories.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "sfmeridian"
sys.path.insert(0, str(PLUGIN / "src"))

from sfmeridian import agent as agent_mod
from sfmeridian import cli, governance, yamlsubset
from sfmeridian.agent import (
    AgentManifest,
    Finish,
    ModelPolicy,
    ToolCall,
    load_manifest,
    run_agent,
)
from sfmeridian.config import (
    ConfigError,
    apply_call_overrides,
    load_config,
)
from sfmeridian.feedback import FeedbackError, Inbox
from sfmeridian.frontmatter import QueryRejected, parse_query
from sfmeridian.index import build_index, load_index, search
from sfmeridian.librarian import VERIFIERS, run_librarian
from sfmeridian.repos import RepoFetchError, fetch
from sfmeridian.sqlstructure import extract
from sfmeridian.tools import ToolContext, default_registry

TODAY = "2026-10-22"
FIXTURES = PLUGIN / "fixtures"


@pytest.fixture()
def workdir(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURES, tmp_path / "fx")
    return tmp_path / "fx"


def _config(workdir: Path, **changes):
    data = yamlsubset.parse((workdir / "sfmeridian.fixture.yml").read_text(), "fixture")
    data.update(changes)
    path = workdir / "sfmeridian.json"
    path.write_text(json.dumps(data))
    return load_config(path, env={})


def _ctx(config, actor="query-librarian"):
    return ToolContext(config, today=TODAY, actor=actor, agents_root=ROOT / "agents")


def _index(workdir: Path):
    config = _config(workdir)
    report = build_index(config)
    return config, report, config.resolve_path(config.data["index"]["dir"])


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# --------------------------------------------------------------------------
# AC-001 configuration
# --------------------------------------------------------------------------

def test_ac001_config_validation_codes_hash_and_overrides(workdir):
    """AC-001: each bad config fails with its code; hash stable; overrides only tighten."""
    base = yamlsubset.parse((workdir / "sfmeridian.fixture.yml").read_text(), "fixture")

    def codes(mutate):
        data = json.loads(json.dumps(base))
        mutate(data)
        with pytest.raises(ConfigError) as exc:
            load_config(data=data, env={})
        return {i.code for i in exc.value.issues}

    assert "E_CONFIG_MISSING" in codes(lambda d: d.pop("query_repositories"))
    assert "E_CONFIG_UNKNOWN_KEY" in codes(lambda d: d.update(surprise=1))
    assert "E_CONFIG_PLACEHOLDER" in codes(lambda d: d["query_repositories"][0].update(uri="<git-remote-url>"))
    assert "E_CONFIG_CREDENTIAL" in codes(lambda d: d["query_repositories"][0].update(
        kind="git", ref="main", uri="https://alice:hunter2@git.example/q.git"))  # qf:allow-secret (deliberate fake)
    assert "E_CONFIG_CREDENTIAL" in codes(lambda d: d["databases"][0]["connection"].update(password="x"))
    assert "E_CONFIG_INVALID" in codes(lambda d: d["databases"][0].update(read_only=False))
    assert "E_CONFIG_UNSUPPORTED" in codes(lambda d: d["databases"][0].update(dialect="snowflake"))
    assert "E_CONFIG_UNSUPPORTED" in codes(lambda d: d.update(retrieval={"mode": "lexical+embeddings"}))
    assert "E_CONFIG_WRITEBACK_TARGET" in codes(lambda d: d.update(governed_tier={
        "writeback": {"enabled": True, "target": {"name": "book", "class": "books_and_records"}}}))
    assert "E_CONFIG_MISSING" in codes(lambda d: d["query_repositories"][0].update(kind="git"))  # no ref
    assert "E_CONFIG_INVALID" in codes(lambda d: d["feedback"].update(promoters=["alice@example.com"]))

    first = load_config(data=base, env={})
    env = {"SFMERIDIAN__GROUNDING__RETRIEVAL_MIN_SCORE": "0.2", "SFMERIDIAN__RETRIEVAL__MODE": "lexical"}
    a = load_config(data=base, env=env)
    b = load_config(data=base, env=dict(reversed(list(env.items()))))
    assert a.hash == b.hash != first.hash and a.data["grounding"]["retrieval_min_score"] == 0.2
    assert load_config(data=base, env={}).hash == first.hash

    assert apply_call_overrides(first, {"row_limit": 100, "as_of": "2026-10-21"}) == {"row_limit": 100, "as_of": "2026-10-21"}
    for bad in ({"row_limit": 10 ** 9}, {"retrieval": "x"}, {"database_profile": "nope"}, {"as_of": "yesterday"}):
        with pytest.raises(ConfigError) as exc:
            apply_call_overrides(first, bad)
        assert {i.code for i in exc.value.issues} == {"E_CONFIG_OVERRIDE_DENIED"}

    # The template validates once placeholders are allowed, and only then.
    template = ROOT / "templates" / "sfmeridian" / "sfmeridian.yml"
    load_config(template, env={}, allow_placeholders=True)
    with pytest.raises(ConfigError):
        load_config(template, env={})


# --------------------------------------------------------------------------
# AC-002 YAML subset
# --------------------------------------------------------------------------

def test_ac002_yaml_subset_matches_pyyaml_and_rejects():
    """AC-002: template and fixture equal PyYAML's reading; unsupported constructs rejected with lines."""
    yaml = pytest.importorskip("yaml")
    for path in (ROOT / "templates/sfmeridian/sfmeridian.yml", FIXTURES / "sfmeridian.fixture.yml"):
        text = path.read_text()
        assert yamlsubset.parse(text, str(path)) == yaml.safe_load(text)
    for bad, line in (("a: 1\nb: &x 2", 2), ("a: !tag 1", 1), ("a: 1\na: 2", 2), ("a:\n\t- x", 2),
                      ("a: [1,\n  2]", 1), ("a: *ref", 1), ("---\na: 1", 1)):
        with pytest.raises(yamlsubset.YamlSubsetError) as exc:
            yamlsubset.parse(bad, "t")
        assert exc.value.line == line, bad
    assert yamlsubset.parse("k: >-\n  a\n  b\nl:\n- {x: [1, 'two']}\n- 3") == {"k": "a b", "l": [{"x": [1, "two"]}, 3]}


# --------------------------------------------------------------------------
# AC-003 repositories
# --------------------------------------------------------------------------

def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_ac003_local_and_git_repos_pinned_no_hardcoded_location(workdir, tmp_path):
    """AC-003: local + pinned git repos from config only; excludes skipped; escapes refused."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    (origin / "sql").mkdir()
    (origin / "sql/a.sql").write_text((workdir / "query_repo/lending/on_loan_value_by_counterparty.sql").read_text()
                                      .replace("sl.on_loan_value.by_counterparty.as_of", "team.on_loan_value"))
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "one")
    pinned = _git(origin, "rev-parse", "HEAD")
    (origin / "sql/b.sql").write_text((workdir / "query_repo/rates/specials_migration.sql").read_text()
                                      .replace("sl.rates.specials_migration", "team.specials"))
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "two")

    base = yamlsubset.parse((workdir / "sfmeridian.fixture.yml").read_text(), "fixture")
    base["query_repositories"].append({"id": "team_git", "kind": "git", "uri": str(origin), "ref": pinned,
                                       "paths": {"include": ["sql/**/*.sql"]}, "dialect": "sqlite",
                                       "database_profile": "fixture_db"})
    (workdir / "two.json").write_text(json.dumps(base))
    config = load_config(workdir / "two.json", env={})
    report = build_index(config)
    assert report.ok, report.errors
    exemplars = _jsonl(config.resolve_path(".sfmeridian/index") / "exemplars.jsonl")
    git_ex = [e for e in exemplars if e["repo_id"] == "team_git"]
    assert [e["path"] for e in git_ex] == ["sql/a.sql"] and git_ex[0]["ref"] == pinned
    local = [e for e in exemplars if e["repo_id"] == "fixture_queries"]
    assert local and all(e["ref"].startswith("local:") for e in local)
    assert not any("scratch/" in e["path"] for e in exemplars)

    outside = tmp_path / "outside.sql"
    outside.write_text("SELECT 1")
    (workdir / "query_repo" / "lending" / "escape.sql").symlink_to(outside)
    repo = config.repository("fixture_queries")
    with pytest.raises(RepoFetchError, match="escapes"):
        fetch(repo, base_dir=workdir, cache_dir=tmp_path / "cache")

    class Store:
        def list_objects(self, prefix):
            return [("bucket/q/x.sql", "v1"), ("bucket/q/../evil.sql", "v1")]

        def get_object(self, key):
            return b"SELECT 1"
    with pytest.raises(RepoFetchError, match="unsafe"):
        fetch({"id": "s3q", "kind": "object_store", "uri": "s3://bucket/q", "paths": {"include": ["**/*.sql"]},
               "dialect": "sqlite"}, base_dir=workdir, cache_dir=tmp_path, clients={"s3": Store()})
    with pytest.raises(RepoFetchError, match="no object-store client"):
        fetch({"id": "s3q", "kind": "object_store", "uri": "s3://bucket/q", "paths": {"include": ["**/*.sql"]},
               "dialect": "sqlite"}, base_dir=workdir, cache_dir=tmp_path)

    for path in (PLUGIN / "src").rglob("*.py"):
        text = path.read_text()
        assert "fixtures/" not in text and not re.search(r"\bquery_repo\b", text), path
        assert "github.com" not in text and "s3://" not in text.replace("``s3://", ""), path


# --------------------------------------------------------------------------
# AC-004 front-matter
# --------------------------------------------------------------------------

def test_ac004_front_matter_valid_malformed_unannotated(workdir):
    """AC-004: valid files carry fields; bad files rejected with reasons; un-annotated is unreviewed."""
    _, _, idx = _index(workdir)
    exemplars = {e["path"]: e for e in _jsonl(idx / "exemplars.jsonl")}
    rejected = {r["path"]: r for r in _jsonl(idx / "rejected.jsonl")}
    good = exemplars["lending/utilization_by_security.sql"]
    assert good["review_status"] == "reviewed" and good["query_id"] == "sl.utilization.by_security.as_of"
    assert [p["name"] for p in good["params"]] == ["as_of", "min_lendable"]
    assert good["pit_columns"] and good["owner"] == "desk-analytics" and good["viewpoint"] == "lender"
    assert exemplars["adhoc/top_fee_names.sql"]["review_status"] == "unreviewed"
    assert set(rejected) == {"broken/bad_yaml.sql", "broken/unclosed_front_matter.sql",
                             "broken/undeclared_param.sql", "broken/duplicate_id.sql"}
    assert "never closed" in rejected["broken/unclosed_front_matter.sql"]["reason"]
    assert "end_date" in rejected["broken/undeclared_param.sql"]["reason"]
    assert rejected["broken/duplicate_id.sql"]["code"] == "E_FRONTMATTER_DUPLICATE_ID"
    assert rejected["broken/bad_yaml.sql"]["line"] == 3

    reviewed_with_placeholder = (workdir / "query_repo/lending/utilization_by_security.sql").read_text().replace(
        "owner: desk-analytics", "owner: <owner-handle>")
    with pytest.raises(QueryRejected):
        parse_query(reviewed_with_placeholder, "t", dialect="sqlite")
    unknown_key = reviewed_with_placeholder.replace("owner: <owner-handle>", "owner: desk-analytics\n-- reveiwed: x")
    with pytest.raises(QueryRejected, match="unknown key"):
        parse_query(unknown_key, "t", dialect="sqlite")
    sidecar = parse_query("SELECT a FROM t WHERE d = :as_of", "t.sql", dialect="sqlite",
                          sidecar="id: t.q\ntitle: T\nintent: I\nreview_status: draft\n")
    assert sidecar.meta["id"] == "t.q" and sidecar.review_status == "draft"


# --------------------------------------------------------------------------
# AC-005 SQL structure
# --------------------------------------------------------------------------

def test_ac005_sql_structure_extraction():
    """AC-005: tables, joins, params, filters (redacted), metrics across dialect quoting."""
    s = extract("""-- comment with FROM fake_table
        WITH prior AS (SELECT security_id, borrow_category FROM borrow_rates WHERE business_date = :prior_date),
        curr AS (SELECT security_id, borrow_category, fee_bps FROM borrow_rates WHERE business_date = :as_of)
        SELECT c.security_id, AVG(c.fee_bps) AS avg_fee_bps /* note */, 'x' AS tag
        FROM curr c JOIN prior p ON p.security_id = c.security_id
        LEFT JOIN securities s USING (security_id)
        WHERE c.fee_bps >= 50 AND s.name LIKE 'A%' """)
    assert s["statement_count"] == 1 and s["statement_kind"] == "WITH" and s["read_only_shape"]
    assert s["ctes"] == ["prior", "curr"] and s["tables"] == ["borrow_rates", "securities"]
    assert s["params"] == ["prior_date", "as_of"] and s["param_style"] == "named_colon"
    filters = {(f["column"], f["op"], f["value"]) for f in s["filters"]}
    assert ("borrow_rates.business_date", "=", ":as_of") in filters
    assert ("borrow_rates.fee_bps", ">=", "<literal>") in filters
    assert ("securities.name", "LIKE", "<literal>") in filters
    assert {"left": "borrow_rates.security_id", "right": "securities.security_id", "join_types": ["left"]} in s["joins"]
    metric = next(i for i in s["select"] if i["name"] == "avg_fee_bps")
    assert metric["metric"] and metric["expression"] == "avg(borrow_rates.fee_bps)"
    assert "fake_table" not in s["tables"]

    pg = extract("SELECT SUM(b.qty) * 360 / NULLIF(SUM(i.lendable), 0) AS u FROM inv i JOIN book b ON b.id = i.id "
                 "WHERE i.d = %(as_of)s AND i.n BETWEEN 1 AND %(hi)s FETCH FIRST 5 ROWS ONLY", "postgres")
    assert pg["param_style"] == "pyformat" and pg["params"] == ["as_of", "hi"] and pg["has_row_limit"]
    assert pg["select"][0]["expression"] == "sum(book.qty) * 360 / nullif(sum(inv.lendable), 0)"
    assert {"column": "inv.n", "op": "BETWEEN", "value": "<literal>..%(hi)s"} in pg["filters"]

    db = extract("SELECT `t`.`a` FROM `cat`.`sch`.`t` WHERE `t`.`a` IN (:x, :y); DELETE FROM t", "databricks")
    assert db["tables"] == ["cat.sch.t"] and db["statement_count"] == 2 and not db["read_only_shape"]
    assert db["write_keywords"] == ["DELETE"]
    ora = extract('SELECT "BR"."FEE_BPS" FROM "BORROW_RATES" "BR" WHERE "BR"."D" = :as_of', "oracle")
    assert ora["tables"] == ["borrow_rates"] and ora["filters"][0]["column"] == "borrow_rates.d"
    assert extract("SELECT a FROM t WHERE x = ? AND y = $1")["param_style"] == "mixed"


# --------------------------------------------------------------------------
# AC-006 learned artifacts
# --------------------------------------------------------------------------

def test_ac006_learned_artifacts_cited_and_incremental(workdir):
    """AC-006: join graph, metric candidates (utilization conflict), filters; cited; second run writes nothing."""
    config, _, idx = _index(workdir)
    joins = {(j["left"], j["right"]): j for j in json.loads((idx / "join_graph.json").read_text())}
    assert ("counterparties.counterparty_id", "sec_lending_book.counterparty_id") in joins
    assert ("collateral.loan_id", "sec_lending_book.loan_id") in joins
    util = joins[("lendable_inventory.security_id", "sec_lending_book.security_id")]
    assert util["support"] == 1 and util["hint_support"] == 1 and util["join_types"] == ["inner", "left"]
    metrics = {m["name"]: m for m in json.loads((idx / "metric_candidates.json").read_text())}
    assert metrics["utilization"]["conflict"] and len(metrics["utilization"]["definitions"]) == 2
    assert not metrics["avg_fee_bps"]["conflict"]
    assert {"lending_revenue", "owner_revenue", "agent_revenue", "collateral_coverage"} <= set(metrics)
    filters = json.loads((idx / "filter_patterns.json").read_text())
    assert all(set(f["value_kinds"]) <= {"param", "literal", "null"} for f in filters)
    for e in _jsonl(idx / "exemplars.jsonl"):
        assert e["repo_id"] and e["ref"] and e["path"] and e["line_span"][0] <= e["line_span"][1]
    for name in ("exemplars.jsonl", "join_graph.json", "metric_candidates.json", "filter_patterns.json"):
        assert "password" not in (idx / name).read_text().lower()
    # Literal values appear nowhere in the derived artifacts.
    for name in ("join_graph.json", "metric_candidates.json", "filter_patterns.json"):
        assert "OPEN" not in (idx / name).read_text()
    second = build_index(config)
    assert second.written == [] and second.repositories[0]["reused"] == second.repositories[0]["files"]


# --------------------------------------------------------------------------
# AC-007 search
# --------------------------------------------------------------------------

def test_ac007_search_eligibility_ranking(workdir):
    """AC-007: reviewed first, hints flagged, deprecated/rejected never, scores in [0, 1)."""
    _, _, idx = _index(workdir)
    index = load_index(idx)
    hits = search(index, "utilization by security", limit=10)
    assert hits[0].exemplar["query_id"] == "sl.utilization.by_security.as_of" and not hits[0].hint
    assert all(0 <= h.score < 1 for h in hits)
    flags = [h.hint for h in hits]
    assert flags == sorted(flags)                          # primary before hints
    ids = {h.exemplar["query_id"] for h in hits}
    assert "sl.utilization.portfolio.draft" in ids         # draft served as a hint
    assert "sl.utilization.legacy" not in ids              # deprecated never
    assert not any(h.exemplar["path"].startswith("broken/") for h in hits)
    assert all(not h.hint for h in search(index, "utilization", include_hints=False))
    assert search(index, "utilization", min_score=0.99) == []
    assert [h.as_dict() for h in search(index, "fee")] == [h.as_dict() for h in search(index, "fee")]


# --------------------------------------------------------------------------
# AC-008 feedback
# --------------------------------------------------------------------------

def test_ac008_feedback_promotion_rules(workdir):
    """AC-008: staged candidates invisible; promotion refused for proposer/non-promoter/email; then served."""
    config, _, idx = _index(workdir)
    inbox = Inbox(config.resolve_path(config.data["feedback"]["inbox"]))
    payload = {"title": "Specials count by date", "intent": "Number of special names on a business date",
               "sql": "SELECT COUNT(*) AS specials_count FROM borrow_rates WHERE business_date = :as_of "
                      "AND borrow_category = 'SPECIAL'", "dialect": "sqlite", "profile": "fixture_db",
               "params": [{"name": "as_of", "type": "date"}], "tables": ["borrow_rates"],
               "pit_columns": ["borrow_rates.business_date"], "grain": "business_date", "tags": ["specials"]}
    record = inbox.propose(kind="exemplar", payload=payload, proposer="desk-analytics", proposed_on=TODAY)
    assert record["status"] == "staged"
    assert inbox.propose(kind="exemplar", payload=payload, proposer="desk-analytics", proposed_on=TODAY) == record
    build_index(config)
    assert not any(h.exemplar["provenance"] == "feedback" for h in search(load_index(idx), "specials count", limit=50))
    promoters = config.data["feedback"]["promoters"]
    for who, code in (("desk-analytics", "E_FEEDBACK_NOT_PROMOTER"), ("someone-else", "E_FEEDBACK_NOT_PROMOTER"),
                      ("lead@example.com", "E_FEEDBACK_HANDLE")):
        with pytest.raises(FeedbackError) as exc:
            inbox.promote(record["candidate_id"], promoter=who, promoters=promoters, promoted_on=TODAY)
        assert exc.value.code == code
    own = inbox.propose(kind="exemplar", payload={**payload, "title": "Mine"}, proposer="lending-lead",
                        proposed_on=TODAY)
    with pytest.raises(FeedbackError) as exc:
        inbox.promote(own["candidate_id"], promoter="lending-lead", promoters=promoters, promoted_on=TODAY)
    assert exc.value.code == "E_FEEDBACK_SELF_PROMOTION"
    inbox.promote(record["candidate_id"], promoter="lending-lead", promoters=promoters, promoted_on=TODAY)
    build_index(config)
    hit = search(load_index(idx), "specials count")[0]
    assert hit.exemplar["provenance"] == "feedback" and hit.exemplar["reviewed_by"] == "lending-lead"
    with pytest.raises(FeedbackError):
        inbox.discard(record["candidate_id"], by="lending-lead", reason="x", discarded_on=TODAY)


# --------------------------------------------------------------------------
# AC-009 governance catalogs
# --------------------------------------------------------------------------

def test_ac009_governance_catalogs_and_imports():
    """AC-009: coverage, handoffs, tooling, manifests valid; strict lists pending admissions; mutations fail."""
    report = governance.validate_all(ROOT / "agents", registry=default_registry())
    assert report["ok"], report["errors"]
    assert report["counts"] == {"coverage_rows": 10, "built_agents": 5, "handoffs": 37, "manifests": 5,
                                "tooling_entries": report["counts"]["tooling_entries"]}
    strict = governance.validate_all(ROOT / "agents", strict=True, registry=default_registry())
    assert not strict["ok"] and "statsmodels" in strict["pending_admissions"]

    coverage = governance.load("coverage.json")
    dup = json.loads(json.dumps(coverage))
    dup["rows"][1]["workflow"] = dup["rows"][0]["workflow"]
    errors: list = []
    governance._validate_coverage(dup, ROOT / "agents", errors)
    assert any("workflow duplicates" in e for e in errors)
    missing = json.loads(json.dumps(governance.load("handoffs.json")))
    missing["handoffs"][0]["path"] = "optimization/no_such_agent"
    errors = []
    governance._validate_handoffs(missing, ROOT / "agents", set(), errors)
    assert any("not found" in e for e in errors)
    clash = json.loads(json.dumps(coverage))
    clash["rows"][1]["agent"] = "securities_lending"
    errors = []
    governance._validate_coverage(clash, ROOT / "agents", errors)
    assert any("duplicates existing agent" in e for e in errors)
    assert governance.check_imports() == []


# --------------------------------------------------------------------------
# AC-010 agent catalog
# --------------------------------------------------------------------------

def test_ac010_query_librarian_catalogued():
    """AC-010: four files, Spec-Driven Role, catalog row, registry entry, exported skill."""
    agent_dir = ROOT / "agents/securities_financing/sfmeridian/query_librarian"
    for name in ("README.md", "prompt.md", "instructions.md", "tasks.md"):
        assert (agent_dir / name).exists()
    assert "## Spec-Driven Role" in (agent_dir / "instructions.md").read_text()
    assert "securities_financing/sfmeridian/query_librarian/" in (ROOT / "agents/README.md").read_text()
    assert "securities_financing/sfmeridian/query_librarian" in (ROOT / "agents/agent_registry.yaml").read_text()
    skills = json.loads((ROOT / ".claude/skills/registry.json").read_text())
    entries = skills["skills"] if isinstance(skills, dict) and "skills" in skills else skills
    entry = next(e for e in entries if e["agent"] == "securities_financing/sfmeridian/query_librarian")
    assert entry["status"] == "active"


# --------------------------------------------------------------------------
# AC-011 CLI
# --------------------------------------------------------------------------

def test_ac011_cli(workdir, capsys):
    """AC-011: CLI commands exit 0 with JSON; an invalid config exits non-zero with codes."""
    cfg = str(workdir / "sfmeridian.fixture.yml")
    base = ["--config", cfg, "--today", TODAY, "--agents-root", str(ROOT / "agents")]
    for argv in (["config", "validate"], ["index"], ["status"], ["search", "utilization"], ["tool", "list"],
                 ["governance", "validate"], ["agent", "run", "query_librarian", "--save"]):
        assert cli.main(base + argv) == 0, argv
        json.loads(capsys.readouterr().out)
    assert list((workdir / ".sfmeridian/index/runs").glob("*.json"))
    bad = workdir / "bad.yml"
    bad.write_text("schema_version: 1\nsurprise: true\n")
    assert cli.main(["--config", str(bad), "status"]) == 2
    assert "E_CONFIG" in capsys.readouterr().out


# --------------------------------------------------------------------------
# AC-012 / AC-013 portability and determinism
# --------------------------------------------------------------------------

def test_ac012_stdlib_only_imports():
    """AC-012: package code imports only the standard library."""
    assert governance.check_imports() == []
    pyproject = (PLUGIN / "pyproject.toml").read_text()
    assert "dependencies = []" in pyproject and 'requires-python = ">=3.11"' in pyproject


def test_ac013_determinism(workdir, tmp_path):
    """AC-013: two independent runs produce byte-identical artifacts and identical search results."""
    other = tmp_path / "again"
    shutil.copytree(FIXTURES, other)
    _, _, idx_a = _index(workdir)
    _, _, idx_b = _index(other)
    for name in ("exemplars.jsonl", "rejected.jsonl", "join_graph.json", "metric_candidates.json",
                 "filter_patterns.json"):
        assert (idx_a / name).read_bytes() == (idx_b / name).read_bytes(), name
    assert [h.as_dict() for h in search(load_index(idx_a), "revenue split")] == \
        [h.as_dict() for h in search(load_index(idx_b), "revenue split")]


# --------------------------------------------------------------------------
# AC-014 data safety
# --------------------------------------------------------------------------

def test_ac014_fixtures_disclosed_and_credential_free():
    """AC-014: the fixture disclosure is complete; fixtures carry no credential or data value."""
    disclosure = (FIXTURES / "README.md").read_text()
    for field in ("Location (section / chart / field)", "Why real data wasn't used", "Generation method",
                  "Reviewer / sign-off"):
        assert field in disclosure
    for path in (FIXTURES / "query_repo").rglob("*.sql"):
        text = path.read_text()
        assert "SYNTHETIC" in text, path
        assert "@" not in text and "password" not in text.lower(), path


# --------------------------------------------------------------------------
# AC-015 tool registry
# --------------------------------------------------------------------------

def test_ac015_tool_registry_shared_schema_and_human_only(workdir):
    """AC-015 (0113 AC-033): one registry; schema-checked inputs; human_only decisions."""
    config, _, _ = _index(workdir)
    reg = default_registry()
    ctx = _ctx(config)
    names = reg.names()
    assert {"repos.index", "queries.search", "feedback.promote", "governance.validate"} <= set(names)
    assert {t["name"] for t in reg.describe()} == set(names)
    assert reg.get("feedback.promote").effect == reg.get("feedback.discard").effect == "human_only"
    bad = reg.call("queries.search", {"query": 3}, ctx)
    assert not bad.ok and bad.error_code == "E_TOOL_INPUT"
    extra = reg.call("queries.search", {"query": "x", "surprise": 1}, ctx)
    assert extra.error_code == "E_TOOL_INPUT"
    assert reg.call("no.such", {}, ctx).error_code == "E_TOOL_UNKNOWN"
    assert reg.call("queries.search", {"query": "utilization"}, ctx).output["hits"]


# --------------------------------------------------------------------------
# AC-016 loop harness
# --------------------------------------------------------------------------

class Scripted:
    def __init__(self, actions, name="scripted"):
        self.actions = list(actions)
        self.name = name

    def decide(self, state):
        action = self.actions.pop(0)
        return action(state) if callable(action) else action


def _manifest(**over):
    data = load_manifest("query_librarian").as_dict()
    data.update(over)
    return AgentManifest.from_dict(data)


def test_ac016_harness_denies_budgets_repairs_and_replays(workdir):
    """AC-016 (0113 AC-032): denial, human_only refusal, budgets, policy errors, repair, model policy, replay."""
    config, _, _ = _index(workdir)
    reg = default_registry()
    ctx = _ctx(config)
    m = _manifest()
    run = run_agent(m, Scripted([ToolCall("feedback.discard", {"candidate_id": "0" * 16, "reason": "x"})]),
                    reg, ctx, verifiers=VERIFIERS)
    assert run.status == "denied"
    granted = _manifest(tools=m.tools + ("feedback.promote",))
    run = run_agent(granted, Scripted([ToolCall("feedback.promote", {"candidate_id": "0" * 16})]), reg, ctx,
                    verifiers=VERIFIERS)
    assert run.status == "denied" and "reserved for a person" in run.summary
    loop = Scripted([ToolCall("repos.status")] * 50)
    assert run_agent(_manifest(max_steps=5), loop, reg, ctx, verifiers=VERIFIERS).status == "budget_exhausted"

    def boom(state):
        raise RuntimeError("bug")
    assert run_agent(m, Scripted([boom]), reg, ctx, verifiers=VERIFIERS).status == "failed"

    uncited = Finish("report", {"findings": [{"id": "F-001", "evidence": [{"type": "rejected", "ref": "nope"}]}]})
    repaired = Scripted([ToolCall("index.rejections"), uncited, lambda state: Finish("ok", _cited_report(state))])
    run = run_agent(m, repaired, reg, ctx, verifiers=VERIFIERS)
    assert run.status == "completed"
    assert any(t["event"] == "verify" and not t["ok"] for t in run.trace)
    never = Scripted([ToolCall("index.rejections"), uncited, uncited, uncited])
    assert run_agent(m, never, reg, ctx, verifiers=VERIFIERS).status == "failed"

    answers = iter(['not json', '{"action": "tool", "name": "repos.status", "args": {}}',
                    '{"action": "escalate", "reason": "need a person"}'])
    model = ModelPolicy(lambda prompt: next(answers), reg)
    run = run_agent(m, model, reg, ctx, verifiers=VERIFIERS)
    assert run.status == "escalated" and run.tool_calls == 1
    garbage = ModelPolicy(lambda prompt: "nope", reg)
    assert run_agent(m, garbage, reg, ctx, verifiers=VERIFIERS).status == "escalated"
    assert "repos.index" in model.prompt(agent_mod.LoopState(m, {}))

    a = run_librarian(ctx, registry=reg)
    b = run_librarian(ctx, registry=reg)
    assert a.run_id == b.run_id and a.trace == b.trace and a.envelope()["audit_events"]


def _cited_report(state):
    obs = state.last("index.rejections")
    return {"findings": [{"id": f"F-{i:03d}", "evidence": [{"type": "rejected", "ref": f"{r['repo_id']}:{r['path']}"}]}
                         for i, r in enumerate(obs.output["rejected"], 1)], "suggested_front_matter": []}


# --------------------------------------------------------------------------
# AC-017 query_librarian loop
# --------------------------------------------------------------------------

def test_ac017_query_librarian_loop(workdir):
    """AC-017: completes with cited findings for rejections, the utilization conflict, the unannotated file."""
    config = _config(workdir)
    run = run_librarian(_ctx(config))
    assert run.status == "completed", run.summary
    kinds = [f["kind"] for f in run.outputs["findings"]]
    assert kinds.count("rejected_file") == 4 and "metric_conflict" in kinds and "unannotated" in kinds
    conflict = next(f for f in run.outputs["findings"] if f["kind"] == "metric_conflict")
    assert "'utilization'" in conflict["message"]
    assert all(s["draft"]["review_status"] == "draft" for s in run.outputs["suggested_front_matter"])
    assert [t["name"] for t in run.trace if t["event"] == "observe"] == [
        "config.validate", "repos.index", "repos.status", "index.rejections", "index.findings", "index.metrics",
        "feedback.list"]

    broken = yamlsubset.parse((workdir / "sfmeridian.fixture.yml").read_text(), "f")
    broken["query_repositories"][0]["uri"] = "missing_dir"
    (workdir / "broken.json").write_text(json.dumps(broken))
    run = run_librarian(_ctx(load_config(workdir / "broken.json", env={})))
    assert run.status == "escalated" and "fetch" in run.summary
    assert any(f["kind"] == "repository_unreachable" for f in run.outputs["findings"])
