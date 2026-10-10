"""Reference runtime for spec 0112 — dbt project review from ``manifest.json``.

dbt compiles a project into ``target/manifest.json``. This module reads that
artifact (no dbt install, no warehouse) and reports the defects that make a dbt
project unsafe for quant work:

* **Ownership** — a model with no owner (``meta.owner`` or a ``group``).
* **Primary keys** — a model without a ``unique`` and a ``not_null`` test on one
  column, or a ``unique_combination_of_columns`` test.
* **Contracts** — a public or mart model without an enforced contract.
* **Incremental safety** — an incremental model without a ``unique_key`` (duplicates
  on re-run or backfill), without an ``is_incremental()`` filter, or with
  ``on_schema_change`` left at ``ignore`` (new columns silently dropped).
* **Reproducibility** — a model whose SQL reads the wall clock
  (``current_date``, ``current_timestamp``, ``now()``, ``getdate()``,
  ``sysdate``), so its result depends on when it ran.
* **Source freshness** — a source with no ``loaded_at_field`` or no
  ``warn_after``/``error_after`` freshness.
* **Snapshots** — a snapshot without a ``unique_key`` or ``strategy``, or a
  ``timestamp`` snapshot without ``updated_at``.

Field names follow dbt's manifest (v10+, dbt 1.5+). Fields absent in older
manifests are treated as absent, which can only add findings, never hide one.

Guarantees held by construction:

* REQ-003 / AC-003 — every model, source, and snapshot node is checked against
  every rule; findings are sorted and carry the node id, rule, and severity.
* REQ-004 / AC-004 — tests are matched to models through ``attached_node``
  (falling back to ``depends_on``), so a test on another model never counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

WALL_CLOCK = re.compile(
    r"\b(current_date|current_timestamp|getdate\s*\(|sysdate|now\s*\(\s*\)|"
    r"localtimestamp|systimestamp|today\s*\(\s*\))",
    re.IGNORECASE,
)
PK_COMBO_TESTS = ("unique_combination_of_columns",)


@dataclass(frozen=True)
class Finding:
    node: str
    rule: str
    severity: str  # error | warn
    message: str


def _get(d: Any, *path: str, default: Any = None) -> Any:
    for p in path:
        if not isinstance(d, Mapping) or p not in d:
            return default
        d = d[p]
    return d


def _owner(node: Mapping[str, Any]) -> Optional[str]:
    return (_get(node, "meta", "owner") or _get(node, "config", "meta", "owner")
            or node.get("group") or _get(node, "config", "group"))


def _tests_by_model(nodes: Mapping[str, Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    out: Dict[str, List[Mapping[str, Any]]] = {}
    for node in nodes.values():
        if node.get("resource_type") != "test":
            continue
        target = node.get("attached_node")
        if not target:
            deps = [d for d in _get(node, "depends_on", "nodes", default=[]) or []
                    if d.startswith(("model.", "snapshot.", "seed."))]
            target = deps[0] if len(deps) == 1 else None
        if target:
            out.setdefault(target, []).append(node)
    return out


def _has_primary_key(tests: Sequence[Mapping[str, Any]]) -> bool:
    unique: Set[str] = set()
    not_null: Set[str] = set()
    for t in tests:
        name = _get(t, "test_metadata", "name")
        col = _get(t, "test_metadata", "kwargs", "column_name") or t.get("column_name")
        if name in PK_COMBO_TESTS:
            return True
        if name == "unique" and col:
            unique.add(str(col).lower())
        elif name == "not_null" and col:
            not_null.add(str(col).lower())
    return bool(unique & not_null)


def _is_mart(node: Mapping[str, Any], mart_dirs: Sequence[str]) -> bool:
    if _get(node, "config", "access") == "public" or node.get("access") == "public":
        return True
    fqn = [str(p).lower() for p in node.get("fqn", [])]
    path = str(node.get("path", "")).lower().replace("\\", "/")
    return any(d in fqn or path.startswith(f"{d}/") for d in mart_dirs)


def review_manifest(manifest: Mapping[str, Any],
                    mart_dirs: Sequence[str] = ("marts",)) -> List[Finding]:
    """Review a parsed ``manifest.json``; returns findings sorted by node and rule."""
    nodes: Mapping[str, Mapping[str, Any]] = manifest.get("nodes", {}) or {}
    sources: Mapping[str, Mapping[str, Any]] = manifest.get("sources", {}) or {}
    tests = _tests_by_model(nodes)
    out: List[Finding] = []

    for nid, node in nodes.items():
        kind = node.get("resource_type")
        if kind == "model":
            out += _review_model(nid, node, tests.get(nid, []), mart_dirs)
        elif kind == "snapshot":
            out += _review_snapshot(nid, node)

    for sid, src in sources.items():
        if not src.get("loaded_at_field") and not _get(src, "config", "loaded_at_field"):
            out.append(Finding(sid, "source_freshness", "warn",
                               "no loaded_at_field: freshness cannot be checked"))
        fresh = src.get("freshness") or {}
        has = any(_get(fresh, k, "count") for k in ("warn_after", "error_after"))
        if not has:
            out.append(Finding(sid, "source_freshness", "warn",
                               "no warn_after/error_after freshness threshold"))
    return sorted(out, key=lambda f: (f.node, f.rule, f.message))


def _review_model(nid: str, node: Mapping[str, Any], tests: Sequence[Mapping[str, Any]],
                  mart_dirs: Sequence[str]) -> List[Finding]:
    out: List[Finding] = []
    cfg = node.get("config", {}) or {}
    if not _owner(node):
        out.append(Finding(nid, "ownership", "warn", "no owner (meta.owner or group)"))
    if not _has_primary_key(tests):
        out.append(Finding(nid, "primary_key", "error",
                           "no unique + not_null test on one column "
                           "(or unique_combination_of_columns)"))
    if _is_mart(node, mart_dirs) and not _get(cfg, "contract", "enforced"):
        out.append(Finding(nid, "contract", "error",
                           "public/mart model without an enforced contract"))
    if cfg.get("materialized") == "incremental":
        code = str(node.get("raw_code") or node.get("raw_sql") or "")
        if not cfg.get("unique_key"):
            out.append(Finding(nid, "incremental_unique_key", "error",
                               "incremental model without unique_key: re-runs and "
                               "backfills can duplicate rows"))
        if "is_incremental()" not in code.replace(" ", ""):
            out.append(Finding(nid, "incremental_filter", "warn",
                               "incremental model without an is_incremental() filter"))
        if (cfg.get("on_schema_change") or "ignore") == "ignore":
            out.append(Finding(nid, "incremental_schema_change", "warn",
                               "on_schema_change is 'ignore': new upstream columns are "
                               "silently dropped (use 'fail' or 'append_new_columns')"))
    code = str(node.get("raw_code") or node.get("raw_sql") or "")
    hits = sorted({m.group(1).lower().rstrip("( ") for m in WALL_CLOCK.finditer(code)})
    if hits:
        out.append(Finding(nid, "wall_clock", "warn",
                           f"reads the wall clock ({', '.join(hits)}): output depends on "
                           "run time; pass the as-of date as a var"))
    return out


def _review_snapshot(nid: str, node: Mapping[str, Any]) -> List[Finding]:
    cfg = node.get("config", {}) or {}
    out: List[Finding] = []
    if not cfg.get("unique_key"):
        out.append(Finding(nid, "snapshot", "error", "snapshot without unique_key"))
    strategy = cfg.get("strategy")
    if strategy not in ("timestamp", "check"):
        out.append(Finding(nid, "snapshot", "error", "snapshot without a timestamp/check strategy"))
    elif strategy == "timestamp" and not cfg.get("updated_at"):
        out.append(Finding(nid, "snapshot", "error",
                           "timestamp snapshot without updated_at"))
    return out


def summarize(findings: Sequence[Finding]) -> Tuple[int, int]:
    """(errors, warnings)."""
    errors = sum(1 for f in findings if f.severity == "error")
    return errors, len(findings) - errors
