"""Acceptance tests for spec 0116 — governed SQL composition and execution.

The initial slice covers AC-001: the deterministic, fully synthetic executable
SQLite fixture on which the verifier, executor, Reader, and ``ask`` tests build.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "sfmeridian"
FIXTURES = PLUGIN / "fixtures"
EXECUTION = FIXTURES / "execution"
sys.path.insert(0, str(PLUGIN / "src"))

from sfmeridian.frontmatter import split_front_matter


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
    assert "execution/fixture_db.py" in disclosure and "execution/expected_results.json" in disclosure
    assert "SYNTHETIC" in (EXECUTION / "fixture_db.py").read_text()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
