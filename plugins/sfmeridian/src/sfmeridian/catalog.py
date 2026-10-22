"""Schema catalog snapshots, diffs, and drift reconciliation.

Spec ``0115`` REQ-001–REQ-004 (realizing ``0113`` REQ-007, RISK-001, RISK-004).

A *snapshot* is the list of tables and views a database profile exposes —
schema, name, kind, columns (name, type, nullability, comment), primary key,
and row-count estimate when the source has one — taken either by read-only
introspection through an injected connection or from a declared catalog file.
Snapshots are content-addressed: the ID hashes the profile, dialect, and
tables, never the date, so an unchanged catalog writes nothing and two
introspections of the same schema agree. Each profile keeps
``<index dir>/catalog/<profile>/<snapshot id>.json`` and a dated
``history.json``.

Introspection runs fixed, plugin-owned ``SELECT`` statements against the
dialect's own dictionary (SQLite ``sqlite_master``/``pragma_table_info``,
PostgreSQL and Databricks ``information_schema``, Oracle ``ALL_TAB_COLUMNS``
and ``ALL_OBJECTS``); nothing a caller supplies is interpolated into SQL, and
schema/table allowlists are applied to the result. Identifiers are matched
case-insensitively (Oracle reports upper case).

*Reconciliation* compares the latest snapshot with every indexed exemplar of
the profile. An exemplar that references a table or column the snapshot does
not have has drifted: with ``drift_policy: exclude`` (the default) it is
written to ``<index dir>/drift.json`` and :func:`sfmeridian.index.load_index`
drops it from retrieval until the catalog or the query changes and a
reconcile clears it; with ``warn`` it stays searchable and is reported.
Breaking changes between snapshots (removed tables or columns, retypes,
relaxed nullability) are handed to ``schema_evolution``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import yamlsubset

__all__ = [
    "DEFAULT_SCHEMA", "INTROSPECTION_SQL", "CatalogError", "Resolved", "Resolver", "connect", "diff",
    "excluded_exemplars", "exemplar_references", "history", "introspect", "load_declared", "load_snapshot",
    "reconcile", "snapshot_profile", "store", "write_drift",
]

SNAPSHOT_SCHEMA = 1
DEFAULT_SCHEMA = {"sqlite": "main", "postgres": "public", "oracle": None, "databricks": "default"}

#: Fixed dictionary queries per dialect: (columns query, primary-key query).
#: Columns rows: schema, table, kind, column, type, nullable, position.
INTROSPECTION_SQL: dict[str, tuple[str, str | None]] = {
    "postgres": (
        ("SELECT c.table_schema, c.table_name, t.table_type, c.column_name, c.data_type, c.is_nullable, "
        "c.ordinal_position FROM information_schema.columns c JOIN information_schema.tables t "
        "ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
        "WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY 1, 2, 7"),
        ("SELECT kcu.table_schema, kcu.table_name, kcu.column_name FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name "
        "AND kcu.table_schema = tc.table_schema AND kcu.table_name = tc.table_name "
        "WHERE tc.constraint_type = 'PRIMARY KEY' ORDER BY 1, 2, kcu.ordinal_position"),
    ),
    "databricks": (
        ("SELECT c.table_schema, c.table_name, t.table_type, c.column_name, c.data_type, c.is_nullable, "
        "c.ordinal_position FROM information_schema.columns c JOIN information_schema.tables t "
        "ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
        "WHERE c.table_schema <> 'information_schema' ORDER BY 1, 2, 7"),
        ("SELECT kcu.table_schema, kcu.table_name, kcu.column_name FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name "
        "AND kcu.table_schema = tc.table_schema AND kcu.table_name = tc.table_name "
        "WHERE tc.constraint_type = 'PRIMARY KEY' ORDER BY 1, 2, kcu.ordinal_position"),
    ),
    "oracle": (
        ("SELECT c.owner, c.table_name, o.object_type, c.column_name, c.data_type, c.nullable, c.column_id "
        "FROM all_tab_columns c JOIN all_objects o ON o.owner = c.owner AND o.object_name = c.table_name "
        "AND o.object_type IN ('TABLE', 'VIEW') WHERE c.owner NOT IN ('SYS', 'SYSTEM') ORDER BY 1, 2, 7"),
        ("SELECT cc.owner, cc.table_name, cc.column_name FROM all_constraints c JOIN all_cons_columns cc "
        "ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name "
        "WHERE c.constraint_type = 'P' AND c.owner NOT IN ('SYS', 'SYSTEM') ORDER BY 1, 2, cc.position"),
    ),
}
_SQLITE_TABLES = ("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
                  "AND name NOT LIKE 'sqlite_%' ORDER BY name")
_SQLITE_COLUMNS = 'SELECT name, type, "notnull", pk FROM pragma_table_info(?) ORDER BY cid'


class CatalogError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _kind(raw: Any) -> str:
    return "view" if "VIEW" in str(raw).upper() else "table"


def _nullable(raw: Any) -> bool:
    return str(raw).upper() in ("YES", "Y", "TRUE", "1")


def _allowed(schema: str | None, name: str, profile: Mapping[str, Any]) -> bool:
    schemas = [s.lower() for s in profile.get("schemas_allowlist") or []]
    tables = [t.lower() for t in profile.get("tables_allowlist") or []]
    if schemas and (schema or "").lower() not in schemas:
        return False
    if tables:
        qualified = f"{schema}.{name}".lower() if schema else name.lower()
        return name.lower() in tables or qualified in tables
    return True


def _finish(tables: Iterable[dict[str, Any]], profile: Mapping[str, Any], source: str,
            default_schema: str | None) -> dict[str, Any]:
    kept = [t for t in tables if _allowed(t.get("schema"), t["name"], profile)]
    for t in kept:
        t.setdefault("kind", "table")
        t.setdefault("primary_key", [])
        t.setdefault("row_count_estimate", None)
        t.setdefault("comment", None)
        t["columns"] = [{"name": c["name"], "type": str(c.get("type") or "").upper(),
                         "nullable": bool(c.get("nullable", True)), "comment": c.get("comment")}
                        for c in t["columns"]]
    kept.sort(key=lambda t: ((t.get("schema") or "").lower(), t["name"].lower()))
    body = {"profile": profile["id"], "dialect": profile["dialect"], "default_schema": default_schema,
            "tables": kept}
    return {"schema_version": SNAPSHOT_SCHEMA, "snapshot_id": hashlib.sha256(_canonical(body).encode()).hexdigest()[:16],
            "source": source, **body}


def introspect(conn: Any, profile: Mapping[str, Any], *, default_schema: str | None = None) -> dict[str, Any]:
    """Read-only introspection through a DB-API connection; returns an unsaved snapshot."""
    dialect = profile["dialect"]
    schema_default = default_schema if default_schema is not None else DEFAULT_SCHEMA.get(dialect)
    cur = None
    try:
        cur = conn.cursor()
        if dialect == "sqlite":
            cur.execute(_SQLITE_TABLES)
            objects = list(cur.fetchall())
            tables = []
            for name, kind in objects:
                cur.execute(_SQLITE_COLUMNS, (name,))
                cols = list(cur.fetchall())
                tables.append({"schema": "main", "name": name, "kind": _kind(kind),
                               "columns": [{"name": c[0], "type": c[1], "nullable": not c[2]} for c in cols],
                               "primary_key": [c[0] for c in sorted(cols, key=lambda c: c[3]) if c[3]]})
            return _finish(tables, profile, "introspect", schema_default)
        if dialect not in INTROSPECTION_SQL:
            raise CatalogError("E_CATALOG_DIALECT", f"no introspection for dialect {dialect!r}")
        columns_sql, keys_sql = INTROSPECTION_SQL[dialect]
        cur.execute(columns_sql)
        by_table: dict[tuple[str, str], dict[str, Any]] = {}
        for schema, table, kind, column, dtype, nullable, _pos in cur.fetchall():
            t = by_table.setdefault((schema, table), {"schema": schema, "name": table, "kind": _kind(kind),
                                                      "columns": []})
            t["columns"].append({"name": column, "type": dtype, "nullable": _nullable(nullable)})
        notes = []
        if keys_sql:
            try:
                cur.execute(keys_sql)
                for schema, table, column in cur.fetchall():
                    if (schema, table) in by_table:
                        by_table[(schema, table)].setdefault("primary_key", []).append(column)
            except Exception as exc:  # noqa: BLE001 — key metadata is optional; the column list is not
                notes.append(f"primary keys unavailable: {type(exc).__name__}")
        snap = _finish(by_table.values(), profile, "introspect", schema_default)
        if notes:
            snap["notes"] = notes
        return snap
    except CatalogError:
        raise
    except Exception as exc:  # noqa: BLE001 — any driver failure is reported, never raised to the host
        raise CatalogError("E_CATALOG_INTROSPECT", f"introspection failed: {type(exc).__name__}") from None
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:  # noqa: BLE001, S110 — closing a cursor is best effort
            pass


def load_declared(path: Path, profile: Mapping[str, Any], *, default_schema: str | None = None) -> dict[str, Any]:
    """A declared catalog file (JSON or YAML subset): ``{tables: [{schema, name, kind, columns: [...]}]}``."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise CatalogError("E_CATALOG_FILE", f"declared catalog not found: {Path(path).name}") from None
    try:
        data = json.loads(text) if Path(path).suffix == ".json" else yamlsubset.parse(text, str(path))
    except (ValueError, yamlsubset.YamlSubsetError) as exc:
        raise CatalogError("E_CATALOG_FILE", f"declared catalog is malformed: {exc}") from None
    tables = data.get("tables") if isinstance(data, dict) else None
    if not isinstance(tables, list):
        raise CatalogError("E_CATALOG_FILE", "declared catalog needs a tables list")
    out = []
    for i, t in enumerate(tables):
        if not isinstance(t, dict) or not isinstance(t.get("name"), str) or not isinstance(t.get("columns"), list):
            raise CatalogError("E_CATALOG_FILE", f"tables[{i}] needs a name and a columns list")
        cols = []
        for c in t["columns"]:
            if isinstance(c, str):
                c = {"name": c}
            if not isinstance(c, dict) or not isinstance(c.get("name"), str):
                raise CatalogError("E_CATALOG_FILE", f"tables[{i}] has a column without a name")
            cols.append(c)
        out.append({"schema": t.get("schema"), "name": t["name"], "kind": _kind(t.get("kind", "table")),
                    "columns": cols, "primary_key": list(t.get("primary_key") or []),
                    "row_count_estimate": t.get("row_count_estimate"), "comment": t.get("comment")})
    schema_default = default_schema if default_schema is not None else data.get("default_schema",
                                                                                 DEFAULT_SCHEMA.get(profile["dialect"]))
    return _finish(out, profile, "file", schema_default)


def connect(profile: Mapping[str, Any], config: Any, connections: Mapping[str, Any] | None) -> Any:
    """An injected connection, or read-only SQLite for a ``sqlite-file:`` location pointer."""
    injected = (connections or {}).get(profile["id"])
    if injected is not None:
        try:
            return injected["connect"]()
        except Exception as exc:  # noqa: BLE001 — driver errors may carry connection strings; report the type only
            raise CatalogError("E_CATALOG_CONNECTION", f"connection failed: {type(exc).__name__}") from None
    ref = profile.get("connection", {}).get("secret_ref", "")
    if profile["dialect"] == "sqlite" and ref.startswith("sqlite-file:"):
        path = config.resolve_path(ref[len("sqlite-file:"):]).resolve()
        if not path.exists():
            raise CatalogError("E_CATALOG_CONNECTION", "SQLite database file not found")
        return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    raise CatalogError("E_CATALOG_CONNECTION", f"no connection injected for profile {profile['id']!r}; drivers "
                                               "and secrets are supplied by the host application")


def snapshot_profile(config: Any, profile_id: str, connections: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Take one profile's snapshot as its ``catalog.<profile>`` entry says (``introspect`` or ``file``)."""
    profile = config.profile(profile_id)
    entry = config.data.get("catalog", {}).get(profile_id) or {"source": "introspect"}
    default_schema = entry.get("default_schema")
    if entry.get("source", "introspect") == "file":
        return load_declared(config.resolve_path(entry["file"]), profile, default_schema=default_schema)
    conn = connect(profile, config, connections)
    try:
        return introspect(conn, profile, default_schema=default_schema)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001, S110 — closing is best effort
            pass


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

def _profile_dir(index_dir: Path, profile_id: str) -> Path:
    return Path(index_dir) / "catalog" / profile_id


def history(index_dir: Path, profile_id: str) -> list[dict[str, Any]]:
    path = _profile_dir(index_dir, profile_id) / "history.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def store(index_dir: Path, snapshot: Mapping[str, Any], taken_on: str) -> dict[str, Any]:
    """Save a snapshot if it is new; unchanged content writes nothing."""
    pdir = _profile_dir(index_dir, snapshot["profile"])
    hist = history(index_dir, snapshot["profile"])
    previous = hist[-1]["snapshot_id"] if hist else None
    changed = previous != snapshot["snapshot_id"]
    if changed:
        pdir.mkdir(parents=True, exist_ok=True)
        target = pdir / f"{snapshot['snapshot_id']}.json"
        if not target.exists():
            target.write_text(json.dumps(snapshot, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                              encoding="utf-8")
        hist.append({"snapshot_id": snapshot["snapshot_id"], "taken_on": taken_on, "source": snapshot["source"]})
        (pdir / "history.json").write_text(json.dumps(hist, indent=1) + "\n", encoding="utf-8")
    return {"profile": snapshot["profile"], "snapshot_id": snapshot["snapshot_id"], "previous_id": previous,
            "changed": changed, "source": snapshot["source"], "tables": len(snapshot["tables"]),
            "columns": sum(len(t["columns"]) for t in snapshot["tables"])}


def load_snapshot(index_dir: Path, profile_id: str, snapshot_id: str | None = None) -> dict[str, Any] | None:
    hist = history(index_dir, profile_id)
    if not hist:
        return None
    sid = snapshot_id or hist[-1]["snapshot_id"]
    path = _profile_dir(index_dir, profile_id) / f"{sid}.json"
    if not path.exists():
        raise CatalogError("E_NOT_FOUND", f"no snapshot {sid} for profile {profile_id}")
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Resolution, diff, reconciliation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Resolved:
    ok: bool
    table: str | None = None          # schema.table as the catalog names it
    column: str | None = None
    type: str | None = None
    reason: str | None = None


class Resolver:
    """Resolve ``table``, ``schema.table``, and ``[schema.]table.column`` against one snapshot."""

    def __init__(self, snapshot: Mapping[str, Any]) -> None:
        self.snapshot = snapshot
        self.default_schema = (snapshot.get("default_schema") or "").lower() or None
        self._by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
        self._by_name: dict[str, list[Mapping[str, Any]]] = {}
        for t in snapshot["tables"]:
            self._by_key[((t.get("schema") or "").lower(), t["name"].lower())] = t
            self._by_name.setdefault(t["name"].lower(), []).append(t)

    @staticmethod
    def label(t: Mapping[str, Any]) -> str:
        return f"{t['schema']}.{t['name']}" if t.get("schema") else t["name"]

    def table(self, ref: str) -> tuple[Mapping[str, Any] | None, str | None]:
        parts = [p.strip('"`[]').lower() for p in ref.split(".")]
        if len(parts) == 1:
            if self.default_schema and (self.default_schema, parts[0]) in self._by_key:
                return self._by_key[(self.default_schema, parts[0])], None
            found = self._by_name.get(parts[0], [])
            if len(found) == 1:
                return found[0], None
            return None, (f"table {ref!r} is ambiguous across schemas" if found else f"table {ref!r} not in catalog")
        key = (parts[-2], parts[-1])
        if key in self._by_key:
            return self._by_key[key], None
        return None, f"table {ref!r} not in catalog"

    def column(self, ref: str) -> Resolved:
        if "." not in ref:
            return Resolved(False, reason=f"column {ref!r} is not qualified with its table")
        table_ref, col = ref.rsplit(".", 1)
        t, why = self.table(table_ref)
        if t is None:
            return Resolved(False, reason=why)
        for c in t["columns"]:
            if c["name"].lower() == col.strip('"`[]').lower():
                return Resolved(True, self.label(t), c["name"], c["type"])
        return Resolved(False, self.label(t), reason=f"column {ref!r} not in catalog table {self.label(t)}")


def _columns(snapshot: Mapping[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    return {Resolver.label(t).lower(): {c["name"].lower(): c for c in t["columns"]} for t in snapshot["tables"]}


def diff(old: Mapping[str, Any] | None, new: Mapping[str, Any]) -> dict[str, Any]:
    """Changes from ``old`` to ``new``, classified ``compatible`` or ``breaking``."""
    if old is None:
        return {"from": None, "to": new["snapshot_id"], "classification": "initial", "changes": [], "handoff": None}
    a, b = _columns(old), _columns(new)
    changes: list[dict[str, Any]] = []
    for t in sorted(set(a) | set(b)):
        if t not in b:
            changes.append({"change": "table_removed", "table": t, "breaking": True})
            continue
        if t not in a:
            changes.append({"change": "table_added", "table": t, "breaking": False})
            continue
        for c in sorted(set(a[t]) | set(b[t])):
            if c not in b[t]:
                changes.append({"change": "column_removed", "table": t, "column": c, "breaking": True})
            elif c not in a[t]:
                changes.append({"change": "column_added", "table": t, "column": c, "breaking": False})
            else:
                if a[t][c]["type"] != b[t][c]["type"]:
                    changes.append({"change": "column_retyped", "table": t, "column": c, "breaking": True,
                                    "from_type": a[t][c]["type"], "to_type": b[t][c]["type"]})
                if not a[t][c]["nullable"] and b[t][c]["nullable"]:
                    changes.append({"change": "nullability_relaxed", "table": t, "column": c, "breaking": True})
    breaking = any(c["breaking"] for c in changes)
    return {"from": old["snapshot_id"], "to": new["snapshot_id"],
            "classification": "breaking" if breaking else ("compatible" if changes else "unchanged"),
            "changes": changes,
            "handoff": ({"agent": "schema_evolution", "path": "data_engineering/schema_evolution",
                         "reason": "breaking catalog change: decide whether downstream queries and loads are safe"}
                        if breaking else None)}


def exemplar_references(exemplar: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """(tables, qualified columns) an exemplar references, from its extracted structure."""
    s = exemplar.get("structure", {})
    tables = sorted(set(s.get("tables", [])) | set(exemplar.get("tables") or []))
    cols: set[str] = set(exemplar.get("pit_columns") or [])
    for item in s.get("select", []):
        cols.update(item.get("columns", []))
    for f in s.get("filters", []):
        cols.add(f["column"])
    for j in s.get("joins", []):
        cols.update((j["left"], j["right"]))
    return tables, sorted(c for c in cols if "." in c)


def reconcile(snapshots: Mapping[str, Mapping[str, Any]], exemplars: Sequence[Mapping[str, Any]],
              policies: Mapping[str, str], repo_profiles: Mapping[str, str | None]) -> dict[str, Any]:
    """Drift of every exemplar whose profile has a snapshot."""
    resolvers = {p: Resolver(s) for p, s in snapshots.items()}
    drifted, checked = [], 0
    for e in exemplars:
        profile = e.get("profile") or repo_profiles.get(e.get("repo_id", ""))
        if profile not in resolvers:
            continue
        checked += 1
        r = resolvers[profile]
        tables, cols = exemplar_references(e)
        missing_tables = sorted({t for t in tables if r.table(t)[0] is None})
        missing_cols = sorted(c for c in cols if c.rsplit(".", 1)[0] not in missing_tables and not r.column(c).ok)
        if missing_tables or missing_cols:
            policy = policies.get(profile, "exclude")
            drifted.append({"exemplar_id": e["exemplar_id"], "query_id": e.get("query_id"), "repo_id": e.get("repo_id"),
                            "path": e.get("path"), "profile": profile, "review_status": e.get("review_status"),
                            "snapshot_id": snapshots[profile]["snapshot_id"], "missing_tables": missing_tables,
                            "missing_columns": missing_cols,
                            "status": "excluded" if policy == "exclude" else "warned",
                            "action": "Re-review the query against the current catalog (or restore the object); "
                                      "it is excluded from retrieval until a reconcile finds it clean."
                                      if policy == "exclude" else "Review the query; drift_policy is warn."})
    drifted.sort(key=lambda d: (d["profile"], d["exemplar_id"]))
    return {"snapshots": {p: s["snapshot_id"] for p, s in sorted(snapshots.items())}, "checked": checked,
            "drifted": drifted}


def write_drift(index_dir: Path, report: Mapping[str, Any]) -> bool:
    path = Path(index_dir) / "drift.json"
    text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def excluded_exemplars(index_dir: Path) -> dict[str, str]:
    """``exemplar_id -> reason`` for exemplars a reconcile excluded."""
    path = Path(index_dir) / "drift.json"
    if not path.exists():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    return {d["exemplar_id"]: "drift: missing " + ", ".join(d["missing_tables"] + d["missing_columns"])
            for d in report.get("drifted", []) if d["status"] == "excluded"}
