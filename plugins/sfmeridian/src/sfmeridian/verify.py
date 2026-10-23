"""Fail-closed SQL verification and exact-context tokens (spec 0116).

This module is deliberately independent of database connections. It turns a
candidate read query into an in-memory :class:`VerifiedQuery` only after the
query passes structural, catalog, join, parameter, point-in-time, and limit
checks. The public token contains hashes and policy metadata, never raw SQL,
parameter values, credentials, or signing material.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .catalog import Resolver
from .sqlstructure import SqlStructureError, Token, extract, tokenize

__all__ = [
    "POLICY_VERSION", "TokenError", "VerificationFinding", "VerificationOutcome",
    "VerificationRecord", "VerificationRequest", "VerifiedQuery", "trusted_predicate_literals",
    "validate_token", "verify",
]

POLICY_VERSION = "sql-verify/1"
_TOKEN_VERSION = "v1"
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_FORBIDDEN_WORDS = frozenset({
    "ALTER", "ATTACH", "BEGIN", "CALL", "COMMIT", "COPY", "CREATE", "DELETE", "DETACH", "DROP",
    "EXEC", "EXECUTE", "GRANT", "INSERT", "MERGE", "PRAGMA", "REPLACE", "REVOKE", "ROLLBACK",
    "SAVEPOINT", "SET", "TRUNCATE", "UPDATE", "VACUUM",
})
_SAFE_JOIN_TYPES = frozenset({"inner", "left", "right", "full"})
_UNSUPPORTED_WORDS = frozenset({"EXCEPT", "INTERSECT", "MINUS", "QUALIFY", "RECURSIVE", "UNION", "WINDOW"})
_DIALECT_POLICIES = {
    "sqlite": {"parameter_style": "named_colon", "limit": "LIMIT", "quotes": frozenset({'"', "["})},
    "postgres": {"parameter_style": "pyformat", "limit": "LIMIT", "quotes": frozenset({'"'})},
    "oracle": {"parameter_style": "named_colon", "limit": "FETCH", "quotes": frozenset({'"'})},
    "databricks": {"parameter_style": "named_colon", "limit": "LIMIT", "quotes": frozenset({"`"})},
}


@dataclass(frozen=True)
class VerificationFinding:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class VerificationRequest:
    sql: str
    params: Mapping[str, Any]
    profile: str
    as_of: str | None = None
    pit_columns: tuple[str, ...] = ()
    require_pit: bool = False
    clearance: str = "public"
    composition_path: str = "reuse"
    query_id: str | None = None
    trusted_literal_hashes: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationRecord:
    sql_hash: str
    params_hash: str
    parameter_names: tuple[str, ...]
    profile: str
    dialect: str
    snapshot_id: str
    config_hash: str
    policy_version: str
    clearance: str
    composition_path: str
    query_id: str | None
    issued_at: int
    expires_at: int
    row_limit: int
    timeout_s: int
    explain_cost: float | None

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["parameter_names"] = list(self.parameter_names)
        return value


@dataclass(frozen=True)
class VerifiedQuery:
    """Private run-scoped query plus the safe signed public record."""

    sql: str
    params_json: str
    record: VerificationRecord
    token: str

    @property
    def params(self) -> dict[str, Any]:
        value = json.loads(self.params_json)
        if not isinstance(value, dict):  # pragma: no cover - constructed internally
            raise TypeError("verified parameters are not an object")
        return value

    def public(self) -> dict[str, Any]:
        return {"ok": True, "token": self.token, **self.record.as_dict()}


@dataclass(frozen=True)
class VerificationOutcome:
    ok: bool
    verified: VerifiedQuery | None
    findings: tuple[VerificationFinding, ...]

    def as_dict(self) -> dict[str, Any]:
        if self.verified is not None:
            return self.verified.public()
        return {"ok": False, "findings": [finding.as_dict() for finding in self.findings]}


class TokenError(ValueError):
    code = "E_EXEC_TOKEN"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"{self.code}: {message}")


def verify(
    request: VerificationRequest,
    *,
    profile: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    join_graph: Sequence[Mapping[str, Any]],
    config_hash: str,
    key_id: str,
    signing_key: bytes,
    now: int,
    ttl_s: int = 300,
    explainer: Callable[..., Mapping[str, Any]] | None = None,
) -> VerificationOutcome:
    """Verify ``request`` and issue an exact-context token, or findings."""
    _validate_signing_inputs(key_id, signing_key, now, ttl_s)
    findings: list[VerificationFinding] = []
    dialect = str(profile.get("dialect", ""))
    if request.profile != profile.get("id"):
        findings.append(VerificationFinding("E_VERIFY_TABLE_NOT_ALLOWED", "request profile does not match"))
    if not bool(profile.get("read_only")):
        findings.append(VerificationFinding("E_VERIFY_NOT_READ_ONLY", "database profile is not read-only"))
    if dialect not in _DIALECT_POLICIES:
        findings.append(VerificationFinding("E_VERIFY_UNKNOWN_IDENTIFIER", "unsupported SQL dialect"))

    try:
        structure = extract(request.sql, dialect)
        tokens = tokenize(request.sql, dialect)
    except (SqlStructureError, ValueError) as exc:
        findings.append(VerificationFinding("E_VERIFY_NOT_READ_ONLY", f"SQL could not be parsed: {type(exc).__name__}"))
        return VerificationOutcome(False, None, tuple(findings))

    if structure["statement_count"] != 1:
        findings.append(VerificationFinding("E_VERIFY_MULTI_STATEMENT", "exactly one statement is required"))
    if not structure["read_only_shape"]:
        findings.append(VerificationFinding("E_VERIFY_NOT_READ_ONLY", "statement is not a read-only SELECT"))
    forbidden = sorted({_word(token) for token in tokens if _word(token) in _FORBIDDEN_WORDS})
    if forbidden:
        findings.append(VerificationFinding(
            "E_VERIFY_NOT_READ_ONLY", f"forbidden SQL operation: {', '.join(forbidden)}"))
    unsupported = sorted({_word(token) for token in tokens if _word(token) in _UNSUPPORTED_WORDS})
    if unsupported:
        findings.append(VerificationFinding(
            "E_VERIFY_UNKNOWN_IDENTIFIER", f"unsupported SQL construct: {', '.join(unsupported)}"))

    resolver = Resolver(snapshot)
    canonical_tables: dict[str, str] = {}
    for table_ref in structure["tables"]:
        table, reason = resolver.table(table_ref)
        if table is None:
            findings.append(VerificationFinding("E_VERIFY_UNKNOWN_IDENTIFIER", reason or "unknown table"))
            continue
        label = Resolver.label(table)
        canonical_tables[table_ref] = label
        if not _table_allowed(label, profile):
            findings.append(VerificationFinding("E_VERIFY_TABLE_NOT_ALLOWED", f"table {label!r} is not allowed"))
    if not canonical_tables:
        findings.append(VerificationFinding("E_VERIFY_UNKNOWN_IDENTIFIER", "query has no catalog-resolved table"))

    if structure["unresolved"]:
        findings.extend(VerificationFinding("E_VERIFY_UNKNOWN_IDENTIFIER", item)
                        for item in structure["unresolved"])
    if any(item["expression"].strip() == "*" or item["expression"].strip().endswith(".*")
           for item in structure["select"]):
        findings.append(VerificationFinding("E_VERIFY_UNKNOWN_IDENTIFIER", "wildcard projections are not allowed"))

    referenced = set()
    for item in structure["select"]:
        referenced.update(item["columns"])
    referenced.update(item["column"] for item in structure["filters"])
    for edge in structure["joins"]:
        referenced.update((edge["left"], edge["right"]))
    for ref in sorted(referenced):
        if not resolver.column(ref).ok:
            reason = resolver.column(ref).reason or f"column {ref!r} does not resolve"
            findings.append(VerificationFinding("E_VERIFY_UNKNOWN_IDENTIFIER", reason))
    _check_clause_identifiers(tokens, structure, resolver, findings)

    _check_joins(structure, resolver, join_graph, findings)
    _check_dialect(dialect, structure, tokens, findings)
    _check_parameters(request, structure, tokens, findings)
    _check_pit(request, structure, resolver, findings)
    row_limit = _check_limit(
        tokens, request.params, int(profile.get("row_limit", 0)), dialect, findings)

    findings = _dedupe(findings)
    if findings:
        return VerificationOutcome(False, None, tuple(findings))

    explain_cost = _check_cost(request, profile, explainer, findings)
    if findings:
        return VerificationOutcome(False, None, tuple(findings))

    params_json = _canonical(request.params)
    record = VerificationRecord(
        sql_hash=str(structure["normalized_sql_hash"]),
        params_hash=_sha(params_json),
        parameter_names=tuple(sorted(request.params)),
        profile=request.profile,
        dialect=dialect,
        snapshot_id=str(snapshot["snapshot_id"]),
        config_hash=config_hash,
        policy_version=POLICY_VERSION,
        clearance=request.clearance,
        composition_path=request.composition_path,
        query_id=request.query_id,
        issued_at=now,
        expires_at=now + ttl_s,
        row_limit=row_limit,
        timeout_s=int(profile.get("timeout_s", 0)),
        explain_cost=explain_cost,
    )
    token = _issue(record, key_id, signing_key)
    return VerificationOutcome(True, VerifiedQuery(request.sql, params_json, record, token), ())


def validate_token(
    token: str,
    verified: VerifiedQuery,
    *,
    keys: Mapping[str, bytes],
    now: int,
) -> VerificationRecord:
    """Validate signature, expiry, and every binding against ``verified``."""
    try:
        version, key_id, payload_text, signature = token.split(".")
    except ValueError:
        raise TokenError("malformed verification token") from None
    if version != _TOKEN_VERSION:
        raise TokenError("unsupported verification token version")
    key = keys.get(key_id)
    if key is None:
        raise TokenError("unknown verification key")
    signed = f"{version}.{key_id}.{payload_text}".encode("ascii")
    expected_signature = _b64(hmac.new(key, signed, hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenError("verification token signature mismatch")
    try:
        payload = json.loads(_unb64(payload_text))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise TokenError("verification token payload is invalid") from None
    if not isinstance(payload, dict):
        raise TokenError("verification token payload is not an object")
    if now < verified.record.issued_at or now > verified.record.expires_at:
        raise TokenError("verification token is outside its validity window")

    try:
        current_hash = extract(verified.sql, verified.record.dialect)["normalized_sql_hash"]
    except (SqlStructureError, ValueError):
        raise TokenError("verified SQL no longer parses") from None
    current = verified.record.as_dict()
    current["sql_hash"] = current_hash
    current["params_hash"] = _sha(verified.params_json)
    params = verified.params
    current["parameter_names"] = sorted(params)
    if payload != current:
        raise TokenError("verification token context mismatch")
    return verified.record


def trusted_predicate_literals(sql: str, dialect: str) -> tuple[str, ...]:
    """Hashes of predicate literals in a reviewed SQL exemplar.

    Composition may pass these hashes back only when it reuses/adapts that
    reviewed exemplar. Values are never exposed by the hash list.
    """
    tokens = tokenize(sql, dialect)
    return tuple(sorted({_literal_hash(token) for i, token in enumerate(tokens)
                         if token.kind in ("string", "number") and _is_predicate_value(tokens, i)}))


def _check_joins(structure: Mapping[str, Any], resolver: Resolver, join_graph: Sequence[Mapping[str, Any]],
                 findings: list[VerificationFinding]) -> None:
    tables = set(structure["tables"])
    edges = structure["joins"]
    if len(tables) > 1 and len(edges) < len(tables) - 1:
        findings.append(VerificationFinding("E_VERIFY_JOIN_KEY", "every joined table needs a resolved key edge"))
    allowed: set[tuple[str, str]] = set()
    for edge in join_graph:
        if int(edge.get("support", 0)) <= 0:
            continue
        pair = _canonical_edge(resolver, str(edge.get("left", "")), str(edge.get("right", "")))
        if pair:
            allowed.add(pair)
    for edge in edges:
        if not set(edge.get("join_types", ())) <= _SAFE_JOIN_TYPES:
            findings.append(VerificationFinding("E_VERIFY_JOIN_KEY", "cross, natural, or lateral joins are refused"))
            continue
        pair = _canonical_edge(resolver, edge["left"], edge["right"])
        if pair is None or pair not in allowed:
            findings.append(VerificationFinding(
                "E_VERIFY_JOIN_KEY", f"join {edge['left']} = {edge['right']} is not a reviewed key"))


def _check_clause_identifiers(tokens: Sequence[Token], structure: Mapping[str, Any], resolver: Resolver,
                              findings: list[VerificationFinding]) -> None:
    """Resolve identifiers in GROUP/ORDER/HAVING clauses the extractor does not expose."""
    aliases = {str(key).lower(): str(value) for key, value in structure["aliases"].items()}
    outputs = {str(item["name"]).lower() for item in structure["select"] if item.get("name")}
    tables = list(structure["tables"])
    depths = _depths(tokens)
    starts: list[tuple[int, int]] = []
    for i, token in enumerate(tokens):
        if token.kind == "kw" and token.value in ("GROUP", "ORDER"):
            if i + 1 < len(tokens) and tokens[i + 1].kind == "kw" and tokens[i + 1].value == "BY":
                starts.append((i + 2, depths[i]))
        elif token.kind == "kw" and token.value in ("HAVING", "QUALIFY"):
            starts.append((i + 1, depths[i]))
    for start, depth in starts:
        end = len(tokens)
        for j in range(start, len(tokens)):
            if depths[j] < depth:
                end = j
                break
            if depths[j] == depth and tokens[j].kind == "kw" and tokens[j].value in (
                    "FETCH", "GROUP", "HAVING", "LIMIT", "ORDER", "QUALIFY", "UNION", "WINDOW"):
                end = j
                break
        for j in range(start, end):
            token = tokens[j]
            if token.kind != "name" or (j + 1 < len(tokens) and tokens[j + 1].value == "("):
                continue
            if token.value.lower() in outputs:
                continue
            refs: list[str] = []
            if len(token.parts) >= 2:
                qualifier = ".".join(token.parts[:-1]).lower()
                refs = [f"{aliases.get(qualifier, qualifier)}.{token.parts[-1]}"]
            else:
                refs = [f"{table}.{token.parts[0]}" for table in tables]
            resolved = [resolver.column(ref) for ref in refs]
            matches = [item for item in resolved if item.ok]
            if len(matches) != 1:
                findings.append(VerificationFinding(
                    "E_VERIFY_UNKNOWN_IDENTIFIER", f"clause identifier {token.value!r} is unknown or ambiguous"))


def _depths(tokens: Sequence[Token]) -> list[int]:
    out: list[int] = []
    depth = 0
    for token in tokens:
        if token.kind == "punct" and token.value == ")":
            depth -= 1
        out.append(depth)
        if token.kind == "punct" and token.value == "(":
            depth += 1
    return out


def _check_dialect(dialect: str, structure: Mapping[str, Any], tokens: Sequence[Token],
                   findings: list[VerificationFinding]) -> None:
    policy = _DIALECT_POLICIES.get(dialect)
    if policy is None:
        return
    if structure["params"] and structure["param_style"] != policy["parameter_style"]:
        findings.append(VerificationFinding(
            "E_VERIFY_UNBOUND_PARAM", f"{dialect} requires {policy['parameter_style']} parameters"))
    quote_chars = {'"', "`", "["}
    used_quotes = {char for token in tokens if token.kind == "name"
                   for char in quote_chars if char in token.raw}
    if not used_quotes <= policy["quotes"]:
        findings.append(VerificationFinding(
            "E_VERIFY_UNKNOWN_IDENTIFIER", f"identifier quoting is not valid for {dialect}"))


def _check_parameters(request: VerificationRequest, structure: Mapping[str, Any], tokens: Sequence[Token],
                      findings: list[VerificationFinding]) -> None:
    if structure["positional_params"] or structure["param_style"] in ("mixed", "numeric", "qmark"):
        findings.append(VerificationFinding("E_VERIFY_UNBOUND_PARAM", "named parameters are required"))
    used, supplied = set(structure["params"]), set(request.params)
    if used != supplied:
        missing, extra = sorted(used - supplied), sorted(supplied - used)
        message = f"parameter mismatch; missing={missing}, extra={extra}"
        findings.append(VerificationFinding("E_VERIFY_UNBOUND_PARAM", message))
    trusted = set(request.trusted_literal_hashes)
    found = {_literal_hash(token) for i, token in enumerate(tokens)
             if token.kind in ("string", "number") and _is_predicate_value(tokens, i)}
    if not found <= trusted:
        findings.append(VerificationFinding(
            "E_VERIFY_UNBOUND_PARAM", "predicate values must be bound or match a reviewed exemplar literal"))
    if any("<subquery>" in item["value"] for item in structure["filters"]):
        findings.append(VerificationFinding("E_VERIFY_UNKNOWN_IDENTIFIER", "predicate subqueries are not supported"))


def _check_pit(request: VerificationRequest, structure: Mapping[str, Any], resolver: Resolver,
               findings: list[VerificationFinding]) -> None:
    if not request.require_pit:
        return
    if not request.as_of or request.params.get("as_of") != request.as_of:
        findings.append(VerificationFinding("E_VERIFY_MISSING_PIT", "as-of questions require a bound :as_of"))
        return
    filters: dict[str, set[str]] = {}
    for item in structure["filters"]:
        resolved = resolver.column(item["column"])
        if resolved.ok:
            key = f"{resolved.table}.{resolved.column}".lower()
            filters.setdefault(key, set()).add(item["value"])
    directly_bounded = {key for key, values in filters.items()
                        if any(":as_of" in value or "%(as_of)s" in value for value in values)}
    adjacency: dict[str, set[str]] = {}
    for edge in structure["joins"]:
        pair = _canonical_edge(resolver, edge["left"], edge["right"])
        if pair:
            left, right = pair
            adjacency.setdefault(left, set()).add(right)
            adjacency.setdefault(right, set()).add(left)
    bounded = set(directly_bounded)
    pending = list(directly_bounded)
    while pending:
        current = pending.pop()
        for other in adjacency.get(current, ()):
            if other not in bounded:
                bounded.add(other)
                pending.append(other)
    for ref in request.pit_columns:
        resolved = resolver.column(ref)
        if not resolved.ok:
            findings.append(VerificationFinding("E_VERIFY_MISSING_PIT", f"PIT column {ref!r} does not resolve"))
            continue
        key = f"{resolved.table}.{resolved.column}".lower()
        if key not in bounded:
            findings.append(VerificationFinding(
                "E_VERIFY_MISSING_PIT", f"PIT column {key!r} is not constrained by :as_of"))


def _check_limit(tokens: Sequence[Token], params: Mapping[str, Any], ceiling: int, dialect: str,
                 findings: list[VerificationFinding]) -> int:
    value: Any = None
    form: str | None = None
    for i, token in enumerate(tokens):
        if token.kind == "kw" and token.value == "LIMIT":
            form = "LIMIT"
            value = _limit_token(tokens[i + 1] if i + 1 < len(tokens) else None, params)
            break
        if token.kind == "kw" and token.value == "FETCH":
            j = i + 1
            if j < len(tokens) and tokens[j].value in ("FIRST", "NEXT"):
                form = "FETCH"
                value = _limit_token(tokens[j + 1] if j + 1 < len(tokens) else None, params)
                break
    expected = _DIALECT_POLICIES.get(dialect, {}).get("limit")
    if (form != expected or not isinstance(value, int) or isinstance(value, bool)
            or value <= 0 or ceiling <= 0 or value > ceiling):
        findings.append(VerificationFinding(
            "E_VERIFY_NO_LIMIT",
            f"row limit must use {expected or 'a supported form'} with a positive integer at or below {ceiling}"))
        return 0
    return value


def _check_cost(request: VerificationRequest, profile: Mapping[str, Any],
                explainer: Callable[..., Mapping[str, Any]] | None,
                findings: list[VerificationFinding]) -> float | None:
    limit = profile.get("explain_cost_limit")
    if limit is None:
        return None
    try:
        normalized_limit = float(limit)
    except (TypeError, ValueError, OverflowError):
        normalized_limit = math.nan
    if (isinstance(limit, bool) or not math.isfinite(normalized_limit) or normalized_limit <= 0):
        findings.append(VerificationFinding("E_VERIFY_COST", "configured explain cost limit is invalid"))
        return None
    if explainer is None:
        findings.append(VerificationFinding("E_VERIFY_COST", "cost guard requires an injected explainer"))
        return None
    try:
        result = explainer(
            request.sql, dict(request.params), timeout_s=int(profile.get("timeout_s", 0)))
    except Exception as exc:  # noqa: BLE001 — driver details and values must never escape
        findings.append(VerificationFinding(
            "E_VERIFY_COST", f"cost explanation failed: {type(exc).__name__}"))
        return None
    if not isinstance(result, Mapping) or not set(result) <= {"cost", "notes"}:
        findings.append(VerificationFinding("E_VERIFY_COST", "explainer returned an invalid normalized result"))
        return None
    cost = result.get("cost")
    notes = result.get("notes", ())
    try:
        normalized = float(cost)
    except (TypeError, ValueError, OverflowError):
        normalized = math.nan
    if (isinstance(cost, bool) or not math.isfinite(normalized) or normalized < 0
            or not isinstance(notes, (list, tuple))
            or not all(isinstance(note, str) for note in notes)):
        findings.append(VerificationFinding("E_VERIFY_COST", "explainer returned an invalid normalized result"))
        return None
    if normalized > normalized_limit:
        findings.append(VerificationFinding("E_VERIFY_COST", "normalized explain cost exceeds the configured limit"))
        return None
    return normalized


def _limit_token(token: Token | None, params: Mapping[str, Any]) -> Any:
    if token is None:
        return None
    if token.kind == "number" and token.raw.isdigit():
        return int(token.raw)
    if token.kind == "param":
        name = token.value[1:] if token.value.startswith(":") else token.value[2:-2]
        return params.get(name)
    return None


def _canonical_edge(resolver: Resolver, left: str, right: str) -> tuple[str, str] | None:
    a, b = resolver.column(left), resolver.column(right)
    if not a.ok or not b.ok:
        return None
    return tuple(sorted((f"{a.table}.{a.column}".lower(), f"{b.table}.{b.column}".lower())))


def _table_allowed(label: str, profile: Mapping[str, Any]) -> bool:
    schema, _, name = label.lower().rpartition(".")
    schemas = {str(value).lower() for value in profile.get("schemas_allowlist", ())}
    tables = {str(value).lower() for value in profile.get("tables_allowlist", ())}
    if schemas and schema not in schemas:
        return False
    return not tables or label.lower() in tables or name in tables


def _is_predicate_value(tokens: Sequence[Token], index: int) -> bool:
    previous = tokens[index - 1] if index else None
    if previous and previous.kind == "op" and previous.value in ("=", "<>", "!=", "<", "<=", ">", ">="):
        return True
    if previous and previous.kind == "kw" and previous.value in ("BETWEEN", "LIKE", "ILIKE"):
        return True
    # ``BETWEEN :low AND 10`` and values inside ``IN (...)``.
    if index >= 2 and tokens[index - 1].kind == "kw" and tokens[index - 1].value == "AND":
        return any(t.kind == "kw" and t.value == "BETWEEN" for t in tokens[max(0, index - 5):index])
    depth = 0
    for i in range(index - 1, max(-1, index - 12), -1):
        token = tokens[i]
        if token.kind == "punct" and token.value == ")":
            depth += 1
        elif token.kind == "punct" and token.value == "(":
            if depth == 0:
                return i > 0 and tokens[i - 1].kind == "kw" and tokens[i - 1].value == "IN"
            depth -= 1
        elif depth == 0 and token.kind == "kw" and token.value in ("WHERE", "HAVING", "ON"):
            break
    return False


def _literal_hash(token: Token) -> str:
    return _sha(f"{token.kind}:{token.raw}")


def _word(token: Token) -> str:
    return token.value.upper() if token.kind in ("kw", "name") else ""


def _dedupe(findings: Sequence[VerificationFinding]) -> list[VerificationFinding]:
    seen: set[tuple[str, str]] = set()
    out: list[VerificationFinding] = []
    for finding in findings:
        key = (finding.code, finding.message)
        if key not in seen:
            seen.add(key)
            out.append(finding)
    return out


def _validate_signing_inputs(key_id: str, signing_key: bytes, now: int, ttl_s: int) -> None:
    if not _KEY_ID_RE.fullmatch(key_id):
        raise ValueError("verification key ID must be 1..64 URL-safe characters")
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        raise ValueError("verification signing key must contain at least 32 bytes")
    if not isinstance(now, int) or isinstance(now, bool) or now < 0:
        raise ValueError("verification clock must return a non-negative integer")
    if not isinstance(ttl_s, int) or isinstance(ttl_s, bool) or not 1 <= ttl_s <= 3600:
        raise ValueError("verification token TTL must be 1..3600 seconds")


def _issue(record: VerificationRecord, key_id: str, signing_key: bytes) -> str:
    payload = _b64(_canonical(record.as_dict()).encode("utf-8"))
    signed = f"{_TOKEN_VERSION}.{key_id}.{payload}".encode("ascii")
    signature = _b64(hmac.new(signing_key, signed, hashlib.sha256).digest())
    return f"{_TOKEN_VERSION}.{key_id}.{payload}.{signature}"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> str:
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    return raw.decode("utf-8")
