"""Read-only dataset sources, the template executor, budgets, and provenance.

Spec ``0121`` REQ-003, REQ-004, REQ-005, REQ-007, REQ-015.

A *dataset* is declared in configuration (``datasets[]``): a database
object with explicit columns, ordering, and bound filters, or a local file.
Files are loaded, within the POC limits, into an in-memory SQLite table so
that one template path serves both.

Connections come from an injected factory: ``ctx.clients["connections"]``
maps a profile ID to ``{"connect": callable, "paramstyle": "qmark" |
"format" | "named" | "numeric"}``. For SQLite profiles whose ``secret_ref``
is ``sqlite-file:<path>`` the plugin opens the file read-only itself
(``mode=ro``); that pointer is a location, not a secret. No driver is
imported by this package.

Every executed statement is a rendered template (see ``templates.py``) and
is recorded with its provenance: object, version pin, filters, template and
version, SQL hash, bound parameters (sensitive values redacted), rows,
truncation, scope, exactness, bytes scanned (``unknown`` unless the platform
reports it), and timing.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import intake
from .templates import Rendered, TemplateError, render

__all__ = ["TRANSIENT_CODE", "Budget", "BudgetExhausted", "Dataset", "Executor", "SourceError", "load_dataset"]

TRANSIENT_CODE = "E_SOURCE_TRANSIENT"
SCOPES = ("full_filtered_population", "ordered_extract", "random_sample", "approximate_aggregate")


class SourceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class BudgetExhausted(SourceError):
    def __init__(self, budget: str, message: str) -> None:
        super().__init__("E_BUDGET_EXHAUSTED", message)
        self.budget = budget


@dataclass
class Budget:
    limits: dict[str, Any]
    clock: Callable[[], float] = time.monotonic
    started: float = 0.0
    queries: int = 0
    rows_local: int = 0
    bytes_local: int = 0

    def start(self) -> None:
        self.started = self.clock()

    def elapsed(self) -> float:
        return self.clock() - self.started

    def check_time(self) -> None:
        if self.elapsed() > self.limits["wall_time_seconds"]:
            raise BudgetExhausted("wall_time_seconds", f"wall-time budget of {self.limits['wall_time_seconds']}s used")

    def take_query(self) -> None:
        self.check_time()
        if self.queries >= self.limits["max_queries"]:
            raise BudgetExhausted("max_queries", f"query budget of {self.limits['max_queries']} used")
        self.queries += 1

    def take_rows(self, rows: int, nbytes: int) -> None:
        if self.rows_local + rows > self.limits["max_rows_local"]:
            raise BudgetExhausted("max_rows_local", f"local-row budget of {self.limits['max_rows_local']} reached")
        if self.bytes_local + nbytes > self.limits["max_local_bytes"]:
            raise BudgetExhausted("max_local_bytes", f"local-byte budget of {self.limits['max_local_bytes']} reached")
        self.rows_local += rows
        self.bytes_local += nbytes

    def used(self) -> dict[str, Any]:
        return {"queries": self.queries, "rows_local": self.rows_local, "bytes_local": self.bytes_local}


@dataclass
class Dataset:
    id: str
    source: str                      # database | file
    dialect: str
    obj: str
    columns: tuple[str, ...]
    order_by: tuple[str, ...]
    filters: tuple[dict[str, Any], ...]
    version: int | None
    dataset_kind: str
    profile: str | None
    path: Path | None = None
    max_rows: int = 5000
    is_view: bool | None = None
    file_bytes: bytes | None = None

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "source": self.source, "dialect": self.dialect, "object": self.obj,
                "columns": list(self.columns), "order_by": list(self.order_by),
                "filters": [{"column": f["column"], "op": f["op"]} for f in self.filters],
                "version": self.version, "dataset_kind": self.dataset_kind, "profile": self.profile,
                "file": self.path.name if self.path else None}


def load_dataset(config: Any, dataset_id: str) -> Dataset:
    for d in config.data.get("datasets", []):
        if d["id"] == dataset_id:
            break
    else:
        raise SourceError("E_RESEARCH_DATASET", f"no dataset {dataset_id!r} in configuration")
    if d["source"] == "file":
        path = config.resolve_path(d["path"])
        return Dataset(d["id"], "file", "sqlite", "intake_file", tuple(d["columns"]), tuple(d.get("order_by") or d["columns"][:1]),
                       tuple(d.get("filters", [])), None, d.get("dataset_kind", "generic"), None, path,
                       d.get("max_rows", 5000))
    profile = config.profile(d["profile"])
    return Dataset(d["id"], "database", profile["dialect"], d["object"], tuple(d["columns"]), tuple(d["order_by"]),
                   tuple(d.get("filters", [])), d.get("version"), d.get("dataset_kind", "generic"), d["profile"],
                   None, min(d.get("max_rows", 5000), profile.get("row_limit", 5000)))


def _encode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)              # stored evidence keeps decimal digits
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise SourceError("E_RESEARCH_VALUE", "binary columns must be excluded")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


_PARAM_RE = re.compile(r":p(\d+)")


def _to_paramstyle(sql: str, params: Sequence[Any], style: str) -> tuple[str, Any]:
    order = [int(m) for m in _PARAM_RE.findall(sql)]
    if style == "named":
        return _PARAM_RE.sub(lambda m: f":p{m.group(1)}", sql), {f"p{i}": params[i] for i in set(order)}
    values = [params[i] for i in order]
    if style == "qmark":
        return _PARAM_RE.sub("?", sql), values
    if style == "format":
        return _PARAM_RE.sub("%s", sql.replace("%", "%%")), values
    if style == "numeric":
        counter = iter(range(1, len(order) + 1))
        return _PARAM_RE.sub(lambda m: f":{next(counter)}", sql), values
    raise SourceError("E_RESEARCH_CONNECTION", f"unsupported paramstyle {style!r}")


class Executor:
    """Runs rendered templates against one dataset under a budget."""

    def __init__(self, dataset: Dataset, budget: Budget, *, connections: Mapping[str, Any] | None = None,
                 config: Any = None, allowed: Sequence[str] = (), sensitive: Sequence[str] = ()) -> None:
        self.dataset = dataset
        self.budget = budget
        self.allowed = tuple(allowed)
        self.sensitive = tuple(sensitive)
        self.log: list[dict[str, Any]] = []
        self._conn: Any = None
        self._paramstyle = "qmark"
        self._connections = connections or {}
        self._config = config
        self.capabilities = {"hard_cancel": False, "bytes_scanned": False}

    # -- connections ------------------------------------------------------
    def _open(self) -> Any:
        if self._conn is not None:
            return self._conn
        ds = self.dataset
        if ds.source == "file":
            self._conn = self._load_file()
            self._paramstyle = "qmark"
        else:
            injected = self._connections.get(ds.profile)
            if injected is not None:
                self._conn = injected["connect"]()
                self._paramstyle = injected.get("paramstyle", "qmark")
            else:
                profile = self._config.profile(ds.profile) if self._config else {}
                ref = profile.get("connection", {}).get("secret_ref", "")
                if ds.dialect != "sqlite" or not ref.startswith("sqlite-file:"):
                    raise SourceError("E_RESEARCH_CONNECTION",
                                      f"no connection injected for profile {ds.profile!r}; drivers are supplied by "
                                      "the host application")
                path = self._config.resolve_path(ref[len("sqlite-file:"):]).resolve()
                if not path.exists():
                    raise SourceError("E_RESEARCH_CONNECTION", "SQLite database file not found")
                self._conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                self._paramstyle = "qmark"
            if ds.dialect == "sqlite" and isinstance(self._conn, sqlite3.Connection):
                self.capabilities["hard_cancel"] = True
                self._conn.set_progress_handler(self._progress, 1000)
        return self._conn

    def _progress(self) -> int:
        try:
            self.budget.check_time()
        except BudgetExhausted:
            return 1          # non-zero aborts the running SQLite statement
        return 0

    def _load_file(self) -> sqlite3.Connection:
        ds = self.dataset
        raw = ds.path.read_bytes()
        ds.file_bytes = raw
        headers, records, _malformed = intake.parse(raw, ds.path.suffix.lower())
        missing_cols = [c for c in ds.columns if c not in headers]
        if missing_cols:
            raise SourceError("E_RESEARCH_DATASET", f"declared columns absent from file: {', '.join(missing_cols)}")
        profiles = intake.profile(headers, records)
        conn = sqlite3.connect(":memory:")
        cols = ", ".join(f'"{c}"' for c in ds.columns)
        conn.execute(f'CREATE TABLE "intake_file" ({cols})')

        def typed(c: str, v: Any) -> Any:
            if intake.missing(v):
                return None
            return intake.numeric(v) if profiles[c]["type"] == "numeric" else v
        conn.executemany(f'INSERT INTO "intake_file" VALUES ({", ".join("?" for _ in ds.columns)})',
                         [[typed(c, r.get(c)) for c in ds.columns] for r in records])
        conn.commit()
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- execution --------------------------------------------------------
    def render(self, template: str, **args: Any) -> Rendered:
        ds = self.dataset
        return render(template, dialect=ds.dialect, obj=ds.obj, allowed=self.allowed, filters=list(ds.filters),
                      version=ds.version, sensitive=self.sensitive, **args)

    def run(self, template: str, *, scope: str = "full_filtered_population", **args: Any) -> dict[str, Any]:
        """Render, budget, execute, and record one template; return rows and provenance."""
        try:
            rendered = self.render(template, **args)
        except TemplateError as exc:
            raise SourceError("E_RESEARCH_TEMPLATE", str(exc)) from None
        self.budget.take_query()
        conn = self._open()
        sql, params = _to_paramstyle(rendered.sql, rendered.params, self._paramstyle)
        started = self.budget.clock()
        attempts = 1   # retries are the loop's decision (at most one, after E_SOURCE_TRANSIENT), not the executor's
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            names = [d[0].lower() for d in cursor.description]
            fetched = cursor.fetchmany(rendered.max_rows + 1)
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc):
                raise BudgetExhausted("wall_time_seconds", "query cancelled at the wall-time budget") from None
            raise SourceError(TRANSIENT_CODE if "locked" in str(exc) or "busy" in str(exc) else "E_RESEARCH_QUERY",
                              "query failed; driver details suppressed") from None
        except Exception as exc:  # noqa: BLE001 — driver errors are suppressed (they can carry connection details)
            transient = getattr(exc, "sfmeridian_transient", False)
            raise SourceError(TRANSIENT_CODE if transient else "E_RESEARCH_QUERY",
                              "query failed; driver details suppressed") from None
        finally:
            if cursor is not None:
                cursor.close()
        truncated = len(fetched) > rendered.max_rows
        rows = [dict(zip(names, (_encode(v) for v in row))) for row in fetched[:rendered.max_rows]]
        if template == "extract":
            self.budget.take_rows(len(rows), len(json.dumps(rows, default=str)))
        record = {
            "query_id": f"Q-{len(self.log) + 1:03d}",
            "template": rendered.template, "template_version": rendered.version, "sql_sha256": rendered.sha256,
            "sql": rendered.sql, "parameters": rendered.redacted_params(),
            "object": self.dataset.obj, "source_version": self.dataset.version,
            "filters": [{"column": f["column"], "op": f["op"]} for f in self.dataset.filters],
            "rows_returned": len(rows), "truncated": truncated,
            "scope": "ordered_extract" if template == "extract" else scope,
            "exact": template != "extract" or not truncated,
            "bytes_scanned": "unknown", "attempts": attempts,
            "elapsed_seconds": round(self.budget.clock() - started, 6),
        }
        self.log.append(record)
        return {"rows": rows, "provenance": record}
