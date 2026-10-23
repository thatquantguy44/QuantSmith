"""Bounded, redacted specialist handoffs for workflows W7--W12.

Spec ``0116`` REQ-015.  A handoff is inert data: this module validates the
receiver against the approved ``handoffs.json`` map and never imports or calls
the receiving agent.  It carries only evidence identifiers and safe metadata,
not result rows, parameters, credentials, or withheld column names.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .access import LEVELS, scrub, scrub_value
from .governance import load

__all__ = [
    "HandoffError", "HandoffRequest", "SpecialistHandoff", "build_handoff",
    "validate_handoff",
]

SCHEMA_VERSION = "sfmeridian.specialist-handoff.v1"
RUN_ENVELOPE_SCHEMA = "quantsmith.orchestration.run.v1"
WORKFLOWS = frozenset({"W7", "W8", "W9", "W10", "W11", "W12"})
_CITATION_KINDS = frozenset({"query", "metric", "catalog", "exemplar", "pack", "run"})
_FORBIDDEN_KEYS = frozenset({
    "credentials", "password", "secret", "signing_key", "token", "rows", "parameters",
    "withheld_columns", "sql",
})
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class HandoffError(ValueError):
    """One stable, scrubbed handoff contract failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = scrub(message)
        super().__init__(f"{code}: {self.message}")


@dataclass(frozen=True)
class HandoffRequest:
    workflow: str
    receiver: str
    request: str
    originating_run_id: str
    execution_run_ids: tuple[str, ...]
    as_of: str
    pit_basis: str
    profile: str
    snapshot_id: str
    citations: tuple[str, ...]
    clearance: str
    withheld_column_count: int = 0
    parameters_redacted: bool = True


@dataclass(frozen=True)
class SpecialistHandoff:
    schema_version: str
    workflow: str
    receiver: str
    receiver_path: str
    request: str
    originating_run_id: str
    execution_run_ids: tuple[str, ...]
    point_in_time: Mapping[str, Any]
    profile: str
    catalog_snapshot_id: str
    citations: tuple[str, ...]
    evidence_references: tuple[Mapping[str, str], ...]
    clearance: str
    redaction: Mapping[str, Any]
    requested_output: str
    never: str
    content_hash: str

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["execution_run_ids"] = list(self.execution_run_ids)
        value["citations"] = list(self.citations)
        value["evidence_references"] = [dict(item) for item in self.evidence_references]
        return value


def build_handoff(request: HandoffRequest, *, catalog: Mapping[str, Any] | None = None) -> SpecialistHandoff:
    """Build an inert handoff whose receiver boundary comes from governance data."""
    entries = _entries(catalog)
    entry = next((item for item in entries
                  if item.get("agent") == request.receiver
                  and request.workflow in item.get("workflows", ())), None)
    if request.workflow not in WORKFLOWS:
        raise HandoffError("E_HANDOFF_WORKFLOW", f"unsupported specialist workflow {request.workflow!r}")
    if entry is None:
        raise HandoffError(
            "E_HANDOFF_RECEIVER",
            f"receiver {request.receiver!r} is not approved for {request.workflow}",
        )
    _validate_request(request)
    execution_ids = tuple(sorted(set(request.execution_run_ids)))
    citations = tuple(sorted({scrub(item.strip()) for item in request.citations if item.strip()}))
    references = (
        {"type": "0070_run", "role": "originating", "schema_version": RUN_ENVELOPE_SCHEMA,
         "run_id": request.originating_run_id},
        *(
            {"type": "0070_run", "role": "execution", "schema_version": RUN_ENVELOPE_SCHEMA,
             "run_id": run_id}
            for run_id in execution_ids
        ),
    )
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "workflow": request.workflow,
        "receiver": str(entry["agent"]),
        "receiver_path": str(entry["path"]),
        "request": scrub(request.request.strip()),
        "originating_run_id": request.originating_run_id,
        "execution_run_ids": list(execution_ids),
        "point_in_time": {
            "attested": True,
            "as_of": request.as_of,
            "basis": scrub(request.pit_basis.strip()),
        },
        "profile": request.profile,
        "catalog_snapshot_id": request.snapshot_id,
        "citations": list(citations),
        "evidence_references": list(references),
        "clearance": request.clearance,
        "redaction": {
            "applied": request.withheld_column_count > 0,
            "withheld_column_count": request.withheld_column_count,
            "withheld_columns_included": False,
            "parameters_redacted": request.parameters_redacted,
        },
        "requested_output": str(entry["output"]),
        "never": str(entry["never"]),
    }
    body["content_hash"] = _hash(body)
    problems = validate_handoff(body, catalog=catalog)
    if problems:
        raise HandoffError("E_HANDOFF_INVALID", "; ".join(problems))
    return SpecialistHandoff(
        schema_version=body["schema_version"], workflow=body["workflow"], receiver=body["receiver"],
        receiver_path=body["receiver_path"], request=body["request"],
        originating_run_id=body["originating_run_id"], execution_run_ids=execution_ids,
        point_in_time=body["point_in_time"], profile=body["profile"],
        catalog_snapshot_id=body["catalog_snapshot_id"], citations=citations,
        evidence_references=tuple(references), clearance=body["clearance"],
        redaction=body["redaction"], requested_output=body["requested_output"],
        never=body["never"], content_hash=body["content_hash"],
    )


def validate_handoff(payload: Mapping[str, Any], *, catalog: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    """Return every contract error without executing or mutating a receiver."""
    problems: list[str] = []
    expected = {
        "schema_version", "workflow", "receiver", "receiver_path", "request",
        "originating_run_id", "execution_run_ids", "point_in_time", "profile",
        "catalog_snapshot_id", "citations", "evidence_references", "clearance",
        "redaction", "requested_output", "never", "content_hash",
    }
    missing = sorted(expected - set(payload))
    extra = sorted(set(payload) - expected)
    if missing:
        problems.append(f"missing fields: {missing}")
    if extra:
        problems.append(f"unknown fields: {extra}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version is not supported")
    workflow, receiver = payload.get("workflow"), payload.get("receiver")
    entry = next((item for item in _entries(catalog)
                  if item.get("agent") == receiver and workflow in item.get("workflows", ())), None)
    if workflow not in WORKFLOWS:
        problems.append("workflow must be one of W7--W12")
    if entry is None:
        problems.append("receiver is not approved for the workflow")
    else:
        for field, catalog_field in (("receiver_path", "path"), ("requested_output", "output"),
                                     ("never", "never")):
            if payload.get(field) != entry.get(catalog_field):
                problems.append(f"{field} differs from handoffs.json")
    if not _bounded_string(payload.get("request"), 1000):
        problems.append("request must be a non-empty string of at most 1000 characters")
    if not _bounded_string(payload.get("originating_run_id"), 128):
        problems.append("originating_run_id is invalid")
    execution_ids = payload.get("execution_run_ids")
    if (not isinstance(execution_ids, list) or not execution_ids
            or any(not _bounded_string(item, 128) for item in execution_ids)):
        problems.append("execution_run_ids must be a non-empty list of bounded IDs")
    point = payload.get("point_in_time")
    if (not isinstance(point, Mapping) or point.get("attested") is not True
            or not isinstance(point.get("as_of"), str) or not _DATE.fullmatch(point["as_of"])
            or not _bounded_string(point.get("basis"), 500)):
        problems.append("point_in_time must attest an ISO as-of and bounded basis")
    for field in ("profile", "catalog_snapshot_id"):
        if not _bounded_string(payload.get(field), 256):
            problems.append(f"{field} is invalid")
    citations = payload.get("citations")
    if not isinstance(citations, list) or not citations:
        problems.append("citations must be a non-empty list")
    else:
        kinds = {item.split(":", 1)[0] for item in citations if isinstance(item, str) and ":" in item}
        if not kinds <= _CITATION_KINDS:
            problems.append("citations contain an unsupported kind")
        if not kinds & {"query", "metric"}:
            problems.append("at least one query or metric citation is required")
    if payload.get("clearance") not in (*LEVELS, "unrestricted"):
        problems.append("clearance is unknown")
    redaction = payload.get("redaction")
    if (not isinstance(redaction, Mapping)
            or redaction.get("withheld_columns_included") is not False
            or redaction.get("parameters_redacted") is not True
            or not isinstance(redaction.get("withheld_column_count"), int)
            or redaction.get("withheld_column_count", -1) < 0):
        problems.append("redaction summary is incomplete or unsafe")
    refs = payload.get("evidence_references")
    run_values = [payload.get("originating_run_id")]
    run_values.extend(execution_ids if isinstance(execution_ids, list) else [])
    required_runs = {item for item in run_values if isinstance(item, str)}
    referenced_runs = {
        item.get("run_id") for item in refs if isinstance(item, Mapping)
        and item.get("type") == "0070_run" and item.get("schema_version") == RUN_ENVELOPE_SCHEMA
    } if isinstance(refs, list) else set()
    if (not isinstance(refs, list) or len(required_runs) != len(run_values)
            or not required_runs <= referenced_runs):
        problems.append("0070 evidence references do not cover every run ID")
    forbidden = _find_forbidden_keys(payload)
    if forbidden:
        problems.append(f"forbidden data fields are present: {sorted(forbidden)}")
    if scrub_value(dict(payload)) != dict(payload):
        problems.append("credential-shaped value is present")
    unhashed = {key: value for key, value in payload.items() if key != "content_hash"}
    if payload.get("content_hash") != _hash(unhashed):
        problems.append("content_hash does not match the payload")
    return tuple(problems)


def _validate_request(request: HandoffRequest) -> None:
    if not _bounded_string(request.request, 1000):
        raise HandoffError("E_HANDOFF_REQUEST", "request must be non-empty and at most 1000 characters")
    for field, value in (("originating_run_id", request.originating_run_id), ("profile", request.profile),
                         ("snapshot_id", request.snapshot_id), ("pit_basis", request.pit_basis)):
        if not _bounded_string(value, 500):
            raise HandoffError("E_HANDOFF_REQUEST", f"{field} is missing or too long")
    if not _DATE.fullmatch(request.as_of):
        raise HandoffError("E_HANDOFF_PIT", "as_of must be an ISO date YYYY-MM-DD")
    if not request.execution_run_ids or any(not _bounded_string(item, 128) for item in request.execution_run_ids):
        raise HandoffError("E_HANDOFF_EVIDENCE", "at least one valid execution run ID is required")
    if not request.citations:
        raise HandoffError("E_HANDOFF_EVIDENCE", "query or metric citations are required")
    if request.clearance not in (*LEVELS, "unrestricted"):
        raise HandoffError("E_HANDOFF_CLEARANCE", "clearance is unknown")
    if request.withheld_column_count < 0 or request.parameters_redacted is not True:
        raise HandoffError("E_HANDOFF_REDACTION", "unsafe redaction summary")


def _entries(catalog: Mapping[str, Any] | None) -> Sequence[Mapping[str, Any]]:
    source = catalog if catalog is not None else load("handoffs.json")
    entries = source.get("handoffs")
    if not isinstance(entries, list):
        raise HandoffError("E_HANDOFF_CATALOG", "handoffs.json has no handoff list")
    return [item for item in entries if isinstance(item, Mapping)]


def _bounded_string(value: Any, limit: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def _find_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                found.add(str(key))
            found.update(_find_forbidden_keys(child))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            found.update(_find_forbidden_keys(child))
    return found


def _hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()
