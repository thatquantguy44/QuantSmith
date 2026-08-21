"""Acceptance tests for spec 0057 -- knowledge console.

Each test is named for the acceptance criterion it covers (see
``specs/0057-knowledge-console/tasks.md``). Standard library + pytest only; no
Node toolchain is required to run this suite.
"""

from __future__ import annotations

import datetime
import http.client
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from quantsmith.knowledge_console import model as m
from quantsmith.knowledge_console import query as q
from quantsmith.knowledge_console import server as s

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY = str(REPO_ROOT / "memory")
WEB_SRC = REPO_ROOT / "web" / "src"

# A fixed as-of well after the seed records so freshness signals are exercised
# deterministically regardless of the wall clock.
AS_OF = datetime.date(2027, 6, 1)


# --- AC-001: load tags each record with its workflow and source file ---------

def test_load_store_tags_workflow_and_source_AC_001():
    store = m.load_store(MEMORY)
    ids = {lr.record.id: lr for lr in store.records}
    # A shared provenance record and a workflow index record both loaded.
    assert "MEM-0001" in ids and "MEM-QR-0001" in ids
    assert ids["MEM-0001"].workflow == "_shared"
    assert ids["MEM-QR-0001"].workflow == "quant_researcher"
    for lr in store.records:
        assert lr.record.source_file  # provenance preserved (spec REQ-013)


# --- AC-002: the model is byte-identical when rebuilt with the same inputs ----

def test_model_is_byte_identical_AC_002():
    store = m.load_store(MEMORY)
    a = m.model_json(m.build_model(store, as_of=AS_OF, changes=[], generated_at=None))
    b = m.model_json(m.build_model(store, as_of=AS_OF, changes=[], generated_at=None))
    assert a == b


# --- AC-003: counts partition the record set ----------------------------------

def test_counts_sum_to_total_AC_003():
    store = m.load_store(MEMORY)
    counts = m.build_model(store, as_of=AS_OF)["counts"]
    total = counts["total"]
    for key in ("by_type", "by_status", "by_confidence", "by_access_level", "by_workflow"):
        assert sum(counts[key].values()) == total, key


# --- AC-004: cumulative trend is monotone and ends at the total ---------------

def test_cumulative_trend_monotone_ends_at_total_AC_004():
    store = m.load_store(MEMORY)
    model = m.build_model(store, as_of=AS_OF)
    series = model["trends"]["cumulative_by_date"]
    values = [pt["count"] for pt in series]
    assert values == sorted(values)  # non-decreasing
    assert values[-1] == model["counts"]["total"]


# --- AC-005: staleness split respects freshness_days --------------------------

def test_staleness_split_at_freshness_AC_005():
    store = m.load_store(MEMORY)  # freshness_days == 90
    # 200 days before as_of -> overdue; 30 days before -> fresh.
    old = m.build_model(store, as_of=AS_OF)["trends"]["staleness"]
    assert old["overdue"] >= 1  # seed records predate AS_OF by >90 days
    near = datetime.date(2026, 8, 1)  # within 90 days of the latest seed record
    fresh_split = m.build_model(store, as_of=near)["trends"]["staleness"]
    assert fresh_split["fresh"] >= 1


# --- AC-006: graph links each record to its workflow and scope ----------------

def test_graph_edges_record_to_workflow_and_scope_AC_006():
    store = m.load_store(MEMORY)
    graph = m.build_graph(store)
    node_ids = {n["id"] for n in graph["nodes"]}
    edges = {(e["source"], e["target"], e["kind"]) for e in graph["edges"]}
    for lr in store.records:
        rec_id = f"rec:{lr.record.id}"
        assert (rec_id, f"wf:{lr.workflow}", "in_workflow") in edges
        assert (rec_id, f"scope:{lr.record.scope}", "about") in edges
    # An evidence-run node exists for each distinct source_run.
    runs = {f"run:{e['source_run']}"
            for lr in store.records for e in lr.record.evidence if "source_run" in e}
    assert runs <= node_ids


# --- AC-007: changes feed is real with git, empty without --------------------

def test_changes_feed_real_and_empty_AC_007(tmp_path):
    real = m.git_changes(MEMORY)
    assert isinstance(real, list) and real, "expected non-empty git history over memory/"
    assert {"hash", "author", "date", "subject", "files"} <= set(real[0])
    # No email addresses leak into the feed (memory gate forbids them).
    for change in real:
        assert "@" not in change["author"]
    # A directory with no git history degrades to an empty feed, no error.
    empty_root = tmp_path / "memory"
    empty_root.mkdir()
    assert m.git_changes(str(empty_root)) == []


# --- AC-008: review queue names the reason a record needs review --------------

def test_review_queue_reasons_AC_008():
    store = m.load_store(MEMORY)
    queue = m.build_model(store, as_of=AS_OF)["review_queue"]
    by_id = {item["record_id"]: item for item in queue}
    # MEM-0001 declares corroboration_count 4 on one evidence entry.
    assert "MEM-0001" in by_id
    kinds = {r["kind"] for r in by_id["MEM-0001"]["reasons"]}
    assert "unsupported_confidence" in kinds
    # As of a date >90 days after the latest record, freshness fires too.
    assert "freshness" in kinds


# --- AC-009: /api/model and /api/health ---------------------------------------

@pytest.fixture()
def running_server():
    httpd = s.make_server(MEMORY, None, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, body


def _post(port, path, payload):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", path, body=json.dumps(payload),
                 headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, body


def test_api_model_and_health_AC_009(running_server):
    port = running_server
    status, body = _get(port, "/api/health")
    assert status == 200
    status, body = _get(port, "/api/model")
    assert status == 200
    model = json.loads(body)
    assert model["counts"]["total"] == len(m.load_store(MEMORY).records)


# --- AC-010: query grounds an answer in the vintage record -------------------

def test_query_cites_vintage_record_AC_010(running_server):
    status, body = _post(running_server, "/api/query",
                         {"question": "why not use adjusted close"})
    assert status == 200
    ans = json.loads(body)
    assert "MEM-0002" in ans["citations"]
    assert ans["mode"] == "keyword"
    assert ans["matched"] is True


# --- AC-011: a no-match question invents nothing ------------------------------

def test_query_no_match_empty_citations_AC_011(running_server):
    status, body = _post(running_server, "/api/query",
                         {"question": "xyzzy plugh quantum banana"})
    assert status == 200
    ans = json.loads(body)
    assert ans["citations"] == []
    assert ans["matched"] is False


# --- AC-012: the default engine is the keyword engine -------------------------

def test_default_engine_is_keyword_AC_012():
    q.register_engine(None)  # ensure clean state
    engine = q.resolve_engine()
    assert engine.name == "keyword"


# --- AC-013: the front end prefers the embedded model over the network --------

def test_frontend_prefers_embedded_model_AC_013():
    api_ts = (WEB_SRC / "lib" / "api.ts").read_text(encoding="utf-8")
    assert "__KB_MODEL__" in api_ts
    # The embedded check must appear before the network fetch in the source.
    assert api_ts.index("__KB_MODEL__") < api_ts.index("/api/model")


# --- AC-014: unknown path 404s and traversal is blocked ----------------------

def test_unknown_path_404_and_traversal_guard_AC_014(running_server):
    port = running_server
    status, _ = _get(port, "/nope")
    assert status == 404
    status, _ = _get(port, "/api/does-not-exist")
    assert status == 404
    status, _ = _get(port, "/../../../etc/passwd")
    assert status == 404


# --- CLI bridge: `print` and `query` subcommands (used by the terminal app) ---

def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "quantsmith.knowledge_console", *args],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": __import__("os").environ.get("PATH", "")},
    )


def test_cli_print_emits_model_json():
    r = _cli("print", "--root", MEMORY)
    assert r.returncode == 0, r.stderr
    model = json.loads(r.stdout)
    assert model["counts"]["total"] == len(m.load_store(MEMORY).records)


def test_cli_query_emits_grounded_answer():
    r = _cli("query", "--root", MEMORY, "--question", "why not use adjusted close")
    assert r.returncode == 0, r.stderr
    ans = json.loads(r.stdout)
    assert "MEM-0002" in ans["citations"]
    assert ans["mode"] == "keyword" and ans["matched"] is True


# --- AC-015: an empty/missing store yields a well-formed empty model ----------

def test_empty_store_yields_empty_model_AC_015(tmp_path):
    missing = tmp_path / "nonexistent-memory"
    store = m.load_store(str(missing))
    model = m.build_model(store, as_of=AS_OF, changes=[])
    assert model["counts"]["total"] == 0
    assert model["records"] == []
    assert model["trends"]["cumulative_by_date"] == []
    assert model["graph"]["nodes"] == []
    assert model["review_queue"] == []
    assert model["changes"] == []
