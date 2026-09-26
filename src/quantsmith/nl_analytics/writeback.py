"""Write-back to a database. Spec ``0080`` (REQ-010, REQ-011, REQ-012).

Publishing a chat answer's insights is opt-in, never a side effect of asking
a question. Every write goes through a declared, reviewable contract
(`templates/data/writeback_contract.md`): a fixed schema, an idempotency key,
a source-table deny-list, and an approval rule. A commit is dry-run by
default, needs an explicit approval unless the contract says otherwise, is
append-only (the only mutation is a tombstone reversal by run id), and the
actual read or write is always a caller-injected callable — this module never
opens a connection.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from .execute import Result
from .insights import Insight
from .plan import QueryPlan

SCHEMA_COLUMNS: Tuple[str, ...] = (
    "record_key", "run_id", "question_hash", "plan_hash", "metric",
    "metric_definition_hash", "dimensions_json", "window_start", "window_end",
    "as_of", "insight_kind", "values_json", "headline", "interpreter_mode",
    "author_handle", "created_at", "reversed_at",
)


class WriteBackError(ValueError):
    """Raised for a malformed contract, a disallowed record, or a refused commit."""


@dataclass(frozen=True)
class WriteBackContract:
    """A declared write-back target — never a connection (REQ-010)."""

    name: str
    columns: Tuple[str, ...]
    idempotency_key: str
    source_tables_denied: Tuple[str, ...]
    auto_approve: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise WriteBackError("a contract needs a name")
        if set(self.columns) != set(SCHEMA_COLUMNS):
            raise WriteBackError(
                f"contract {self.name!r}: columns must be exactly {SCHEMA_COLUMNS}, "
                f"got {self.columns}"
            )
        if self.idempotency_key not in self.columns:
            raise WriteBackError(f"contract {self.name!r}: idempotency_key not in its own columns")

    def targets_denied_table(self, table: str) -> bool:
        """Whether ``table`` is on this contract's deny-list (glob-style ``*``)."""
        for pattern in self.source_tables_denied:
            regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
            if re.match(regex, table):
                return True
        return False


def default_contract(name: str, *, source_tables_denied: Sequence[str] = (), auto_approve: bool = False) -> WriteBackContract:
    """A contract using the standard schema (matches the shipped template)."""
    return WriteBackContract(
        name=name, columns=SCHEMA_COLUMNS, idempotency_key="record_key",
        source_tables_denied=tuple(source_tables_denied), auto_approve=auto_approve,
    )


_NAME_RE = re.compile(r"^\s*-\s*\*\*Name:\*\*\s*(?P<value>\S+)")
_AUTO_APPROVE_RE = re.compile(r"^\s*-\s*\*\*`auto_approve`:\*\*\s*`(?P<value>true|false)`")
_HEADING_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*-\s+(?P<text>.+?)\s*$")


def load_contract(path: str) -> WriteBackContract:
    """Parse a committed ``writeback_contract.md`` (T-011) into a
    :class:`WriteBackContract`.

    Schema and idempotency key are the one, system-wide insight-record shape
    (``SCHEMA_COLUMNS``) — the parts a contract file actually varies per
    deployment are its name, source-table deny-list, and approval rule.
    A file that still carries the template's own unfilled placeholders
    (``<target-name>``, ``<e.g. ...>``) is rejected: an "undeclared" target,
    not a real one.
    """
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()

    name = None
    for line in lines:
        m = _NAME_RE.match(line)
        if m:
            name = m.group("value")
            break
    if not name or name.startswith("<"):
        raise WriteBackError(f"{path}: no target name (or still a template placeholder)")

    auto_approve = False
    for line in lines:
        m = _AUTO_APPROVE_RE.match(line)
        if m:
            auto_approve = m.group("value") == "true"
            break

    denied: list = []
    in_section = False
    for line in lines:
        heading = _HEADING_RE.match(line)
        if heading:
            in_section = heading.group("title") == "Source-Table Deny-List"
            continue
        if not in_section:
            continue
        bullet = _BULLET_RE.match(line)
        if bullet and not bullet.group("text").startswith("<"):
            denied.append(bullet.group("text").strip("`"))

    return default_contract(name, source_tables_denied=tuple(denied), auto_approve=auto_approve)


@runtime_checkable
class WriteBackWriter(Protocol):
    """What a caller injects to actually write records (REQ-010).

    ``write`` returns the count of *new* rows it inserted — idempotency is
    the writer's own job (e.g. ``INSERT ... ON CONFLICT DO NOTHING``), since
    only the writer knows what is already stored. ``reverse`` tombstones
    every record for ``run_id`` and returns how many it touched.
    """

    def write(self, records: Sequence[Mapping[str, object]]) -> int: ...

    def reverse(self, run_id: str, reversed_at: int) -> int: ...


@dataclass(frozen=True)
class WriteBackOutcome:
    """What ``publish``/``reverse`` did (or would do, for a dry run)."""

    status: str  # "dry_run" | "committed" | "reversed"
    records: Tuple[Dict[str, object], ...]
    written_count: int
    run_id: Optional[str]


def _validate_records(records: Sequence[Mapping[str, object]], contract: WriteBackContract) -> None:
    for r in records:
        if set(r) != set(contract.columns):
            raise WriteBackError(
                f"record for contract {contract.name!r} has columns {sorted(r)}, "
                f"contract requires exactly {sorted(contract.columns)}"
            )


def build_records(
    plan: QueryPlan,
    result: Result,
    insights: Sequence[Insight],
    *,
    run_id: str,
    question: str,
    metric_definition_hash: str,
    author_handle: str,
    interpreter_mode: str,
    created_at: int,
) -> Tuple[Dict[str, object], ...]:
    """Build one write-back record per insight (REQ-010).

    ``record_key`` is a hash of ``run_id`` and the insight's position, so
    rebuilding the identical answer produces the identical keys — the
    idempotency a re-run relies on.
    """
    question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
    plan_hash = plan.content_hash()
    records = []
    for i, insight in enumerate(insights):
        record_key = hashlib.sha256(f"{run_id}:{i}".encode("utf-8")).hexdigest()
        records.append(
            {
                "record_key": record_key,
                "run_id": run_id,
                "question_hash": question_hash,
                "plan_hash": plan_hash,
                "metric": plan.metric,
                "metric_definition_hash": metric_definition_hash,
                "dimensions_json": json.dumps(list(plan.dimensions), sort_keys=True),
                "window_start": plan.window.start_period,
                "window_end": plan.window.end_period,
                "as_of": result.as_of,
                "insight_kind": insight.kind,
                "values_json": json.dumps(insight.values, sort_keys=True, default=str),
                "headline": insight.statement,
                "interpreter_mode": interpreter_mode,
                "author_handle": author_handle,
                "created_at": created_at,
                "reversed_at": None,
            }
        )
    return tuple(records)


def publish(
    records: Sequence[Mapping[str, object]],
    contract: WriteBackContract,
    writer: WriteBackWriter,
    *,
    dry_run: bool = True,
    approved: bool = False,
    target_table: Optional[str] = None,
) -> WriteBackOutcome:
    """Publish ``records`` under ``contract`` (REQ-010, REQ-011).

    Dry run (the default) validates and returns the exact records it would
    write without calling ``writer`` at all. A commit needs ``approved=True``
    unless ``contract.auto_approve`` — a target naming its own approval
    decision in the contract, not a caller's local default.
    """
    if target_table is not None and contract.targets_denied_table(target_table):
        raise WriteBackError(f"contract {contract.name!r} denies writes to table {target_table!r}")
    _validate_records(records, contract)

    run_id = records[0]["run_id"] if records else None
    if dry_run:
        return WriteBackOutcome(status="dry_run", records=tuple(dict(r) for r in records), written_count=0, run_id=run_id)

    if not contract.auto_approve and not approved:
        raise WriteBackError(
            f"contract {contract.name!r} requires approval to commit "
            "(pass approved=True) unless auto_approve is set"
        )

    written = writer.write(records)
    return WriteBackOutcome(status="committed", records=tuple(dict(r) for r in records), written_count=written, run_id=run_id)


def reverse(run_id: str, reversed_at: int, contract: WriteBackContract, writer: WriteBackWriter) -> WriteBackOutcome:
    """Tombstone every record for ``run_id`` (REQ-011). Never deletes.

    ``reversed_at`` is caller-supplied, like every other timestamp/period in
    this package (``created_at``, ``as_of``) — the writer never reads a
    clock, so ``prior_insights`` can compare a record's reversal against an
    arbitrary earlier ``as_of`` exactly (NFR-002).
    """
    if not run_id:
        raise WriteBackError("reverse() needs a run_id")
    count = writer.reverse(run_id, reversed_at)
    return WriteBackOutcome(status="reversed", records=(), written_count=count, run_id=run_id)


# ---------------------------------------------------------------------------
# Prior-insight comparisons (REQ-012)
# ---------------------------------------------------------------------------

# A caller-injected read of every persisted record for one ``plan_hash``
# (any ``created_at``, any reversal state) — the as-of and reversal filtering
# happens here, not in the reader, the same division execute.py uses.
PriorInsightReader = Callable[[str], Sequence[Mapping[str, object]]]


@dataclass(frozen=True)
class PriorInsight:
    """Enough of a persisted answer to compare against: a total level, keyed
    like a :class:`~quantsmith.nl_analytics.execute.Result` (``compute_insights``
    only ever reads ``.values``, so this stands in for one).

    Reconstructed from the persisted ``level`` insight only — a per-dimension
    prior-insight comparison (reconstructing a group-level breakdown from
    stored ``contributor`` rows) is a documented follow-up, not built here.
    """

    values: Dict[Tuple[str, ...], float]
    as_of: int
    run_id: str


def prior_insights(reader: PriorInsightReader, key: str, as_of: int) -> Optional[PriorInsight]:
    """The most recent persisted level for ``key``, visible as of ``as_of``
    (REQ-012, NFR-002).

    ``key`` identifies *what* was asked, not *when* — ``respond.py`` uses
    ``"{metric}|{dim1}|{dim2}..."`` (metric and declared dimensions, not the
    window), so "since yesterday" matches the same governed question across
    two different rolling windows. The reader interprets ``key`` however its
    store needs to (a WHERE clause on ``metric``/``dimensions_json``, for the
    SQLite reader in ``writeback_sqlite.py``).

    Never reads a clock: ``as_of`` is the only bound. A record written after
    ``as_of``, or reversed at or before ``as_of``, is invisible — and this
    function never writes, so the store's history is never touched by a read.
    """
    rows = reader(key)
    visible = [
        r for r in rows
        if r["insight_kind"] == "level"
        and int(r["created_at"]) <= as_of
        and (r.get("reversed_at") is None or int(r["reversed_at"]) > as_of)
    ]
    if not visible:
        return None
    latest = max(visible, key=lambda r: int(r["created_at"]))
    level = json.loads(str(latest["values_json"]))["level"]
    return PriorInsight(values={(): float(level)}, as_of=int(latest["as_of"]), run_id=str(latest["run_id"]))
