"""Deterministic SQL structure extraction for learning from a query repository.

Spec ``0114`` REQ-005 (realizing ``0113`` REQ-006). A standard-library
tokenizer and a small clause reader turn one query into the structure later
phases learn from: statement count and kind, CTE names, base tables and
aliases, join edges with keys, parameters and their style, filter columns and
operators, select-list metric expressions, and a normalized SQL hash.

This is **learning, not verification**. It is heuristic by design and
records what it could not resolve in ``unresolved``; it never decides
whether a query is safe to run. That is ``0116``'s fail-closed verifier.
Literal values never leave this module: filters carry ``<literal>``.

Quoting rules covered: ``'strings'`` (``''`` escape), ``"identifiers"``
(PostgreSQL, Oracle, SQLite), ```backticks``` (Databricks), ``[brackets]``
(SQLite only); parameters ``:name`` (SQLite, Oracle, Databricks),
``%(name)s`` (psycopg), ``?`` and ``$1``; ``--`` and ``/* */`` comments.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = ["SqlStructureError", "Token", "extract", "tokenize"]

KEYWORDS = frozenset("""
SELECT FROM WHERE JOIN INNER LEFT RIGHT FULL OUTER CROSS NATURAL LATERAL ON USING AS GROUP BY
ORDER HAVING LIMIT OFFSET FETCH FIRST NEXT ROWS ROW ONLY UNION ALL INTERSECT EXCEPT MINUS
DISTINCT WITH RECURSIVE AND OR NOT IN IS NULL LIKE ILIKE BETWEEN CASE WHEN THEN ELSE END EXISTS
INSERT UPDATE DELETE MERGE INTO VALUES SET CREATE ALTER DROP TRUNCATE GRANT REVOKE CALL EXEC
EXECUTE COPY QUALIFY WINDOW OVER PARTITION ASC DESC NULLS TOP INTERVAL TRUE FALSE
""".split())
WRITE_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "ALTER", "DROP", "TRUNCATE",
                  "GRANT", "REVOKE", "CALL", "EXEC", "EXECUTE", "COPY")
AGGREGATES = ("SUM", "COUNT", "AVG", "MIN", "MAX")
JOIN_PREFIX = ("INNER", "LEFT", "RIGHT", "FULL", "OUTER", "CROSS", "NATURAL", "LATERAL")
CLAUSE_END = frozenset({"WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET", "FETCH", "UNION",
                        "INTERSECT", "EXCEPT", "MINUS", "QUALIFY", "WINDOW", "JOIN", "ON", "USING",
                        *JOIN_PREFIX})
COMPARISON = ("=", "<>", "!=", "<", "<=", ">", ">=")


class SqlStructureError(ValueError):
    """Raised only for input the tokenizer cannot read at all (unterminated text)."""


@dataclass(frozen=True)
class Token:
    kind: str            # name | kw | param | string | number | op | punct
    value: str           # names are lower-cased dotted paths; keywords upper
    raw: str
    pos: int
    parts: Tuple[str, ...] = ()


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$#]*")
_NUMBER_RE = re.compile(r"(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?")
_OPS = ("<=", ">=", "<>", "!=", "||", "::", "=", "<", ">", "+", "-", "*", "/", "%")


def _raw_tokens(sql: str, dialect: str) -> List[Tuple[str, str, int]]:
    out: List[Tuple[str, str, int]] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch.isspace():
            i += 1
            continue
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            if j < 0:
                raise SqlStructureError("unterminated /* comment")
            i = j + 2
            continue
        if ch == "'":
            j = i + 1
            while True:
                j = sql.find("'", j)
                if j < 0:
                    raise SqlStructureError("unterminated string literal")
                if sql.startswith("''", j):
                    j += 2
                    continue
                break
            out.append(("string", sql[i:j + 1], i))
            i = j + 1
            continue
        if ch in ('"', "`") or (ch == "[" and dialect == "sqlite"):
            close = {'"': '"', "`": "`", "[": "]"}[ch]
            j = i + 1
            while True:
                j = sql.find(close, j)
                if j < 0:
                    raise SqlStructureError("unterminated quoted identifier")
                if close != "]" and sql.startswith(close * 2, j):
                    j += 2
                    continue
                break
            out.append(("qident", sql[i + 1:j].replace(close * 2, close), i))
            i = j + 1
            continue
        if ch == ":" and sql.startswith("::", i):
            out.append(("op", "::", i))
            i += 2
            continue
        if ch == ":" and i + 1 < n and (sql[i + 1].isalpha() or sql[i + 1] == "_"):
            m = _IDENT_RE.match(sql, i + 1)
            assert m
            out.append(("param", ":" + m.group(0), i))
            i = m.end()
            continue
        if sql.startswith("%(", i):
            m = re.compile(r"%\(([A-Za-z_][A-Za-z0-9_]*)\)s").match(sql, i)
            if m:
                out.append(("param", "%(" + m.group(1) + ")s", i))
                i = m.end()
                continue
        if ch == "?":
            out.append(("param", "?", i))
            i += 1
            continue
        if ch == "$" and i + 1 < n and sql[i + 1].isdigit():
            m = re.compile(r"\$\d+").match(sql, i)
            assert m
            out.append(("param", m.group(0), i))
            i = m.end()
            continue
        m = _NUMBER_RE.match(sql, i)
        if m and (ch.isdigit() or (ch == "." and i + 1 < n and sql[i + 1].isdigit())):
            out.append(("number", m.group(0), i))
            i = m.end()
            continue
        m = _IDENT_RE.match(sql, i)
        if m:
            out.append(("ident", m.group(0), i))
            i = m.end()
            continue
        op = next((o for o in _OPS if sql.startswith(o, i)), None)
        if op:
            out.append(("op", op, i))
            i += len(op)
            continue
        if ch in "(),;.":
            out.append(("punct", ch, i))
            i += 1
            continue
        out.append(("other", ch, i))
        i += 1
    return out


def tokenize(sql: str, dialect: str = "sqlite") -> List[Token]:
    """Tokens with dotted names merged and keywords recognized."""
    raw = _raw_tokens(sql, dialect)
    tokens: List[Token] = []
    i = 0
    while i < len(raw):
        kind, value, pos = raw[i]
        if kind in ("ident", "qident"):
            parts = [value]
            quoted = kind == "qident"
            j = i + 1
            while j + 1 < len(raw) and raw[j] == ("punct", ".", raw[j][2]) and (
                    raw[j + 1][0] in ("ident", "qident") or raw[j + 1][1] == "*"):
                parts.append(raw[j + 1][1])
                quoted = quoted or raw[j + 1][0] == "qident"
                j += 2
            text = sql[pos:raw[j - 1][2] + len(raw[j - 1][1]) + (2 if raw[j - 1][0] == "qident" else 0)]
            if len(parts) == 1 and not quoted and value.upper() in KEYWORDS:
                tokens.append(Token("kw", value.upper(), value, pos))
            else:
                norm = tuple(p.lower() if p != "*" else p for p in parts)
                tokens.append(Token("name", ".".join(norm), text, pos, norm))
            i = j
            continue
        tokens.append(Token(kind, value, value, pos))
        i += 1
    return tokens


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _is_kw(tok: Optional[Token], *words: str) -> bool:
    return tok is not None and tok.kind == "kw" and tok.value in words


def _is_p(tok: Optional[Token], ch: str) -> bool:
    return tok is not None and tok.kind == "punct" and tok.value == ch


def _render(tokens: Sequence[Token], names: Optional[Dict[int, str]] = None) -> str:
    """Canonical text: string literals redacted, names optionally replaced.

    Numeric constants are kept (a day-count ``360`` is part of a metric's
    definition); string literals never are.
    """
    out: List[str] = []
    prev: Optional[Token] = None
    for k, t in enumerate(tokens):
        text = "<literal>" if t.kind == "string" else (names or {}).get(k, t.value)
        glue = prev is None or _is_p(t, ")") or _is_p(t, ",") or _is_p(prev, "(") or (
            _is_p(t, "(") and prev.kind in ("name", "kw"))
        out.append(text if glue else " " + text)
        prev = t
    return "".join(out).strip()


class _Reader:
    def __init__(self, tokens: List[Token]) -> None:
        self.t = tokens
        self.depth = [0] * len(tokens)
        d = 0
        for i, tok in enumerate(tokens):
            if _is_p(tok, ")"):
                d -= 1
            self.depth[i] = d
            if _is_p(tok, "("):
                d += 1
        self.scope = [-1] * len(tokens)          # index of the enclosing "(" (-1 at top)
        stack: List[int] = []
        for i, tok in enumerate(tokens):
            if _is_p(tok, ")") and stack:
                stack.pop()
            self.scope[i] = stack[-1] if stack else -1
            if _is_p(tok, "("):
                stack.append(i)
        self.scope_targets: Dict[int, List[str]] = {}
        self.ctes: List[str] = []
        self.cte_body: Dict[str, int] = {}       # CTE name -> index of its body's "("
        self.tables: List[str] = []
        self.aliases: Dict[str, str] = {}
        self.ambiguous: set = set()
        self.joins: Dict[Tuple[str, str], set] = {}
        self.filters: set = set()
        self.unresolved: List[str] = []

    def tok(self, i: int) -> Optional[Token]:
        return self.t[i] if 0 <= i < len(self.t) else None

    def matching(self, i: int) -> int:
        """Index of the ``)`` closing the ``(`` at ``i``."""
        d = 0
        for j in range(i, len(self.t)):
            if _is_p(self.t[j], "("):
                d += 1
            elif _is_p(self.t[j], ")"):
                d -= 1
                if d == 0:
                    return j
        return len(self.t) - 1

    # -- CTEs ----------------------------------------------------------
    def read_ctes(self) -> None:
        for i, tok in enumerate(self.t):
            if not _is_kw(tok, "WITH"):
                continue
            j = i + 1
            if _is_kw(self.tok(j), "RECURSIVE"):
                j += 1
            while True:
                name = self.tok(j)
                if name is None or name.kind != "name":
                    break
                j += 1
                if _is_p(self.tok(j), "("):           # column list
                    j = self.matching(j) + 1
                if not _is_kw(self.tok(j), "AS"):
                    break
                j += 1
                if not _is_p(self.tok(j), "("):
                    break
                self.ctes.append(name.value)
                self.cte_body[name.value] = j
                j = self.matching(j) + 1
                if _is_p(self.tok(j), ","):
                    j += 1
                    continue
                break

    # -- table references ---------------------------------------------
    def bind(self, alias: str, target: str) -> None:
        previous = self.aliases.get(alias)
        if previous is not None and previous != target:
            self.ambiguous.add(alias)
        self.aliases[alias] = target

    def table_ref(self, i: int) -> Tuple[int, Optional[str]]:
        """Read one table reference at ``i``; return (next index, table or None)."""
        start = i
        tok = self.tok(i)
        if _is_kw(tok, "LATERAL"):
            i += 1
            tok = self.tok(i)
        target: Optional[str] = None
        if _is_p(tok, "("):
            i = self.matching(i) + 1
            target = None                               # derived table
        elif tok is not None and tok.kind == "name":
            if _is_p(self.tok(i + 1), "("):             # table function
                i = self.matching(i + 1) + 1
            else:
                target = tok.value
                if target not in self.ctes and target not in self.tables:
                    self.tables.append(target)
                i += 1
        else:
            return i, None
        if target is not None:
            bucket = self.scope_targets.setdefault(self.scope[start], [])
            if target not in bucket:
                bucket.append(target)
        alias_tok = self.tok(i)
        if _is_kw(alias_tok, "AS"):
            i += 1
            alias_tok = self.tok(i)
        if alias_tok is not None and alias_tok.kind == "name" and len(alias_tok.parts) == 1:
            if target is not None:
                self.bind(alias_tok.value, target)
            i += 1
        if target is not None:
            self.bind(target, target)
            self.bind(target.split(".")[-1], target)
        return i, target

    def read_from_clauses(self) -> None:
        i = 0
        while i < len(self.t):
            tok = self.t[i]
            if _is_kw(tok, "FROM"):
                depth = self.depth[i]
                prev_table: Optional[str] = None
                i, prev_table = self.table_ref(i + 1)
                while _is_p(self.tok(i), ",") and self.depth[i] == depth:
                    i, t = self.table_ref(i + 1)
                    prev_table = t or prev_table
                # joins at this depth
                while i < len(self.t) and self.depth[i] == depth:
                    k = i
                    join_type = []
                    while _is_kw(self.tok(k), *JOIN_PREFIX):
                        join_type.append(self.t[k].value)
                        k += 1
                    if not _is_kw(self.tok(k), "JOIN"):
                        break
                    kind = "inner"
                    for word in ("LEFT", "RIGHT", "FULL", "CROSS"):
                        if word in join_type:
                            kind = word.lower()
                    i, right = self.table_ref(k + 1)
                    if _is_kw(self.tok(i), "ON"):
                        end = self.clause_end(i + 1, depth)
                        self.read_condition(i + 1, end, kind)
                        i = end
                    elif _is_kw(self.tok(i), "USING") and _is_p(self.tok(i + 1), "("):
                        close = self.matching(i + 1)
                        for c in self.t[i + 2:close]:
                            if c.kind == "name" and prev_table and right:
                                self.add_join(f"{self.through_cte(prev_table)}.{c.value}",
                                              f"{self.through_cte(right)}.{c.value}", kind)
                        i = close + 1
                    prev_table = right or prev_table
                continue
            i += 1

    def clause_end(self, start: int, depth: int) -> int:
        j = start
        while j < len(self.t):
            tok = self.t[j]
            if self.depth[j] < depth or (_is_p(tok, ")") and self.depth[j] <= depth):
                return j
            if self.depth[j] == depth and (_is_p(tok, ";") or (tok.kind == "kw" and tok.value in CLAUSE_END)):
                return j
            j += 1
        return j

    # -- columns, joins, filters ----------------------------------------
    def resolve(self, name: Token, index: Optional[int] = None) -> Optional[str]:
        parts = name.parts
        if len(parts) >= 2:
            qualifier, column = ".".join(parts[:-1]), parts[-1]
            if qualifier in self.ambiguous:
                self.unresolved.append(f"ambiguous alias {qualifier!r} in {name.value}")
                return None
            table = self.aliases.get(qualifier)
            if table is None and qualifier in self.ctes:
                table = qualifier
            if table is None:
                self.unresolved.append(f"unknown qualifier {qualifier!r} in {name.value}")
                return None
            return f"{self.through_cte(table)}.{column}"
        if index is not None:
            in_scope = self.scope_targets.get(self.scope[index], [])
            if len(in_scope) == 1:
                return f"{self.through_cte(in_scope[0])}.{parts[0]}"
        if len(self.tables) == 1 and not self.ctes:
            return f"{self.tables[0]}.{parts[0]}"
        self.unresolved.append(f"unqualified column {parts[0]!r} is ambiguous in its scope")
        return None

    def through_cte(self, table: str) -> str:
        """A CTE that reads one base table stands for that table (else itself)."""
        seen = set()
        while table in self.cte_body and table not in seen:
            seen.add(table)
            targets = self.scope_targets.get(self.cte_body[table], [])
            if len(targets) != 1:
                break
            table = targets[0]
        return table

    def add_join(self, left: str, right: str, kind: str) -> None:
        if left.split(".")[:-1] == right.split(".")[:-1]:
            return
        key = tuple(sorted((left, right)))
        self.joins.setdefault(key, set()).add(kind)  # type: ignore[arg-type]

    def _value(self, j: int) -> Tuple[Optional[str], int]:
        tok = self.tok(j)
        if tok is None:
            return None, j
        if tok.kind == "param":
            return tok.value, j + 1
        if tok.kind in ("string", "number") or _is_kw(tok, "TRUE", "FALSE"):
            return "<literal>", j + 1
        if _is_kw(tok, "NULL"):
            return "NULL", j + 1
        if _is_p(tok, "("):
            close = self.matching(j)
            inner = self.t[j + 1:close]
            if any(_is_kw(x, "SELECT") for x in inner):
                return "<subquery>", close + 1
            values = sorted({x.value if x.kind == "param" else "<literal>"
                             for x in inner if x.kind in ("param", "string", "number")})
            return ",".join(values) or None, close + 1
        return None, j

    def read_condition(self, start: int, end: int, join_kind: Optional[str]) -> None:
        j = start
        while j < end:
            tok = self.t[j]
            if tok.kind == "name" and not _is_p(self.tok(j + 1), "(") and not _is_p(self.tok(j - 1), "."):
                nxt = self.tok(j + 1)
                # column = column  -> join edge
                if nxt is not None and nxt.kind == "op" and nxt.value == "=":
                    other = self.tok(j + 2)
                    if other is not None and other.kind == "name" and not _is_p(self.tok(j + 3), "("):
                        left, right = self.resolve(tok, j), self.resolve(other, j + 2)
                        if left and right:
                            self.add_join(left, right, join_kind or "inner")
                        j += 3
                        continue
                op: Optional[str] = None
                k = j + 1
                if nxt is not None and nxt.kind == "op" and nxt.value in COMPARISON:
                    op, k = nxt.value, j + 2
                elif _is_kw(nxt, "NOT") and _is_kw(self.tok(j + 2), "IN", "LIKE", "ILIKE", "BETWEEN"):
                    op, k = "NOT " + self.t[j + 2].value, j + 3
                elif _is_kw(nxt, "IN", "LIKE", "ILIKE", "BETWEEN"):
                    op, k = nxt.value, j + 2
                elif _is_kw(nxt, "IS"):
                    op = "IS NOT" if _is_kw(self.tok(j + 2), "NOT") else "IS"
                    k = j + 3 if op == "IS NOT" else j + 2
                if op:
                    value, k2 = self._value(k)
                    if op.endswith("BETWEEN") and _is_kw(self.tok(k2), "AND"):
                        high, k2 = self._value(k2 + 1)
                        value = f"{value}..{high}"
                    column = self.resolve(tok, j)
                    if column and value is not None:
                        self.filters.add((column, op, value))
                    j = max(k2, j + 1)
                    continue
            j += 1

    def read_where_clauses(self) -> None:
        for i, tok in enumerate(self.t):
            if _is_kw(tok, "WHERE", "HAVING", "QUALIFY"):
                self.read_condition(i + 1, self.clause_end(i + 1, self.depth[i]), None)

    # -- select list ----------------------------------------------------
    def select_items(self) -> List[Dict[str, Any]]:
        start = next((i for i, tok in enumerate(self.t) if _is_kw(tok, "SELECT") and self.depth[i] == 0), None)
        if start is None:
            return []
        i = start + 1
        while _is_kw(self.tok(i), "DISTINCT", "ALL"):
            i += 1
        if _is_kw(self.tok(i), "TOP"):
            i += 2
        end = next((j for j in range(i, len(self.t)) if _is_kw(self.t[j], "FROM") and self.depth[j] == 0),
                   len(self.t))
        items: List[List[Tuple[int, Token]]] = [[]]
        for j in range(i, end):
            if _is_p(self.t[j], ",") and self.depth[j] == 0:
                items.append([])
            else:
                items[-1].append((j, self.t[j]))
        out = []
        for indexed in items:
            if not indexed:
                continue
            item = [t for _, t in indexed]
            positions = [j for j, _ in indexed]
            alias = None
            expr = item
            if len(item) >= 2 and _is_kw(item[-2], "AS") and item[-1].kind == "name":
                alias, expr = item[-1].value, item[:-2]
            elif (len(item) >= 2 and item[-1].kind == "name" and len(item[-1].parts) == 1
                  and (item[-2].kind in ("name", "number", "string") or _is_p(item[-2], ")") or _is_kw(item[-2], "END"))):
                alias, expr = item[-1].value, item[:-1]
            elif len(item) == 1 and item[0].kind == "name":
                alias = item[0].parts[-1]
            aggregates = sorted({t.value.upper() for k, t in enumerate(expr)
                                 if t.kind == "name" and t.value.upper() in AGGREGATES
                                 and k + 1 < len(expr) and _is_p(expr[k + 1], "(")})
            ratio = any(t.kind == "op" and t.value == "/" for t in expr)
            resolved: Dict[int, str] = {}
            for k, t in enumerate(expr):
                if t.kind == "name" and t.parts[-1] != "*" and not (k + 1 < len(expr) and _is_p(expr[k + 1], "(")):
                    column = self.resolve(t, positions[k])
                    if column:
                        resolved[k] = column
            columns = sorted(set(resolved.values()))
            out.append({
                "name": alias,
                "expression": _render(expr, resolved),
                "metric": bool(aggregates) or ratio,
                "aggregates": aggregates,
                "columns": columns,
            })
        return out


def extract(sql: str, dialect: str = "sqlite") -> Dict[str, Any]:
    """Structure of ``sql`` as a JSON-ready dict (see module docstring)."""
    tokens = tokenize(sql, dialect)
    statements: List[List[Token]] = [[]]
    depth = 0
    for tok in tokens:
        if _is_p(tok, "("):
            depth += 1
        elif _is_p(tok, ")"):
            depth -= 1
        if _is_p(tok, ";") and depth == 0:
            statements.append([])
        else:
            statements[-1].append(tok)
    statements = [s for s in statements if s]
    first = statements[0] if statements else []
    kind = first[0].value if first and first[0].kind == "kw" else (first[0].value.upper() if first else "")
    write_keywords = sorted({t.value for t in tokens if t.kind == "kw" and t.value in WRITE_KEYWORDS})
    if any(t.kind == "name" and t.value == "replace" for i, t in enumerate(tokens)
           if not (i + 1 < len(tokens) and _is_p(tokens[i + 1], "("))):
        write_keywords.append("REPLACE")

    reader = _Reader(first)
    reader.read_ctes()
    reader.read_from_clauses()
    reader.read_where_clauses()
    select = reader.select_items()

    named: List[str] = []
    styles = set()
    for tok in tokens:
        if tok.kind != "param":
            continue
        if tok.value.startswith(":"):
            styles.add("named_colon")
            name = tok.value[1:]
        elif tok.value.startswith("%("):
            styles.add("pyformat")
            name = tok.value[2:-2]
        elif tok.value == "?":
            styles.add("qmark")
            continue
        else:
            styles.add("numeric")
            name = tok.value
        if name not in named:
            named.append(name)
    style = "none" if not styles else (styles.pop() if len(styles) == 1 else "mixed")

    has_limit = any(_is_kw(t, "LIMIT") for t in first) or any(
        _is_kw(first[i], "FETCH") and _is_kw(first[i + 1] if i + 1 < len(first) else None, "FIRST", "NEXT")
        for i in range(len(first)))
    normalized = " ".join(t.value if t.kind != "string" else t.raw for t in tokens)
    return {
        "statement_count": len(statements),
        "statement_kind": kind,
        "read_only_shape": len(statements) == 1 and kind in ("SELECT", "WITH") and not write_keywords,
        "write_keywords": sorted(set(write_keywords)),
        "ctes": reader.ctes,
        "tables": sorted(reader.tables),
        "aliases": {k: v for k, v in sorted(reader.aliases.items()) if k != v},
        "joins": [{"left": l, "right": r, "join_types": sorted(kinds)}
                  for (l, r), kinds in sorted(reader.joins.items())],
        "params": named,
        "param_style": style,
        "positional_params": sum(1 for t in tokens if t.kind == "param" and t.value == "?"),
        "filters": [{"column": c, "op": o, "value": v} for c, o, v in sorted(reader.filters)],
        "select": select,
        "has_row_limit": has_limit,
        "normalized_sql_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "unresolved": sorted(set(reader.unresolved)),
    }
