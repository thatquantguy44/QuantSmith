"""Plugin-owned, reviewed SELECT templates for dataset research.

Spec ``0121`` REQ-004, REQ-007 (POC AC-07, §7). The research agent never runs
model-produced or repository SQL. It renders one of the templates below with:

* identifiers validated as simple names (POC rules: letters, digits,
  underscores; objects up to three parts) and drawn from the dataset's
  allowed columns;
* every value bound as a named parameter (``:p0``, ``:p1``, …), converted to
  the connection's parameter style only at execution;
* a row limit on every statement that can return more than one row — one
  row more than is kept, so truncation is detected (the POC's rule).

Each rendered statement then passes :func:`check_rendered`, the same static
rules ``0116``'s verifier enforces: one read-only statement, every name
either the object, an allowed column, a template alias, or a whitelisted
function, and no string literal from input. A template that fails the check
is never executed.

Dialects: ``sqlite``, ``postgres``, ``oracle``, ``databricks``; ``mssql``
templates exist (the POC supports SQL Server) but are gated off by
configuration until the owner enables the dialect.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ..sqlstructure import extract, tokenize

__all__ = ["Predicate", "Rendered", "TemplateError", "check_rendered", "quote", "render"]

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TEMPLATE_VERSION = "1"
FILTER_OPS = ("=", ">=", ">", "<=", "<", "<>")
_ALIASES = frozenset({"n", "non_null", "distinct_n", "min_v", "max_v", "sum_v", "grp", "nulls", "violations",
                      "applicable", "repeated_keys", "rows_in_repeats", "missing_key_rows", "max_change", "t", "d",
                      "version", "of"})
_FUNCTIONS = frozenset({"count", "sum", "min", "max", "coalesce", "abs"})


class TemplateError(ValueError):
    code = "E_RESEARCH_TEMPLATE"


@dataclass(frozen=True)
class Rendered:
    template: str
    sql: str
    params: tuple[Any, ...]
    sensitive_params: tuple[int, ...] = ()
    max_rows: int = 1
    version: str = TEMPLATE_VERSION

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()

    def redacted_params(self) -> list[Any]:
        return ["<redacted>" if i in self.sensitive_params else v for i, v in enumerate(self.params)]


@dataclass
class Predicate:
    """A structured boolean condition: never raw SQL text.

    ``kind`` is one of ``cmp_value`` (column op value), ``cmp_column``
    (column op column), ``cmp_scaled`` (column op other × value), ``null``,
    ``not_null``, ``not_in`` (column not in values), ``abs_diff_gt``
    (|a − b·c/10000/360| > value; the ACT/360 accrual check), ``any``/``all``
    (of sub-predicates).
    """

    kind: str
    column: str | None = None
    op: str | None = None
    value: Any = None
    other: str | None = None
    third: str | None = None
    values: Sequence[Any] = ()
    parts: Sequence[Predicate] = field(default_factory=list)

    def columns(self) -> list[str]:
        out = [c for c in (self.column, self.other, self.third) if c]
        for p in self.parts:
            out.extend(p.columns())
        return out


def quote(name: str, dialect: str) -> str:
    """Quote a validated simple identifier.

    Oracle folds unquoted names to upper case, so quoting a lower-case name
    there would change its meaning; validated names are emitted unquoted for
    Oracle and quoted elsewhere.
    """
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise TemplateError(f"invalid identifier {name!r}: use letters, digits, and underscores")
    if dialect == "databricks":
        return f"`{name}`"
    if dialect == "mssql":
        return f"[{name}]"
    if dialect == "oracle":
        return name
    return f'"{name}"'


def quote_object(name: str, dialect: str) -> str:
    parts = name.split(".") if isinstance(name, str) else []
    if not 1 <= len(parts) <= 3:
        raise TemplateError("object names have one to three parts")
    return ".".join(quote(p, dialect) for p in parts)


class _Builder:
    def __init__(self, dialect: str, obj: str, allowed: Sequence[str], version: int | None,
                 filters: Sequence[dict[str, Any]], sensitive: Sequence[str]) -> None:
        if dialect not in ("sqlite", "postgres", "oracle", "databricks", "mssql"):
            raise TemplateError(f"unsupported dialect {dialect!r}")
        self.dialect = dialect
        self.allowed = set(allowed)
        self.sensitive = set(sensitive)
        self.params: list[Any] = []
        self.sensitive_idx: list[int] = []
        self.source = quote_object(obj, dialect)
        if version is not None:
            if dialect != "databricks" or not isinstance(version, int) or isinstance(version, bool) or version < 0:
                raise TemplateError("version pins need a non-negative Databricks Delta table version")
            self.source += f" VERSION AS OF {version}"
        self.where: list[str] = []
        for f in filters:
            self.where.append(self.cmp_value(f["column"], f["op"], f["value"]))

    def col(self, name: str) -> str:
        if name not in self.allowed:
            raise TemplateError(f"column {name!r} is not an allowed analysis column for this dataset")
        return quote(name, self.dialect)

    def bind(self, value: Any, column: str | None = None) -> str:
        if value is None or not isinstance(value, (str, int, float, bool)):
            raise TemplateError("bound values must be non-null scalars")
        self.params.append(value)
        if column in self.sensitive:
            self.sensitive_idx.append(len(self.params) - 1)
        return f":p{len(self.params) - 1}"

    def cmp_value(self, column: str, op: str, value: Any) -> str:
        if op not in FILTER_OPS:
            raise TemplateError(f"unsupported operator {op!r}")
        return f"{self.col(column)} {op} {self.bind(value, column)}"

    def predicate(self, p: Predicate) -> str:
        if p.kind == "cmp_value":
            return self.cmp_value(p.column, p.op, p.value)
        if p.kind == "cmp_column":
            if p.op not in FILTER_OPS:
                raise TemplateError(f"unsupported operator {p.op!r}")
            return f"{self.col(p.column)} {p.op} {self.col(p.other)}"
        if p.kind == "cmp_scaled":
            if p.op not in FILTER_OPS:
                raise TemplateError(f"unsupported operator {p.op!r}")
            return f"{self.col(p.column)} {p.op} {self.col(p.other)} * {self.bind(p.value)}"
        if p.kind == "null":
            return f"{self.col(p.column)} IS NULL"
        if p.kind == "not_null":
            return f"{self.col(p.column)} IS NOT NULL"
        if p.kind == "not_in":
            if not p.values:
                raise TemplateError("not_in needs values")
            return f"{self.col(p.column)} NOT IN ({', '.join(self.bind(v, p.column) for v in p.values)})"
        if p.kind == "abs_diff_gt":
            return (f"ABS({self.col(p.column)} - {self.col(p.other)} * {self.col(p.third)} / 10000.0 / 360.0) > "
                    f"{self.bind(p.value)}")
        if p.kind in ("any", "all"):
            if not p.parts:
                raise TemplateError(f"{p.kind} needs parts")
            joiner = " OR " if p.kind == "any" else " AND "
            return "(" + joiner.join(self.predicate(x) for x in p.parts) + ")"
        raise TemplateError(f"unknown predicate kind {p.kind!r}")

    def from_where(self, extra: Sequence[str] = ()) -> str:
        clauses = list(self.where) + list(extra)
        return f" FROM {self.source}" + (" WHERE " + " AND ".join(f"({c})" for c in clauses) if clauses else "")

    def limited(self, select: str, rest: str, limit: int) -> str:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise TemplateError("limit must be a positive integer")
        if self.dialect == "mssql":
            return f"SELECT TOP ({limit}) {select}{rest}"
        if self.dialect == "oracle":
            return f"SELECT {select}{rest} FETCH FIRST {limit} ROWS ONLY"
        return f"SELECT {select}{rest} LIMIT {limit}"


def render(template: str, *, dialect: str, obj: str, allowed: Sequence[str], filters: Sequence[dict[str, Any]] = (),
           version: int | None = None, sensitive: Sequence[str] = (), **args: Any) -> Rendered:
    """Render one named template; raise :class:`TemplateError` on any invalid input."""
    b = _Builder(dialect, obj, allowed, version, filters, sensitive)
    max_rows = 1
    if template == "count_rows":
        sql = "SELECT COUNT(*) AS n" + b.from_where()
    elif template == "column_summary":
        c = b.col(args["column"])
        numeric = args.get("numeric", False)
        select = (f"COUNT(*) AS n, COUNT({c}) AS non_null, COUNT(DISTINCT {c}) AS distinct_n, "
                  f"MIN({c}) AS min_v, MAX({c}) AS max_v" + (f", SUM({c}) AS sum_v" if numeric else ""))
        sql = "SELECT " + select + b.from_where()
    elif template == "group_counts":
        g = b.col(args["column"])
        max_rows = args["limit"]
        sql = b.limited(f"{g} AS grp, COUNT(*) AS n", b.from_where() + f" GROUP BY {g} ORDER BY n DESC, grp",
                        max_rows + 1)
    elif template == "nulls_by_group":
        c, g = b.col(args["column"]), b.col(args["group"])
        max_rows = args["limit"]
        sql = b.limited(f"{g} AS grp, COUNT(*) AS n, SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) AS nulls",
                        b.from_where() + f" GROUP BY {g} ORDER BY grp", max_rows + 1)
    elif template == "key_repeats":
        keys = [b.col(k) for k in args["keys"]]
        if not keys:
            raise TemplateError("key_repeats needs keys")
        inner = f"SELECT {', '.join(keys)}, COUNT(*) AS n" + b.from_where() + \
            f" GROUP BY {', '.join(keys)} HAVING COUNT(*) > 1"
        sql = f"SELECT COUNT(*) AS repeated_keys, COALESCE(SUM(n), 0) AS rows_in_repeats FROM ({inner}) t"
    elif template == "key_missing":
        keys = [b.col(k) for k in args["keys"]]
        cond = " OR ".join(f"{k} IS NULL" for k in keys)
        sql = "SELECT COUNT(*) AS missing_key_rows" + b.from_where([cond])
    elif template == "rule_counts":
        violated = b.predicate(args["violation"])
        applicable = b.predicate(args["applicable"])
        sql = (f"SELECT COUNT(*) AS n, SUM(CASE WHEN {applicable} THEN 1 ELSE 0 END) AS applicable, "
               f"SUM(CASE WHEN {applicable} AND {violated} THEN 1 ELSE 0 END) AS violations" + b.from_where())
    elif template == "rule_counts_by_group":
        g = b.col(args["group"])
        violated = b.predicate(args["violation"])
        applicable = b.predicate(args["applicable"])
        max_rows = args["limit"]
        sql = b.limited(f"{g} AS grp, COUNT(*) AS n, SUM(CASE WHEN {applicable} THEN 1 ELSE 0 END) AS applicable, "
                        f"SUM(CASE WHEN {applicable} AND {violated} THEN 1 ELSE 0 END) AS violations",
                        b.from_where() + f" GROUP BY {g} ORDER BY grp", max_rows + 1)
    elif template == "segment_numeric":
        c, g = b.col(args["column"]), b.col(args["group"])
        max_rows = args["limit"]
        sql = b.limited(f"{g} AS grp, COUNT(*) AS n, COUNT({c}) AS non_null, MIN({c}) AS min_v, "
                        f"MAX({c}) AS max_v, SUM({c}) AS sum_v",
                        b.from_where() + f" GROUP BY {g} ORDER BY grp", max_rows + 1)
    elif template == "consistency":
        change = args.get("change_column")
        select = "COUNT(*) AS n" + (f", MAX({b.col(change)}) AS max_change" if change else "")
        sql = "SELECT " + select + b.from_where()
    elif template == "extract":
        cols = [b.col(c) for c in args["columns"]]
        order = [b.col(c) for c in args["order_by"]]
        if not cols or not order:
            raise TemplateError("extract needs explicit columns and ordering")
        max_rows = args["limit"]
        sql = b.limited(", ".join(cols), b.from_where() + " ORDER BY " + ", ".join(order), max_rows + 1)
    else:
        raise TemplateError(f"unknown template {template!r}")
    rendered = Rendered(template, sql, tuple(b.params), tuple(b.sensitive_idx), max_rows)
    check_rendered(rendered, dialect=dialect, obj=obj, allowed=allowed)
    return rendered


def check_rendered(rendered: Rendered, *, dialect: str, obj: str, allowed: Sequence[str]) -> None:
    """Static check every rendered statement must pass before execution."""
    structure = extract(rendered.sql, "sqlite" if dialect == "mssql" else dialect)
    if structure["statement_count"] != 1 or not structure["read_only_shape"]:
        raise TemplateError("rendered SQL is not a single read-only statement")
    if structure["write_keywords"]:
        raise TemplateError(f"rendered SQL contains write keywords {structure['write_keywords']}")
    obj_parts = {p.lower() for p in obj.split(".")} | {obj.lower()}
    names = {a.lower() for a in allowed} | _ALIASES | _FUNCTIONS | obj_parts
    for tok in tokenize(rendered.sql, "sqlite" if dialect == "mssql" else dialect):
        if tok.kind == "string":
            raise TemplateError("rendered SQL may not contain string literals")
        if tok.kind == "name":
            for part in tok.parts:
                if part != "*" and part not in names:
                    raise TemplateError(f"rendered SQL references unexpected name {part!r}")
        if tok.kind == "param" and not re.fullmatch(r":p\d+", tok.value):
            raise TemplateError("rendered SQL may only use the template's own named parameters")
    if len(structure["params"]) != len(rendered.params):
        raise TemplateError("parameter count mismatch")
