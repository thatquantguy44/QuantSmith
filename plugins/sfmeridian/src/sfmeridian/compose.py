"""Retrieval-first SQL composition: reuse, then adapt, then generate.

Spec ``0116`` REQ-002.  Reviewed, primary, undrifted exemplars are the only
reusable evidence.  A high-confidence match is returned byte-for-byte as
``reuse``.  Lower-confidence evidence may be given to the injected completer
for ``adapt``; only when retrieval has no eligible hit may the completer
``generate``.  Every candidate is checked against the current catalog before
it can be handed to the independent verifier, and this module never writes to
the index or query repository.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .access import REDACTED, scrub
from .catalog import Resolver
from .index import Index, search
from .sqlstructure import SqlStructureError, extract
from .verify import VerificationRequest, trusted_predicate_literals

__all__ = [
    "CompositionError", "CompositionRecord", "CompositionRequest", "compose",
]

_REUSE_SCORE = 0.75


class CompositionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = scrub(message)
        super().__init__(f"{code}: {self.message}")


@dataclass(frozen=True)
class CompositionRequest:
    question: str
    profile: str
    params: Mapping[str, Any]
    as_of: str | None = None
    route_outcome: str = "no_governed_match"
    pit_columns: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompositionRecord:
    sql: str
    params_json: str
    path: str
    profile: str
    dialect: str
    as_of: str | None
    source_exemplars: tuple[Mapping[str, Any], ...]
    catalog_objects: tuple[str, ...]
    limitations: tuple[str, ...]
    query_id: str | None
    pit_columns: tuple[str, ...]
    trusted_literal_hashes: tuple[str, ...]

    @property
    def params(self) -> dict[str, Any]:
        value = json.loads(self.params_json)
        if not isinstance(value, dict):  # pragma: no cover - constructed internally
            raise TypeError("composition parameters are not an object")
        return value

    @property
    def content_hash(self) -> str:
        return f"sha256:{hashlib.sha256(_canonical(self._identity()).encode()).hexdigest()}"

    def as_dict(self) -> dict[str, Any]:
        params = self.params
        safe_params = {name: (value if name == "as_of" and value == self.as_of else REDACTED)
                       for name, value in sorted(params.items())}
        return {
            "sql": self.sql,
            "params": safe_params,
            "parameter_names": sorted(params),
            "path": self.path,
            "profile": self.profile,
            "dialect": self.dialect,
            "as_of": self.as_of,
            "source_exemplars": [dict(item) for item in self.source_exemplars],
            "catalog_objects": list(self.catalog_objects),
            "limitations": list(self.limitations),
            "query_id": self.query_id,
            "pit_columns": list(self.pit_columns),
            "content_hash": self.content_hash,
        }

    def verification_request(self, *, clearance: str = "public") -> VerificationRequest:
        return VerificationRequest(
            sql=self.sql,
            params=self.params,
            profile=self.profile,
            as_of=self.as_of,
            pit_columns=self.pit_columns,
            require_pit=self.as_of is not None,
            clearance=clearance,
            composition_path=self.path,
            query_id=self.query_id,
            trusted_literal_hashes=self.trusted_literal_hashes,
        )

    def _identity(self) -> dict[str, Any]:
        value = asdict(self)
        value["params_hash"] = hashlib.sha256(self.params_json.encode()).hexdigest()
        del value["params_json"]
        value["source_exemplars"] = [dict(item) for item in self.source_exemplars]
        value["catalog_objects"] = list(self.catalog_objects)
        value["limitations"] = list(self.limitations)
        value["pit_columns"] = list(self.pit_columns)
        value["trusted_literal_hashes"] = list(self.trusted_literal_hashes)
        return value


def compose(
    request: CompositionRequest,
    *,
    index: Index,
    profile: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    completer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    min_score: float = 0.05,
) -> CompositionRecord:
    """Compose one catalog-bound query without mutating retrieval state."""
    if request.route_outcome != "no_governed_match":
        raise CompositionError(
            "E_VERIFY_UNKNOWN_IDENTIFIER", "SQL composition requires a recorded no-governed-match route")
    if request.as_of is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", request.as_of):
        raise CompositionError("E_VERIFY_UNBOUND_PARAM", "as_of must be an ISO date YYYY-MM-DD")
    if request.profile != profile.get("id"):
        raise CompositionError("E_VERIFY_TABLE_NOT_ALLOWED", "composition profile does not match")
    dialect = str(profile.get("dialect", ""))
    hits = [hit for hit in search(
        index, request.question, limit=5, profile=request.profile, tags=request.tags,
        include_hints=False, min_score=min_score,
    ) if _eligible(hit.exemplar, dialect)]

    for hit in hits:
        bound = _bind(hit.exemplar, request)
        if bound is not None and _reuse_match(request.question, hit.score, hit.exemplar):
            sql = str(hit.exemplar["sql"])
            objects = _catalog_check(sql, dialect, profile, snapshot, bound)
            return _record(
                sql=sql, params=bound, path="reuse", profile=request.profile, dialect=dialect,
                as_of=request.as_of, exemplars=(hit.exemplar,), objects=objects, limitations=(),
                query_id=hit.exemplar.get("query_id"),
                pit_columns=tuple(hit.exemplar.get("pit_columns") or ()),
                trusted_literals=trusted_predicate_literals(sql, dialect),
            )

    mode = "adapt" if hits else "generate"
    if completer is None:
        raise CompositionError(
            "E_VERIFY_UNKNOWN_IDENTIFIER", f"no safe {mode} candidate without an injected completer")
    context = _completion_context(request, profile, snapshot, hits, mode)
    try:
        candidate = completer(context)
    except Exception as exc:  # noqa: BLE001 — model/provider detail must not escape
        raise CompositionError(
            "E_VERIFY_UNKNOWN_IDENTIFIER", f"composition completer failed: {type(exc).__name__}") from None
    if not isinstance(candidate, Mapping):
        raise CompositionError("E_VERIFY_UNKNOWN_IDENTIFIER", "composition completer returned no object")
    allowed = {"sql", "source_exemplar_ids", "limitations"}
    if not set(candidate) <= allowed or not isinstance(candidate.get("sql"), str):
        raise CompositionError("E_VERIFY_UNKNOWN_IDENTIFIER", "composition completer returned an invalid object")
    limitations = candidate.get("limitations", ())
    if (not isinstance(limitations, (list, tuple))
            or not all(isinstance(item, str) and item.strip() for item in limitations)):
        raise CompositionError("E_VERIFY_UNKNOWN_IDENTIFIER", "composition limitations must be non-empty strings")

    cited_ids = candidate.get("source_exemplar_ids", ())
    if not isinstance(cited_ids, (list, tuple)) or not all(isinstance(item, str) for item in cited_ids):
        raise CompositionError("E_VERIFY_UNKNOWN_IDENTIFIER", "source exemplar IDs must be strings")
    by_id = {str(hit.exemplar["exemplar_id"]): hit.exemplar for hit in hits}
    if mode == "adapt":
        if not cited_ids or not set(cited_ids) <= set(by_id):
            raise CompositionError(
                "E_VERIFY_UNKNOWN_IDENTIFIER", "adaptation must cite retrieved primary exemplars")
        cited = tuple(by_id[item] for item in sorted(set(cited_ids)))
    else:
        if cited_ids:
            raise CompositionError(
                "E_VERIFY_UNKNOWN_IDENTIFIER", "generated SQL cannot claim an unretrieved exemplar")
        cited = ()

    params = _request_params(request)
    sql = str(candidate["sql"]).strip()
    objects = _catalog_check(sql, dialect, profile, snapshot, params)
    structure = extract(sql, dialect)
    if mode == "adapt" and any(
            structure["normalized_sql_hash"] == item["normalized_sql_hash"] for item in cited):
        raise CompositionError("E_VERIFY_UNKNOWN_IDENTIFIER", "unchanged reviewed SQL must use the reuse path")
    if mode == "adapt":
        candidate_tables = {name.lower().split(".")[-1] for name in structure["tables"]}
        cited_tables = {name.lower().split(".")[-1] for item in cited
                        for name in item["structure"]["tables"]}
        if not candidate_tables & cited_tables:
            raise CompositionError(
                "E_VERIFY_UNKNOWN_IDENTIFIER", "adaptation must retain a cited exemplar source")
    trusted: set[str] = set()
    pit_columns = set(request.pit_columns)
    for item in cited:
        trusted.update(trusted_predicate_literals(str(item["sql"]), dialect))
        pit_columns.update(item.get("pit_columns") or ())
    return _record(
        sql=sql, params=params, path=mode, profile=request.profile, dialect=dialect,
        as_of=request.as_of, exemplars=cited, objects=objects,
        limitations=tuple(scrub(item) for item in limitations), query_id=None,
        pit_columns=tuple(sorted(pit_columns)), trusted_literals=tuple(sorted(trusted)),
    )


def _eligible(exemplar: Mapping[str, Any], dialect: str) -> bool:
    return (exemplar.get("eligibility") == "primary" and exemplar.get("review_status") == "reviewed"
            and exemplar.get("dialect") == dialect and isinstance(exemplar.get("sql"), str))


def _reuse_match(question: str, score: float, exemplar: Mapping[str, Any]) -> bool:
    normalized = " ".join(question.lower().split())
    exact = {" ".join(str(exemplar.get(key) or "").lower().split()) for key in ("query_id", "title", "intent")}
    return score >= _REUSE_SCORE or normalized in exact


def _bind(exemplar: Mapping[str, Any], request: CompositionRequest) -> dict[str, Any] | None:
    supplied = dict(request.params)
    if request.as_of is not None:
        if "as_of" in supplied and supplied["as_of"] != request.as_of:
            return None
        supplied["as_of"] = request.as_of
    declared = exemplar.get("params") or []
    names = {str(item.get("name")) for item in declared if isinstance(item, Mapping)}
    if set(supplied) - names:
        return None
    bound: dict[str, Any] = {}
    for item in declared:
        if not isinstance(item, Mapping):
            return None
        name = str(item.get("name"))
        if name in supplied:
            bound[name] = supplied[name]
        elif "default" in item:
            bound[name] = item["default"]
        elif item.get("required", True):
            return None
    return bound


def _request_params(request: CompositionRequest) -> dict[str, Any]:
    params = dict(request.params)
    if request.as_of is not None:
        if "as_of" in params and params["as_of"] != request.as_of:
            raise CompositionError("E_VERIFY_UNBOUND_PARAM", "as_of does not match the supplied parameter")
        params["as_of"] = request.as_of
    try:
        _canonical(params)
    except (TypeError, ValueError, OverflowError):
        raise CompositionError("E_VERIFY_UNBOUND_PARAM", "composition parameters are not canonical JSON") from None
    return params


def _catalog_check(sql: str, dialect: str, profile: Mapping[str, Any],
                   snapshot: Mapping[str, Any], params: Mapping[str, Any]) -> tuple[str, ...]:
    try:
        structure = extract(sql, dialect)
    except (SqlStructureError, ValueError) as exc:
        raise CompositionError(
            "E_VERIFY_UNKNOWN_IDENTIFIER", f"composed SQL could not be parsed: {type(exc).__name__}") from None
    if structure["statement_count"] != 1 or not structure["read_only_shape"]:
        raise CompositionError("E_VERIFY_NOT_READ_ONLY", "composition must be one read-only SELECT")
    if set(structure["params"]) != set(params):
        raise CompositionError("E_VERIFY_UNBOUND_PARAM", "composition parameter names do not match supplied values")
    resolver = Resolver(snapshot)
    objects: set[str] = set()
    for ref in structure["tables"]:
        table, reason = resolver.table(ref)
        if table is None:
            raise CompositionError("E_VERIFY_UNKNOWN_IDENTIFIER", reason or "unknown composed table")
        label = Resolver.label(table)
        if not _table_allowed(label, profile):
            raise CompositionError("E_VERIFY_TABLE_NOT_ALLOWED", f"table {label!r} is not allowed")
        objects.add(label)
    if not objects or structure["unresolved"]:
        message = structure["unresolved"][0] if structure["unresolved"] else "composition has no table"
        raise CompositionError("E_VERIFY_UNKNOWN_IDENTIFIER", message)
    refs = {column for item in structure["select"] for column in item["columns"]}
    refs.update(item["column"] for item in structure["filters"])
    for edge in structure["joins"]:
        refs.update((edge["left"], edge["right"]))
    for ref in refs:
        resolved = resolver.column(ref)
        if not resolved.ok:
            raise CompositionError(
                "E_VERIFY_UNKNOWN_IDENTIFIER", resolved.reason or f"column {ref!r} does not resolve")
    if any(item["expression"].strip() == "*" or item["expression"].strip().endswith(".*")
           for item in structure["select"]):
        raise CompositionError("E_VERIFY_UNKNOWN_IDENTIFIER", "wildcard projections are not allowed")
    return tuple(sorted(objects))


def _table_allowed(label: str, profile: Mapping[str, Any]) -> bool:
    schema, _, name = label.lower().rpartition(".")
    schemas = {str(value).lower() for value in profile.get("schemas_allowlist", ())}
    tables = {str(value).lower() for value in profile.get("tables_allowlist", ())}
    return (not schemas or schema in schemas) and (not tables or label.lower() in tables or name in tables)


def _completion_context(request: CompositionRequest, profile: Mapping[str, Any],
                        snapshot: Mapping[str, Any], hits: Sequence[Any], mode: str) -> dict[str, Any]:
    catalog = []
    for table in snapshot.get("tables", ()):
        label = Resolver.label(table)
        if _table_allowed(label, profile):
            catalog.append({"object": label, "kind": table.get("kind", "table"),
                            "columns": sorted(str(column["name"]) for column in table.get("columns", ()))})
    exemplars = []
    for hit in hits:
        item = hit.exemplar
        exemplars.append({
            "exemplar_id": item["exemplar_id"], "query_id": item.get("query_id"),
            "repo_id": item["repo_id"], "ref": item["ref"], "path": item["path"],
            "sql": item["sql"], "tables": list(item.get("tables") or ()),
            "pit_columns": list(item.get("pit_columns") or ()), "score": round(hit.score, 6),
        })
    return {
        "mode": mode, "question": request.question, "profile": request.profile,
        "dialect": profile.get("dialect"), "as_of": request.as_of,
        "parameter_names": sorted(_request_params(request)), "pit_columns": list(request.pit_columns),
        "catalog": catalog, "exemplars": exemplars,
        "constraints": {
            "read_only": True, "named_parameters_only": True,
            "row_limit": profile.get("row_limit"), "generated_sql_is_not_indexed": True,
        },
    }


def _record(*, sql: str, params: Mapping[str, Any], path: str, profile: str, dialect: str,
            as_of: str | None, exemplars: Sequence[Mapping[str, Any]], objects: Sequence[str],
            limitations: Sequence[str], query_id: str | None, pit_columns: Sequence[str],
            trusted_literals: Sequence[str]) -> CompositionRecord:
    evidence = tuple({
        "id": item["exemplar_id"], "query_id": item.get("query_id"), "repo": item["repo_id"],
        "ref": item["ref"], "path": item["path"], "sql_hash": item["normalized_sql_hash"],
    } for item in exemplars)
    try:
        params_json = _canonical(params)
    except (TypeError, ValueError, OverflowError):
        raise CompositionError("E_VERIFY_UNBOUND_PARAM", "composition parameters are not canonical JSON") from None
    return CompositionRecord(
        sql=sql, params_json=params_json, path=path, profile=profile, dialect=dialect,
        as_of=as_of, source_exemplars=evidence, catalog_objects=tuple(sorted(objects)),
        limitations=tuple(limitations), query_id=query_id, pit_columns=tuple(sorted(set(pit_columns))),
        trusted_literal_hashes=tuple(sorted(set(trusted_literals))),
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
