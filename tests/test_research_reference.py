"""Tests for the Market Research reference store reader.

Covers ``src/quantsmith/knowledge_console/research.py``, which backs the
Research view in ``apps/knowledge-console`` (the terminal). This module is a
reference/example implementation of the target schema in
``specs/0056-market-research-knowledge-base/`` (status: Draft) — it does not
implement that spec's requirements (no MCP interface, no entitlement
enforcement, no email connector); these tests verify the reader itself, not
0056's acceptance criteria.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from quantsmith.knowledge_console import research as r

REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH = str(REPO_ROOT / "research")

AS_OF = datetime.date(2026, 8, 21)


def test_load_research_store_reads_the_committed_reference_items():
    store = r.load_research_store(RESEARCH)
    ids = {it.id for it in store.items}
    assert {"RES-0001", "RES-0002", "RES-0003", "RES-0008"} <= ids
    for it in store.items:
        assert it.source_type in r.SOURCE_TYPES
        assert it.access_level in r.ACCESS_LEVELS
        assert it.review_status in r.REVIEW_STATUSES
        assert it.source_file  # provenance preserved


def test_quarantined_items_are_flagged_hidden_by_default():
    store = r.load_research_store(RESEARCH)
    by_id = {it.id: it for it in store.items}
    model = r.build_research_model(store, as_of=AS_OF)
    views = {v["id"]: v for v in model["items"]}
    assert by_id["RES-0008"].review_status == "quarantined"
    assert views["RES-0008"]["hidden_by_default"] is True
    assert views["RES-0001"]["hidden_by_default"] is False
    assert model["counts"]["hidden"] == 1
    assert model["counts"]["visible"] == model["counts"]["total"] - 1


def test_counts_partition_the_item_set():
    store = r.load_research_store(RESEARCH)
    model = r.build_research_model(store, as_of=AS_OF)
    counts = model["counts"]
    for key in ("by_source_type", "by_asset_class", "by_access_level", "by_review_status"):
        assert sum(counts[key].values()) == counts["total"]


def test_superseded_item_names_its_replacement():
    store = r.load_research_store(RESEARCH)
    by_id = {it.id: it for it in store.items}
    assert by_id["RES-0007"].review_status == "superseded"
    assert by_id["RES-0007"].superseded_by == "RES-0001"


def test_model_is_deterministic():
    store = r.load_research_store(RESEARCH)
    a = r.build_research_model(store, as_of=AS_OF, generated_at=None)
    b = r.build_research_model(store, as_of=AS_OF, generated_at=None)
    assert a == b


def test_disclaimer_names_spec_0056_as_draft_and_not_implemented():
    store = r.load_research_store(RESEARCH)
    model = r.build_research_model(store, as_of=AS_OF)
    assert "0056" in model["disclaimer"]
    assert "Draft" in model["disclaimer"]


def test_missing_root_yields_empty_store_not_an_error(tmp_path):
    store = r.load_research_store(str(tmp_path / "no-such-dir"))
    assert store.items == ()
    model = r.build_research_model(store, as_of=AS_OF)
    assert model["counts"]["total"] == 0
    assert model["items"] == []


def test_restricted_items_carry_an_entitlement_class():
    store = r.load_research_store(RESEARCH)
    restricted = [it for it in store.items if it.access_level == "restricted"]
    assert restricted, "expected at least one restricted reference item"
    for it in restricted:
        assert it.entitlement_class


def test_cli_research_subcommand_emits_model_json():
    import json
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "quantsmith.knowledge_console", "research", "--root", RESEARCH],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert proc.returncode == 0, proc.stderr
    model = json.loads(proc.stdout)
    store = r.load_research_store(RESEARCH)
    assert model["counts"]["total"] == len(store.items)
