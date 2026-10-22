"""Query front-matter: extraction, validation, and consistency with the SQL.

Spec ``0114`` REQ-004 (realizing ``0113`` REQ-005). Front-matter is a YAML
block inside the leading comment of a ``.sql`` file::

    -- ---
    -- id: sl.utilization.by_security.as_of
    -- title: ...
    -- ---
    SELECT ...

or, when the repository declares ``metadata_convention: sidecar``, a
``<name>.yml`` next to ``<name>.sql``. It is parsed as data only. A file with
no front-matter is indexable as ``unreviewed``; a file whose front-matter is
malformed or inconsistent with its SQL is rejected with a reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import yamlsubset
from .sqlstructure import SqlStructureError, extract

__all__ = ["ParsedQuery", "QueryRejected", "parse_query", "split_front_matter", "validate_meta"]

_MARKER_RE = re.compile(r"^\s*--\s*---\s*$")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_PLACEHOLDER_RE = re.compile(r"<[^<>\s][^<>]*>")

REVIEW_STATUSES = ("draft", "reviewed", "deprecated")
PARAM_TYPES = ("date", "timestamp", "string", "integer", "number", "boolean", "string_list", "integer_list")
VIEWPOINTS = ("lender", "beneficial_owner", "agent", "borrower")
REQUIRED_ALWAYS = ("id", "title", "intent", "review_status")
REQUIRED_REVIEWED = ("owner", "dialect", "profile", "params", "tables", "pit_columns", "grain",
                     "reviewed_by", "reviewed_on")
OPTIONAL = ("tags", "concepts", "viewpoint", "supersedes", "notes", "default", "description")
KNOWN = set(REQUIRED_ALWAYS) | set(REQUIRED_REVIEWED) | set(OPTIONAL)


class QueryRejected(ValueError):
    def __init__(self, code: str, reason: str, line: int = 0) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason
        self.line = line


@dataclass
class ParsedQuery:
    meta: Optional[Dict[str, Any]]      # None when the file has no front-matter
    sql: str
    line_span: Tuple[int, int]          # 1-based, inclusive, of the SQL body
    structure: Dict[str, Any]
    findings: List[str] = field(default_factory=list)

    @property
    def review_status(self) -> str:
        return "unreviewed" if self.meta is None else self.meta["review_status"]


def split_front_matter(text: str, source: str) -> Tuple[Optional[Dict[str, Any]], str, int]:
    """Return (front-matter or None, SQL body, 1-based first line of the body)."""
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None or not _MARKER_RE.match(lines[first]):
        return None, text, 1
    end = next((i for i in range(first + 1, len(lines)) if _MARKER_RE.match(lines[i])), None)
    if end is None:
        raise QueryRejected("E_FRONTMATTER_INVALID", "front-matter opened with '-- ---' but never closed",
                            first + 1)
    body: List[str] = []
    for i in range(first + 1, end):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped:
            body.append("")
            continue
        if not stripped.startswith("--"):
            raise QueryRejected("E_FRONTMATTER_INVALID", "every front-matter line must start with '--'", i + 1)
        content = stripped[2:]
        body.append(content[1:] if content.startswith(" ") else content)
    # Line numbers inside the YAML are offset by the header line.
    padded = "\n" * (first + 1) + "\n".join(body)
    try:
        meta = yamlsubset.parse(padded, source)
    except yamlsubset.YamlSubsetError as exc:
        raise QueryRejected("E_FRONTMATTER_INVALID", exc.message, exc.line) from None
    if not isinstance(meta, dict):
        raise QueryRejected("E_FRONTMATTER_INVALID", "front-matter must be a mapping", first + 1)
    sql = "\n".join(lines[end + 1:])
    return meta, sql, end + 2


def validate_meta(meta: Dict[str, Any], structure: Dict[str, Any]) -> List[str]:
    """Raise on invalid front-matter; return non-fatal findings."""
    for key in meta:
        if key not in KNOWN and not str(key).startswith("x_"):
            raise QueryRejected("E_FRONTMATTER_INVALID", f"unknown key {key!r} (extensions use an x_ prefix)")
    for key in REQUIRED_ALWAYS:
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise QueryRejected("E_FRONTMATTER_INVALID", f"missing or empty {key!r}")
    if not _ID_RE.match(meta["id"]):
        raise QueryRejected("E_FRONTMATTER_INVALID", f"id {meta['id']!r} must be lowercase dotted words")
    status = meta["review_status"]
    if status not in REVIEW_STATUSES:
        raise QueryRejected("E_FRONTMATTER_INVALID",
                            f"review_status {status!r} is not one of {', '.join(REVIEW_STATUSES)}")
    for key in ("tags", "concepts", "tables", "pit_columns"):
        if key in meta and meta[key] is not None and (
                not isinstance(meta[key], list) or not all(isinstance(v, str) for v in meta[key])):
            raise QueryRejected("E_FRONTMATTER_INVALID", f"{key!r} must be a list of strings")
    if meta.get("viewpoint") is not None and meta["viewpoint"] not in VIEWPOINTS:
        raise QueryRejected("E_FRONTMATTER_INVALID", f"viewpoint must be one of {', '.join(VIEWPOINTS)}")

    params = meta.get("params") or []
    if not isinstance(params, list):
        raise QueryRejected("E_FRONTMATTER_INVALID", "params must be a list")
    declared: List[str] = []
    for p in params:
        if not isinstance(p, dict) or not isinstance(p.get("name"), str):
            raise QueryRejected("E_FRONTMATTER_INVALID", "each param needs a name")
        if p.get("type") not in PARAM_TYPES:
            raise QueryRejected("E_FRONTMATTER_INVALID",
                                f"param {p['name']!r} type must be one of {', '.join(PARAM_TYPES)}")
        unknown = set(p) - {"name", "type", "required", "default", "description"}
        if unknown:
            raise QueryRejected("E_FRONTMATTER_INVALID", f"param {p['name']!r} has unknown keys {sorted(unknown)}")
        declared.append(p["name"])
    if len(set(declared)) != len(declared):
        raise QueryRejected("E_FRONTMATTER_INVALID", "duplicate parameter names")

    findings: List[str] = []
    if status == "reviewed":
        for key in REQUIRED_REVIEWED:
            if key not in meta or meta[key] in (None, ""):
                raise QueryRejected("E_FRONTMATTER_INVALID", f"reviewed queries need {key!r}")
        if not meta["tables"]:
            raise QueryRejected("E_FRONTMATTER_INVALID", "reviewed queries must list their tables")
        if not isinstance(meta["reviewed_on"], str) or not _DATE_RE.match(meta["reviewed_on"]):
            raise QueryRejected("E_FRONTMATTER_INVALID", "reviewed_on must be an ISO date YYYY-MM-DD")
        for key in ("owner", "reviewed_by"):
            if not _HANDLE_RE.match(str(meta[key])):
                raise QueryRejected("E_FRONTMATTER_INVALID",
                                    f"{key} must be a pseudonymous handle (lowercase, no email address)")
        for path, value in _strings(meta):
            if _PLACEHOLDER_RE.search(value):
                raise QueryRejected("E_FRONTMATTER_PLACEHOLDER", f"unresolved placeholder in {path}: {value!r}")
        used = structure["params"]
        missing = [u for u in used if u not in declared]
        unused = [d for d in declared if d not in used]
        if missing:
            raise QueryRejected("E_FRONTMATTER_INVALID", f"parameters used but not declared: {', '.join(missing)}")
        if unused:
            raise QueryRejected("E_FRONTMATTER_INVALID", f"parameters declared but not used: {', '.join(unused)}")
        if structure["positional_params"]:
            raise QueryRejected("E_FRONTMATTER_INVALID",
                                "reviewed queries use named parameters only (positional '?' found)")
        declared_tables = {t.lower() for t in meta["tables"]}
        extracted = set(structure["tables"])
        bare = {t.split(".")[-1] for t in extracted}
        missing_tables = sorted(t for t in declared_tables if t not in extracted and t not in bare)
        extra_tables = sorted(t for t in extracted if t not in declared_tables and t.split(".")[-1] not in declared_tables)
        if missing_tables:
            findings.append(f"declared tables not found in SQL: {', '.join(missing_tables)}")
        if extra_tables:
            findings.append(f"tables in SQL not declared: {', '.join(extra_tables)}")
    if not structure["read_only_shape"]:
        findings.append("SQL is not a single read-only statement; it will never be eligible for execution")
    findings.extend(f"extraction: {u}" for u in structure["unresolved"])
    return findings


def _strings(value: Any, path: str = ""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, f"{path}[{i}]")


def parse_query(text: str, source: str, *, dialect: str, sidecar: Optional[str] = None) -> ParsedQuery:
    """Parse one query file (raising :class:`QueryRejected` when it is invalid)."""
    if sidecar is not None:
        try:
            meta = yamlsubset.parse(sidecar, source + " (sidecar)")
        except yamlsubset.YamlSubsetError as exc:
            raise QueryRejected("E_FRONTMATTER_INVALID", exc.message, exc.line) from None
        if not isinstance(meta, dict):
            raise QueryRejected("E_FRONTMATTER_INVALID", "sidecar must be a mapping")
        sql, start = text, 1
    else:
        meta, sql, start = split_front_matter(text, source)
    query_dialect = meta.get("dialect", dialect) if isinstance(meta, dict) else dialect
    try:
        structure = extract(sql, query_dialect if isinstance(query_dialect, str) else dialect)
    except SqlStructureError as exc:
        raise QueryRejected("E_SQL_UNREADABLE", str(exc)) from None
    if structure["statement_count"] == 0:
        raise QueryRejected("E_SQL_UNREADABLE", "no SQL statement found")
    sql_lines = sql.splitlines()
    first = next((i for i, line in enumerate(sql_lines) if line.strip()), 0)
    last = max((i for i, line in enumerate(sql_lines) if line.strip()), default=0)
    findings = validate_meta(meta, structure) if meta is not None else (
        [f"extraction: {u}" for u in structure["unresolved"]]
        + ([] if structure["read_only_shape"]
           else ["SQL is not a single read-only statement; it will never be eligible for execution"]))
    return ParsedQuery(meta, sql.strip("\n"), (start + first, start + last), structure, findings)
