"""Token-only, query-only SQL execution with redaction and provenance.

Spec ``0116`` REQ-006–REQ-007.  This module deliberately has no function
that accepts raw SQL.  :func:`execute` receives an in-memory
:class:`~sfmeridian.verify.VerifiedQuery`, validates its exact-context token
against current configuration, catalog snapshot, caller clearance, and
parameters, then calls only a narrowed :class:`QueryOnlyAdapter`.

Rows are redacted before hashing or returning.  Driver exception text, raw
plans, signing material, and non-as-of parameter values never enter errors,
provenance, replay reports, or the ``0070`` producer payload.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .access import REDACTED, Caller, column_requirements, redact_rows, scrub
from .config import Config
from .sqlstructure import SqlStructureError, extract
from .verify import (
    TokenError,
    VerificationRequest,
    VerifiedQuery,
    validate_token,
    verify,
)

__all__ = [
    "ExecutionError", "ExecutionProvenance", "ExecutionResult", "QueryBatch",
    "QueryOnlyAdapter", "ReplayReport", "adapt_query_source", "execute", "replay",
]

_ENVELOPE_SCHEMA = "quantsmith.orchestration.run.v1"
_SPEC_ID = "0116-sfmeridian-governed-sql-composition"


class ExecutionError(RuntimeError):
    """One stable, scrubbed execution failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = scrub(message)
        super().__init__(f"{code}: {self.message}")


@dataclass(frozen=True)
class QueryBatch:
    """Normalized output of an injected query source."""

    rows: Sequence[Mapping[str, Any]]
    truncated: bool = False


class QueryOnlyAdapter:
    """Narrow capability: profile-bound ``query`` and no write methods."""

    __slots__ = ("_query", "dialect", "profile", "read_only")

    def __init__(self, query: Callable[..., Any], *, profile: str, dialect: str) -> None:
        self._query = query
        self.profile = profile
        self.dialect = dialect
        self.read_only = True

    def query(self, sql: str, params: Mapping[str, Any], *, timeout_s: int,
              row_limit: int) -> Any:
        return self._query(sql, params, timeout_s=timeout_s, row_limit=row_limit)


def adapt_query_source(source: Any, *, profile: str, dialect: str) -> QueryOnlyAdapter:
    """Attest and narrow an adopter source; writable/undeclared sources fail."""
    if getattr(source, "read_only", None) is not True:
        raise ExecutionError("E_EXEC_TIMEOUT", "query source is not declared read-only")
    source_profile = getattr(source, "profile", profile)
    source_dialect = getattr(source, "dialect", dialect)
    if source_profile != profile or source_dialect != dialect:
        raise ExecutionError("E_EXEC_TOKEN", "query source context does not match verification")
    query = getattr(source, "query", None)
    if not callable(query):
        raise ExecutionError("E_EXEC_TIMEOUT", "query source does not provide the query-only contract")
    return QueryOnlyAdapter(query, profile=profile, dialect=dialect)


@dataclass(frozen=True)
class ExecutionProvenance:
    run_id: str
    query_id: str | None
    sql_hash: str
    params_hash: str
    path: str
    source_exemplars: tuple[str, ...]
    profile: str
    dialect: str
    snapshot_id: str
    config_hash: str
    policy_version: str
    issued_at: int
    as_of: str | None
    parameter_names: tuple[str, ...]
    parameters: Mapping[str, Any]
    row_count: int
    truncated: bool
    elapsed_ms: int
    explain_cost: float | None
    clearance: str
    withheld_columns: tuple[str, ...]
    rows_hash: str

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_exemplars"] = list(self.source_exemplars)
        value["parameter_names"] = list(self.parameter_names)
        value["withheld_columns"] = list(self.withheld_columns)
        return value


@dataclass(frozen=True)
class ExecutionResult:
    rows: tuple[dict[str, Any], ...]
    provenance: ExecutionProvenance

    def as_dict(self) -> dict[str, Any]:
        return {"rows": [dict(row) for row in self.rows], "provenance": self.provenance.as_dict(),
                "envelope": self.envelope()}

    def envelope(self) -> dict[str, Any]:
        """Safe producer payload shaped for a spec-0070 run envelope."""
        p = self.provenance
        return {
            "schema_version": _ENVELOPE_SCHEMA,
            "run_id": p.run_id,
            "producer": "sfmeridian.sql.execute",
            "spec_id": _SPEC_ID,
            "status": "completed",
            "mode": "deterministic",
            "created_at": _timestamp(p.issued_at),
            "actor": {"type": "runtime", "id": "sfmeridian", "clearance": p.clearance},
            "config_hash": p.config_hash,
            "audit_events": [
                {"seq": 0, "event": "gate_result", "name": "sql.verify", "ok": True},
                {"seq": 1, "event": "data_source_read", "name": p.profile, "ok": True},
                {"seq": 2, "event": "run_completed", "name": "sql.execute", "ok": True},
            ],
            "artifacts": [{"type": "execution_result", "hash": p.rows_hash,
                           "access_class": p.clearance}],
            "replay": {"mode": "deterministic", "expected_rows_hash": p.rows_hash},
            "provenance": p.as_dict(),
        }


@dataclass(frozen=True)
class ReplayReport:
    run_id: str
    status: str  # replayed | mismatch | failed
    mismatches: tuple[str, ...]
    current: ExecutionResult | None = None
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "run_id": self.run_id, "status": self.status, "mismatches": list(self.mismatches),
        }
        if self.current is not None:
            value["current"] = self.current.as_dict()
        if self.error_code is not None:
            value["error_code"] = self.error_code
        return value


def execute(
    verified: VerifiedQuery,
    *,
    token: str,
    params: Mapping[str, Any],
    keys: Mapping[str, bytes],
    now: int,
    config: Config,
    snapshot_id: str,
    caller: Caller,
    source: QueryOnlyAdapter,
    source_exemplars: Sequence[str] = (),
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> ExecutionResult:
    """Execute one exact verified context through the query-only capability."""
    try:
        record = validate_token(token, verified, keys=keys, now=now)
    except TokenError as exc:
        raise ExecutionError(exc.code, exc.message) from None
    try:
        params_json = _canonical(params)
    except (TypeError, ValueError, OverflowError):
        raise ExecutionError("E_EXEC_TOKEN", "execution parameters are not canonical JSON values") from None
    if params_json != verified.params_json:
        raise ExecutionError("E_EXEC_TOKEN", "execution parameters do not match verification")
    if record.config_hash != config.hash or record.snapshot_id != snapshot_id:
        raise ExecutionError("E_EXEC_TOKEN", "current configuration or catalog snapshot does not match verification")
    if caller.active and caller.clearance != record.clearance:
        raise ExecutionError("E_EXEC_TOKEN", "caller clearance does not match verification")
    try:
        profile = config.profile(record.profile)
    except KeyError:
        raise ExecutionError("E_EXEC_TOKEN", "verified database profile is no longer configured") from None
    if (profile.get("dialect") != record.dialect or profile.get("read_only") is not True
            or int(profile.get("timeout_s", 0)) != record.timeout_s
            or record.row_limit > int(profile.get("row_limit", 0))):
        raise ExecutionError("E_EXEC_TOKEN", "database policy no longer matches verification")
    if not isinstance(source, QueryOnlyAdapter):
        raise ExecutionError("E_EXEC_TIMEOUT", "execution requires a query-only adapter")
    if source.profile != record.profile or source.dialect != record.dialect or source.read_only is not True:
        raise ExecutionError("E_EXEC_TOKEN", "query source context does not match verification")

    started = monotonic_ns()
    try:
        raw = source.query(
            verified.sql, dict(params), timeout_s=record.timeout_s, row_limit=record.row_limit)
        batch = _batch(raw, record.row_limit)
    except ExecutionError:
        raise
    except Exception as exc:  # noqa: BLE001 — never expose driver exception text
        raise ExecutionError("E_EXEC_TIMEOUT", f"query source failed: {type(exc).__name__}") from None
    elapsed_ms = max(0, (monotonic_ns() - started) // 1_000_000)

    who = caller if caller.active else Caller(caller.handle, record.clearance, False, caller.source)
    withheld = _withheld_output_columns(config, who, verified.sql, record.dialect, batch.rows)
    rows = tuple(redact_rows(batch.rows[:record.row_limit], withheld))
    rows_hash = _hash(rows)
    as_of = params.get("as_of")
    safe_as_of = as_of if isinstance(as_of, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of) else None
    identity = {
        "config_hash": record.config_hash,
        "snapshot_id": record.snapshot_id,
        "sql_hash": record.sql_hash,
        "params_hash": record.params_hash,
        "as_of": safe_as_of,
        "clearance": record.clearance,
        "policy_version": record.policy_version,
        "profile": record.profile,
        "dialect": record.dialect,
    }
    run_id = f"sfm-{hashlib.sha256(_canonical(identity).encode()).hexdigest()[:20]}"
    parameter_view = {name: (safe_as_of if name == "as_of" and safe_as_of else REDACTED)
                      for name in sorted(params)}
    provenance = ExecutionProvenance(
        run_id=run_id,
        query_id=record.query_id,
        sql_hash=record.sql_hash,
        params_hash=record.params_hash,
        path=record.composition_path,
        source_exemplars=tuple(sorted({scrub(str(value)) for value in source_exemplars if value is not None})),
        profile=record.profile,
        dialect=record.dialect,
        snapshot_id=record.snapshot_id,
        config_hash=record.config_hash,
        policy_version=record.policy_version,
        issued_at=record.issued_at,
        as_of=safe_as_of,
        parameter_names=tuple(sorted(params)),
        parameters=parameter_view,
        row_count=len(rows),
        truncated=batch.truncated or len(batch.rows) > record.row_limit,
        elapsed_ms=elapsed_ms,
        explain_cost=record.explain_cost,
        clearance=record.clearance,
        withheld_columns=tuple(withheld),
        rows_hash=rows_hash,
    )
    return ExecutionResult(rows, provenance)


def replay(
    previous: ExecutionResult,
    request: VerificationRequest,
    *,
    profile: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    join_graph: Sequence[Mapping[str, Any]],
    config: Config,
    key_id: str,
    signing_key: bytes,
    keys: Mapping[str, bytes],
    now: int,
    source: QueryOnlyAdapter,
    caller: Caller,
    source_exemplars: Sequence[str] = (),
    ttl_s: int = 300,
    explainer: Callable[..., Mapping[str, Any]] | None = None,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> ReplayReport:
    """Re-verify under current policy, execute, and compare safe hashes."""
    outcome = verify(
        request,
        profile=profile,
        snapshot=snapshot,
        join_graph=join_graph,
        config_hash=config.hash,
        key_id=key_id,
        signing_key=signing_key,
        now=now,
        ttl_s=ttl_s,
        explainer=explainer,
    )
    if not outcome.ok or outcome.verified is None:
        return ReplayReport(previous.provenance.run_id, "failed", (), error_code=(
            outcome.findings[0].code if outcome.findings else "E_EXEC_TOKEN"))
    try:
        current = execute(
            outcome.verified,
            token=outcome.verified.token,
            params=request.params,
            keys=keys,
            now=now,
            config=config,
            snapshot_id=str(snapshot["snapshot_id"]),
            caller=caller,
            source=source,
            source_exemplars=source_exemplars,
            monotonic_ns=monotonic_ns,
        )
    except ExecutionError as exc:
        return ReplayReport(previous.provenance.run_id, "failed", (), error_code=exc.code)
    fields = ("run_id", "sql_hash", "params_hash", "snapshot_id", "config_hash", "policy_version",
              "rows_hash", "row_count", "truncated", "withheld_columns")
    mismatches = tuple(field for field in fields
                       if getattr(previous.provenance, field) != getattr(current.provenance, field))
    return ReplayReport(previous.provenance.run_id, "mismatch" if mismatches else "replayed",
                        mismatches, current)


def _batch(value: Any, row_limit: int) -> QueryBatch:
    batch = value if isinstance(value, QueryBatch) else QueryBatch(value)
    if (not isinstance(batch.rows, Sequence) or isinstance(batch.rows, (str, bytes))
            or not all(isinstance(row, Mapping) for row in batch.rows)):
        raise ExecutionError("E_EXEC_TIMEOUT", "query source returned invalid rows")
    rows = tuple(dict(row) for row in batch.rows)
    if not all(isinstance(key, str) for row in rows for key in row):
        raise ExecutionError("E_EXEC_TIMEOUT", "query source returned invalid row keys")
    try:
        _canonical(rows)
    except (TypeError, ValueError, OverflowError):
        raise ExecutionError("E_EXEC_TIMEOUT", "query source returned non-canonical row values") from None
    return QueryBatch(rows, bool(batch.truncated) or len(rows) > row_limit)


def _withheld_output_columns(config: Config, who: Caller, sql: str, dialect: str,
                             rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows or not who.active:
        return []
    try:
        structure = extract(sql, dialect)
    except (SqlStructureError, ValueError):  # token validation should make this unreachable
        raise ExecutionError("E_EXEC_TOKEN", "verified SQL no longer parses") from None
    requirements = column_requirements(config)
    hidden_names: set[str] = set()
    for item in structure["select"]:
        for ref in item["columns"]:
            parts = ref.lower().split(".")
            variants = {ref.lower(), ".".join(parts[-2:])}
            requirement = next((requirements[key] for key in variants if key in requirements), None)
            if requirement and not who.sees(requirement["level"]):
                hidden_names.add(str(item.get("name") or parts[-1]).lower())
    actual = {str(key).lower(): str(key) for row in rows for key in row}
    return sorted(actual[name] for name in hidden_names if name in actual)


def _hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode()).hexdigest()}"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _timestamp(epoch: int) -> str:
    # Verification uses an injected UTC epoch, so no wall-clock read is needed.
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
