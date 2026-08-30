"""Reference pipeline for spec 0048 — workflow memory runtime.

Spec ``0002`` defined a persistent workflow memory store: typed records with
provenance, dates, confidence, and a point-in-time scope, committed as YAML
under ``memory/``. Nothing has ever read them as records. ``memory-check.sh``
greps for the string ``first_seen``, which proves a field name appears in a
file and nothing else — it cannot tell a well-formed record from a malformed
one, and it cannot answer a question.

This module makes the store machine-readable. ``load_store`` parses the
committed YAML into typed ``Record`` objects, ``query`` answers scoped
questions, ``point_in_time_filter`` enforces the P4 firewall, and ``validate``
replaces string-matching with real structural checks.

Two design commitments carry the weight:

**The parser never guesses.** It accepts a documented subset of YAML and
raises ``MemoryParseError`` with a file and line on anything outside it. A
lenient parser that silently mis-reads a record is worse than no parser,
because a workflow would act on the mis-reading (spec RISK-001). The
dependency-free constraint is deliberate — ``pyyaml`` is not in the SDK's base
dependencies and the memory gate must run in a copied scaffold.

**A memory store is itself look-ahead.** Knowledge recorded in 2026 did not
exist in 2020, so serving it to a 2020 backtest leaks the future. The rule
therefore depends on record ``type``: mechanical facts about how data is built
are timeless, while claims about what *worked* are bounded — see
``point_in_time_filter`` for the full reasoning (spec RISK-006).

Spec ``0049`` adds the write path this module lacked: ``resolve_author``
finishes ``0048``'s outstanding author-resolution requirements;
``propose_records``/``stage_candidates`` let a pipeline capture what it
observed into a **committed staging area** (``memory/inbox/``) without ever
touching the live store; ``promote`` is the one deliberate, human-invoked
action that turns an accepted candidate into a real ``Record`` — a
``Candidate`` is a distinct, lighter type precisely so nothing *but*
``promote`` can create a ``Record`` (spec NFR-005).
"""

from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

# Identity resolution lives in access_control.py (spec 0058) so it can be
# shared by read-time clearance without a circular import; re-exported here
# unchanged so every existing caller (the CLI, 0049's promote(), tests) keeps
# working at its original import path.
from .access_control import (  # noqa: F401
    AUTHOR_HANDLE_RE,
    derive_handle,
    resolve_author,
)
from . import access_control as _access_control

# --------------------------------------------------------------------------
# Vocabulary — mirrors instructions/workflow_memory.md (spec 0002)
# --------------------------------------------------------------------------

RECORD_TYPES = ("schema", "quirk", "pattern", "pitfall", "decision", "metric", "performance")
CONFIDENCE_LEVELS = ("low", "medium", "high")
STATUS_VALUES = ("active", "stale", "superseded", "retired")

#: Types describing how the data is *constructed*. These are timeless: "join on
#: security_id, tickers get reused" was true in 2005; nobody had written it down
#: yet. Excluding them from a historical query makes a workflow re-learn a
#: mechanical fact or get it wrong, with no leakage benefit.
MECHANICAL_TYPES = ("schema", "quirk", "pitfall")

#: Types encoding an *outcome* — what worked, what a metric came out at. These
#: are bounded by ``last_confirmed`` rather than ``first_seen``, because
#: corroboration is where the future enters a record.
PREDICTIVE_TYPES = ("pattern", "metric", "performance")

#: ``pit_scope`` values that permit use inside a point-in-time-bounded query.
#: Anything else — including ``"original vintage only"`` and any unrecognised
#: string — is excluded. Exclusion is the safe failure: a missing record makes a
#: workflow ask again, a leaked record makes a backtest lie (spec RISK-004).
PIT_SCOPE_ADMISSIBLE = ("<= run date", "<= decision date")
PIT_SCOPE_KNOWN = PIT_SCOPE_ADMISSIBLE + ("original vintage only",)

_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

#: An author must be a pseudonymous handle, never a routable address. The
#: pattern is the guard, not a convention (spec REQ-009). Alias kept for
#: backward compatibility; the canonical definition lives in
#: access_control.py (spec 0058), which also uses it for roster handles.
_AUTHOR_RE = AUTHOR_HANDLE_RE
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class MemoryParseError(ValueError):
    """Raised when a memory file falls outside the supported YAML subset.

    Carries the file and line so the failure is actionable. This is an error,
    not a finding: a file we cannot parse is a file whose records we must not
    pretend to have read.
    """

    def __init__(self, file: str, line: int, reason: str) -> None:
        super().__init__(f"{file}:{line}: {reason}")
        self.file = file
        self.line = line
        self.reason = reason


@dataclass(frozen=True)
class Finding:
    """A validation result. Advisory by default; the gate decides severity."""

    record_id: str
    severity: str  # "error" | "warn" | "info"
    message: str
    file: str = ""
    line: int = 0


@dataclass(frozen=True)
class Record:
    """One memory record.

    Field order matters: everything spec ``0002`` committed comes first, and
    every field ``0048`` adds is appended with a default, so the files ``0002``
    wrote parse unchanged (spec NFR-003).

    ``depends_on`` names records this one's statement relies on being true —
    e.g. a ``pattern`` that depends on a ``quirk`` it assumes. It is not
    validated yet (no cycle/dangling check, unlike ``superseded_by``); the
    field exists so a real record can carry the relation from the day it is
    written, rather than the relation being lost because nowhere to put it. Do
    not confuse it with ``coexists``, which silences the contradiction check
    for two records that legitimately both hold — ``depends_on`` says one
    record is only true *because* another is.
    """

    id: str
    scope: str
    type: str
    statement: str
    confidence: str
    corroboration_count: int  # as DECLARED in the file — a claim, not a measure
    first_seen: datetime.date
    last_confirmed: datetime.date
    status: str
    pit_scope: str
    evidence: Tuple[Mapping[str, str], ...] = ()
    access_level: str = "internal"
    # --- appended by 0048 -------------------------------------------------
    author: Optional[str] = None
    superseded_by: Optional[str] = None
    coexists: Tuple[str, ...] = ()
    depends_on: Tuple[str, ...] = ()
    # --- provenance for findings; not part of the record vocabulary -------
    source_file: str = ""
    source_line: int = 0

    @property
    def corroboration_derived(self) -> int:
        """Corroboration counted from distinct evidence runs.

        ``corroboration_count`` is typed by whoever wrote the record; this is
        computed from what the record can actually show. Ranking uses this one,
        so retrieval order cannot be set by typing a larger integer.
        """
        return len({e["source_run"] for e in self.evidence if "source_run" in e})


@dataclass(frozen=True)
class Store:
    """All records loaded from one manifest, with their governance metadata."""

    records: Tuple[Record, ...]
    freshness_days: int = 90
    files: Tuple[str, ...] = ()


# --------------------------------------------------------------------------
# YAML subset parser (T-001, NFR-005, RISK-001)
# --------------------------------------------------------------------------

def _strip_comment(raw: str) -> str:
    """Remove a trailing ``#`` comment that is not inside quotes."""
    out, quote = [], None
    for ch in raw:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _scalar(text: str, file: str, line: int):
    """Convert a scalar token, preserving the distinction the subset allows."""
    text = text.strip()
    if not text:
        return ""
    if (text[0] == '"' and text[-1] == '"' and len(text) > 1) or (
        text[0] == "'" and text[-1] == "'" and len(text) > 1
    ):
        return text[1:-1]
    if text in ("[]", "{}"):
        return [] if text == "[]" else {}
    if _DATE_RE.match(text):
        try:
            return datetime.date.fromisoformat(text)
        except ValueError as exc:  # pragma: no cover - regex makes this rare
            raise MemoryParseError(file, line, f"invalid date {text!r}: {exc}") from exc
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text.startswith(("[", "{", "&", "*", "!", ">", "|")):
        raise MemoryParseError(
            file, line, f"unsupported YAML construct {text[0]!r} — subset is "
            "mappings, lists of mappings, and plain scalars",
        )
    return text


def _split_pair(content: str, file: str, lineno: int) -> Tuple[str, str]:
    if ":" not in content:
        raise MemoryParseError(file, lineno, f"expected 'key: value', got {content!r}")
    key, _, value = content.partition(":")
    key = key.strip()
    if not key:
        raise MemoryParseError(file, lineno, "empty key")
    return key, value.strip()


def parse_memory_file(text: str, file: str = "<memory>") -> Dict:
    """Parse the documented subset: comments, mappings, lists of mappings.

    Deliberately small. Anything richer raises ``MemoryParseError`` (with file
    and line) rather than being guessed at.

    A key with an empty value is genuinely ambiguous — ``evidence:`` may open a
    mapping or a list, and which one is only knowable from the *next* line. So
    the container is not created until that line arrives; if none does, the key
    holds an empty mapping.
    """
    root: Dict = {}
    stack: List[Dict] = [{"indent": -1, "node": root}]
    pending: Optional[Dict] = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        leading = raw[: len(raw) - len(raw.lstrip())]
        if "\t" in leading:
            raise MemoryParseError(file, lineno, "tab in indentation; use spaces")
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.strip()

        if pending is not None:
            if indent > pending["indent"]:
                node = [] if content.startswith("- ") else {}
                pending["parent"][pending["key"]] = node
                stack.append({"indent": pending["indent"], "node": node})
            else:
                pending["parent"][pending["key"]] = {}
            pending = None

        while len(stack) > 1 and indent <= stack[-1]["indent"]:
            stack.pop()
        node = stack[-1]["node"]

        if content.startswith("- "):
            if not isinstance(node, list):
                raise MemoryParseError(
                    file, lineno, "list item outside a list-valued key")
            entry: Dict = {}
            node.append(entry)
            stack.append({"indent": indent, "node": entry})
            body = content[2:].strip()
            if body:
                key, value = _split_pair(body, file, lineno)
                if value == "":
                    pending = {"parent": entry, "key": key, "indent": indent + 2}
                else:
                    entry[key] = _scalar(value, file, lineno)
            continue

        if not isinstance(node, dict):
            raise MemoryParseError(file, lineno, "mapping key inside a list scope")
        key, value = _split_pair(content, file, lineno)
        if value == "":
            pending = {"parent": node, "key": key, "indent": indent}
        else:
            node[key] = _scalar(value, file, lineno)

    if pending is not None:
        pending["parent"][pending["key"]] = {}

    return root


# --------------------------------------------------------------------------
# Record construction (T-001, T-013)
# --------------------------------------------------------------------------

_REQUIRED = ("id", "scope", "type", "statement", "confidence",
             "first_seen", "last_confirmed", "status", "pit_scope")


def _normalise_evidence(value, file: str, line: int) -> Tuple[Mapping[str, str], ...]:
    """Accept ``0002``'s single mapping or ``0048``'s list of mappings.

    Wrapping the singular form is what keeps every committed file parsing
    unchanged (spec REQ-014, NFR-003).
    """
    if value in (None, "", [], {}):
        return ()
    if isinstance(value, dict):
        return ({k: str(v) for k, v in value.items()},)
    if isinstance(value, list):
        out = []
        for item in value:
            if not isinstance(item, dict):
                raise MemoryParseError(
                    file, line, "evidence list entries must be mappings"
                )
            out.append({k: str(v) for k, v in item.items()})
        return tuple(out)
    raise MemoryParseError(file, line, f"unsupported evidence form: {type(value).__name__}")


def _as_date(value, file: str, line: int, field_name: str) -> datetime.date:
    if isinstance(value, datetime.date):
        return value
    raise MemoryParseError(
        file, line, f"{field_name} must be an ISO date (YYYY-MM-DD), got {value!r}"
    )


def build_record(raw: Mapping, file: str = "", line: int = 0,
                 access_level: str = "internal") -> Record:
    """Build a ``Record`` from a parsed mapping.

    Missing *structural* fields raise; missing *governance* fields (author) are
    left ``None`` for ``validate`` to report, because the committed store
    predates the field and failing on it would make the gate unusable.
    """
    missing = [k for k in _REQUIRED if k not in raw]
    if missing:
        raise MemoryParseError(
            file, line, f"record missing required field(s): {', '.join(missing)}"
        )
    coexists = raw.get("coexists") or ()
    if isinstance(coexists, str):
        coexists = (coexists,)
    depends_on = raw.get("depends_on") or ()
    if isinstance(depends_on, str):
        depends_on = (depends_on,)
    return Record(
        id=str(raw["id"]),
        scope=str(raw["scope"]),
        type=str(raw["type"]),
        statement=str(raw["statement"]),
        confidence=str(raw["confidence"]),
        corroboration_count=int(raw.get("corroboration_count", 0) or 0),
        first_seen=_as_date(raw["first_seen"], file, line, "first_seen"),
        last_confirmed=_as_date(raw["last_confirmed"], file, line, "last_confirmed"),
        status=str(raw["status"]),
        pit_scope=str(raw["pit_scope"]),
        evidence=_normalise_evidence(raw.get("evidence"), file, line),
        access_level=str(raw.get("access_level", access_level)),
        author=(str(raw["author"]) if raw.get("author") else None),
        superseded_by=(str(raw["superseded_by"]) if raw.get("superseded_by") else None),
        coexists=tuple(str(c) for c in coexists),
        depends_on=tuple(str(d) for d in depends_on),
        source_file=file,
        source_line=line,
    )


def load_records(text: str, file: str = "<memory>") -> List[Record]:
    """Load every record from one file's ``records:`` list."""
    doc = parse_memory_file(text, file)
    raw_records = doc.get("records") or []
    if not isinstance(raw_records, list):
        raise MemoryParseError(file, 0, "'records' must be a list")
    default_access = str(doc.get("access_level", "internal"))
    return [build_record(r, file=file, access_level=default_access) for r in raw_records]


# --------------------------------------------------------------------------
# Point-in-time filtering (T-003, REQ-003, REQ-016, RISK-004, RISK-006)
# --------------------------------------------------------------------------

def pit_scope_admits(record: Record) -> bool:
    """Whether ``pit_scope`` permits use in a bounded query.

    Unrecognised values are excluded, not included. The asymmetry is the whole
    point: a missing record makes a workflow ask again; a leaked record makes a
    backtest lie, and P4 forbids that.
    """
    return record.pit_scope in PIT_SCOPE_ADMISSIBLE


def type_rule_admits(record: Record, as_of: datetime.date) -> bool:
    """Whether the record's *type* permits use as of ``as_of``.

    - Mechanical (``schema``/``quirk``/``pitfall``): always. These describe how
      the data is constructed, not an outcome someone measured.
    - Predictive (``pattern``/``metric``/``performance``): ``last_confirmed <=
      as_of``. Bounding on ``first_seen`` would be wrong — a pattern first seen
      in 2018 but confirmed through 2026 is a 2026 artifact, because
      corroboration is where the future enters a record.
    - ``decision``: ``first_seen <= as_of``. A decision is an event; it existed
      from the moment it was made.

    Knowingly conservative for the predictive case: a record whose statement
    never changed is excluded anyway, because without record versioning there
    is no way to tell. Versioning would replace exclusion with serving the
    contemporaneous version.
    """
    if record.type in MECHANICAL_TYPES:
        return True
    if record.type in PREDICTIVE_TYPES:
        return record.last_confirmed <= as_of
    if record.type == "decision":
        return record.first_seen <= as_of
    # An unknown type is not a licence to serve the record.
    return False


def point_in_time_filter(records: Sequence[Record],
                         as_of: datetime.date) -> List[Record]:
    """Records admissible as of ``as_of``.

    Both rules must pass. Because they are independent, ``pit_scope`` being
    free text cannot admit a record the type rule excludes — the weaker check
    can never override the stronger one.
    """
    return [r for r in records
            if type_rule_admits(r, as_of) and pit_scope_admits(r)]


# --------------------------------------------------------------------------
# Query and ranking (T-002, REQ-002, NFR-002)
# --------------------------------------------------------------------------

def rank_key(record: Record):
    """The total order records are returned and rendered in.

    ``confidence`` desc, ``corroboration_derived`` desc, ``last_confirmed``
    desc, then ``id`` ascending as a tiebreak.

    The ``id`` term is what makes the order *total*. Without it, two records
    equal on the first three fields would come back in whatever order the
    filesystem or a dict iteration happened to produce, and the same query
    could answer differently on two machines (NFR-002).

    Ranking uses ``corroboration_derived``, never the declared
    ``corroboration_count``: the declared number is a claim, and retrieval
    order must not be settable by typing a larger integer. ``confidence`` is
    still human-set and therefore still gameable — ``validate`` constrains it
    but does not derive it, so this ordering is a heuristic for usefulness and
    not a measurement of it (spec RISK-005).
    """
    return (
        -_CONFIDENCE_RANK.get(record.confidence, 0),
        -record.corroboration_derived,
        -record.last_confirmed.toordinal(),
        record.id,
    )


def query(records: Sequence[Record], *,
          scope: Optional[str] = None,
          type: Optional[str] = None,
          min_confidence: Optional[str] = None,
          status: Optional[str] = "active",
          as_of: Optional[datetime.date] = None,
          viewer_clearance: Optional[str] = None) -> List[Record]:
    """Select records, in deterministic rank order.

    Every filter is opt-in except ``status``, which defaults to ``"active"``:
    a caller who does not say otherwise wants what the store currently
    believes, not what it has retired. Pass ``status=None`` for every record
    regardless of lifecycle.

    ``as_of`` applies the point-in-time firewall (``point_in_time_filter``).
    It is deliberately a parameter rather than a default: a query with no
    ``as_of`` is unbounded and returns everything, which is right for "what do
    we know about this dataset" and wrong for anything feeding a backtest.

    ``viewer_clearance`` applies the per-person access filter (spec 0058,
    REQ-010). It is ``None`` by default so every existing caller is unfiltered
    (NFR-004); pass the caller's resolved clearance to drop records whose
    ``access_level`` exceeds it.
    """
    out = list(records)

    if scope is not None:
        out = [r for r in out if r.scope == scope]
    if type is not None:
        out = [r for r in out if r.type == type]
    if status is not None:
        out = [r for r in out if r.status == status]
    if min_confidence is not None:
        floor = _CONFIDENCE_RANK.get(min_confidence, 0)
        out = [r for r in out if _CONFIDENCE_RANK.get(r.confidence, 0) >= floor]
    if as_of is not None:
        out = point_in_time_filter(out, as_of)
    if viewer_clearance is not None:
        out = [r for r in out
               if _access_control.access_level_allows(r.access_level, viewer_clearance)]

    return sorted(out, key=rank_key)


# --------------------------------------------------------------------------
# Rendering (T-004, REQ-004, RISK-003, RISK-005)
# --------------------------------------------------------------------------

def format_record_line(record: Record) -> str:
    """One record as a single line of prompt context.

    ``last_confirmed`` appears on every line deliberately. Decay checking is
    advisory, so a stale record can sit in the store indefinitely; showing the
    date is how a reader discounts it without the gate having to (RISK-003).
    """
    return (
        f"- [{record.id}] {record.scope} ({record.type}, "
        f"{record.confidence}, confirmed {record.last_confirmed.isoformat()}): "
        f"{record.statement}"
    )


def render_context(records: Sequence[Record], *, budget_chars: int = 2000,
                   header: str = "Known about this scope:") -> str:
    """Render records as a bounded text block for an agent prompt.

    Fills in rank order and stops at ``budget_chars``, then states how many
    were dropped. Records are dropped from the *bottom* of the ranking, so
    what survives a tight budget is what the store is most confident about.

    **The budget is characters, not tokens.** This module has no tokenizer and
    will not pretend to estimate one — a wrong token estimate silently
    overflows a context window, which is worse than an honest character count.
    A caller who needs tokens owns that conversion.

    An omission notice is emitted whenever anything is dropped, including the
    case where nothing fits at all. Silently returning less than was asked for
    is how a workflow ends up reasoning from a partial store without knowing it.
    """
    ordered = sorted(records, key=rank_key)
    if not ordered:
        return ""

    lines: List[str] = [header]
    used = len(header) + 1  # header plus its newline
    included = 0

    for record in ordered:
        line = format_record_line(record)
        # +1 for the newline this line will carry.
        if used + len(line) + 1 > budget_chars:
            break
        lines.append(line)
        used += len(line) + 1
        included += 1

    omitted = len(ordered) - included
    if omitted:
        lines.append(
            f"... {omitted} further record(s) omitted "
            "(ranked below the included set)."
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Validation (T-005, REQ-005, REQ-009, REQ-010)
# --------------------------------------------------------------------------

def validate(records: Sequence[Record]) -> List[Finding]:
    """Structural validation of a record set.

    This is what replaces grepping for the string ``first_seen``: it checks
    that fields hold *legal values*, that ids are unique, that dates are
    ordered, and that authorship is a pseudonymous handle rather than an
    address. Every finding is collected — validation never stops at the first.
    """
    findings: List[Finding] = []
    seen: Dict[str, Record] = {}

    for r in records:
        where = {"file": r.source_file, "line": r.source_line}

        if r.id in seen:
            findings.append(Finding(
                r.id, "error",
                f"duplicate record id (also in {seen[r.id].source_file})", **where))
        else:
            seen[r.id] = r

        if r.type not in RECORD_TYPES:
            findings.append(Finding(
                r.id, "error",
                f"unknown type {r.type!r}; expected one of {', '.join(RECORD_TYPES)}",
                **where))
        if r.confidence not in CONFIDENCE_LEVELS:
            findings.append(Finding(
                r.id, "error",
                f"unknown confidence {r.confidence!r}; expected one of "
                f"{', '.join(CONFIDENCE_LEVELS)}", **where))
        if r.status not in STATUS_VALUES:
            findings.append(Finding(
                r.id, "error",
                f"unknown status {r.status!r}; expected one of "
                f"{', '.join(STATUS_VALUES)}", **where))

        if r.last_confirmed < r.first_seen:
            findings.append(Finding(
                r.id, "error",
                f"last_confirmed {r.last_confirmed} precedes first_seen "
                f"{r.first_seen}", **where))

        if r.pit_scope not in PIT_SCOPE_KNOWN:
            findings.append(Finding(
                r.id, "warn",
                f"unrecognised pit_scope {r.pit_scope!r}; the record is EXCLUDED "
                "from point-in-time queries until this is one of: "
                + ", ".join(repr(s) for s in PIT_SCOPE_KNOWN), **where))

        if r.author is None:
            findings.append(Finding(
                r.id, "info",
                "no author; record predates author attribution (spec 0048)",
                **where))
        elif "@" in r.author or not _AUTHOR_RE.match(r.author):
            findings.append(Finding(
                r.id, "error",
                f"author {r.author!r} is not a pseudonymous handle — an address "
                "or free text must never be committed as authorship", **where))

        # T-014 — corroboration consistency (spec REQ-010)
        if r.corroboration_derived > 0 and r.corroboration_count > r.corroboration_derived:
            findings.append(Finding(
                r.id, "warn",
                f"declared corroboration_count {r.corroboration_count} exceeds "
                f"derived count {r.corroboration_derived} (distinct source_run entries); "
                "update the count or add more evidence runs", **where))
        elif r.confidence == "high" and r.corroboration_derived <= 1:
            findings.append(Finding(
                r.id, "warn",
                f"confidence=high but only {r.corroboration_derived} corroborating "
                "evidence run(s); consider lowering confidence or adding runs", **where))

    # T-015 — supersession integrity (spec REQ-015)
    all_ids = set(seen.keys())
    for r in records:
        where = {"file": r.source_file, "line": r.source_line}
        if r.status == "superseded" and r.superseded_by is None:
            findings.append(Finding(
                r.id, "error",
                "status=superseded but superseded_by is not set", **where))
        if r.superseded_by is not None and r.superseded_by not in all_ids:
            findings.append(Finding(
                r.id, "error",
                f"superseded_by={r.superseded_by!r} does not resolve to a known id",
                **where))
    # Cycle detection over the superseded_by graph.
    superseded_by_map = {r.id: r.superseded_by for r in records if r.superseded_by}
    for start_id in superseded_by_map:
        visited: set = {start_id}
        current = superseded_by_map.get(start_id)
        while current is not None and current in superseded_by_map:
            if current in visited:
                findings.append(Finding(
                    start_id, "error",
                    f"superseded_by chain is cyclic (revisited {current!r})"))
                break
            visited.add(current)
            current = superseded_by_map.get(current)

    # T-016 — contradiction candidates (spec REQ-016)
    active = [r for r in records if r.status == "active"]
    for i, r1 in enumerate(active):
        for r2 in active[i + 1:]:
            if r1.scope == r2.scope and r1.type == r2.type:
                if r2.id in r1.coexists or r1.id in r2.coexists:
                    continue
                findings.append(Finding(
                    r1.id, "info",
                    f"active record {r2.id!r} shares scope {r1.scope!r} and type "
                    f"{r1.type!r}; mark one superseded or add coexists to silence",
                    file=r1.source_file, line=r1.source_line))

    return findings


# --------------------------------------------------------------------------
# Decay check and store fingerprint (spec 0048 T-006, T-008)
# --------------------------------------------------------------------------

def check_decay(records: Sequence[Record], freshness_days: int) -> List[Finding]:
    """Records whose last_confirmed is older than freshness_days.

    Returns info-severity findings only — decay is advisory; nothing is
    excluded from queries because it is stale. The cutoff is relative to
    today so the same store produces different findings on different dates,
    which is expected: decay is a live-operations concern, not an audit trail.
    """
    import hashlib as _hashlib  # local import to avoid shadowing top-level name
    cutoff = datetime.date.today() - datetime.timedelta(days=freshness_days)
    return [
        Finding(
            r.id, "info",
            f"last_confirmed {r.last_confirmed.isoformat()} is older than "
            f"{freshness_days} days; consider reconfirming",
            file=r.source_file, line=r.source_line,
        )
        for r in records
        if r.status == "active" and r.last_confirmed < cutoff
    ]


def store_version(records: Sequence[Record]) -> str:
    """A short content hash of the record set, for change detection.

    Sorted by id so the hash is independent of load order, and built from
    the fields most likely to change on a legitimate update (statement,
    last_confirmed, status) rather than provenance metadata.
    """
    import hashlib as _hashlib
    h = _hashlib.sha256()
    for r in sorted(records, key=lambda r: r.id):
        h.update(
            f"{r.id}:{r.statement}:{r.last_confirmed.isoformat()}:{r.status}\n"
            .encode("utf-8")
        )
    return h.hexdigest()[:16]


def load_manifest(root: str | os.PathLike = "memory") -> Dict:
    """Load memory/manifest.yaml, returning an empty dict if absent."""
    path = Path(root) / "manifest.yaml"
    if not path.is_file():
        return {}
    return parse_memory_file(path.read_text(encoding="utf-8"), str(path))


# --------------------------------------------------------------------------
# Candidates (spec 0049 T-002, REQ-003/REQ-004)
# --------------------------------------------------------------------------

class MemoryWriteError(ValueError):
    """A promotion was refused (spec REQ-009); nothing was written."""


@dataclass(frozen=True)
class CandidateSpec:
    """What a proposer knows about an observation, before any review.

    Deliberately excludes ``id``, ``author``, and ``first_seen`` — those are
    supplied only by :func:`promote` (spec NFR-005). ``target_catalog`` is a
    path relative to ``memory/`` (e.g. ``"quant_researcher/index.yaml"`` or
    ``"_shared/datasets/example_prices/provenance.yaml"``); it is supplied by
    the proposer explicitly rather than inferred from ``scope``, because
    inference is guessable wrong in a way that would silently misfile a
    record (spec plan.md Trade-offs).
    """

    scope: str
    type: str
    statement: str
    confidence: str
    pit_scope: str
    evidence: Tuple[Mapping[str, str], ...]
    target_catalog: str
    access_level: str = "internal"


@dataclass(frozen=True)
class Candidate:
    """A proposed, not-yet-real observation. Not a :class:`Record`.

    ``candidate_id`` addresses this candidate within its inbox file
    (workflow/source_run/position), independent of list order, so
    :func:`promote`/:func:`discard` can name one precisely even if the file
    has been hand-edited since staging.
    """

    candidate_id: str
    spec: CandidateSpec
    workflow: str
    source_run: str
    proposed_at: datetime.date


def propose_records(specs: Sequence[CandidateSpec], *, workflow: str,
                    source_run: str,
                    proposed_at: Optional[datetime.date] = None) -> List[Candidate]:
    """Build candidates from specs. Pure — writes nothing (spec AC-005).

    ``candidate_id`` is deterministic: ``"<workflow>/<source_run>/<NNN>"`` by
    position in ``specs``, so proposing the same batch twice yields the same
    ids (spec AC-007's byte-identical restaging depends on this).
    """
    proposed_at = proposed_at or datetime.date.today()
    return [
        Candidate(
            candidate_id=f"{workflow}/{source_run}/{i:03d}",
            spec=s, workflow=workflow, source_run=source_run,
            proposed_at=proposed_at,
        )
        for i, s in enumerate(specs, start=1)
    ]


# --------------------------------------------------------------------------
# Deterministic YAML rendering (spec 0049 NFR-003)
# --------------------------------------------------------------------------

def _needs_quoting(text: str) -> bool:
    if text == "" or text in ("[]", "{}"):
        return True
    if _DATE_RE.match(text):
        return True
    if re.fullmatch(r"-?\d+", text):
        return True
    if text[:1] in ("[", "{", "&", "*", "!", ">", "|"):
        return True
    if text != text.strip():
        return True
    return False


def _render_scalar(value, *, always_quote: bool = False) -> str:
    """Render one scalar value in the YAML subset ``parse_memory_file`` reads.

    The subset has no escape sequences (spec plan.md), so a value containing a
    double quote is sanitised (quotes replaced with single quotes) rather than
    emitted in a form that would silently mis-parse on the way back in — the
    same "never guess" stance ``parse_memory_file`` itself takes.
    """
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, int) and not isinstance(value, bool) and not always_quote:
        # A real int (e.g. corroboration_count) always renders bare, matching
        # the store's existing style -- only a *string* that merely looks
        # like digits goes through _needs_quoting's protective quoting below.
        return str(value)
    text = str(value)
    if '"' in text:
        text = text.replace('"', "'")
        always_quote = True
    if always_quote or _needs_quoting(text):
        return f'"{text}"'
    return text


def _render_entry(fields: Sequence[Tuple[str, object, bool]], *, indent: str = "  ") -> List[str]:
    """Render one ``- key: value`` list entry (plus its nested ``evidence:``).

    ``fields`` is ``(key, value, always_quote)``; a value of type
    ``Tuple[Mapping, ...]`` is rendered as a nested list-of-mappings (the
    ``evidence:`` shape), matching what ``parse_memory_file`` accepts.
    """
    lines: List[str] = []
    first = True
    for key, value, always_quote in fields:
        prefix = f"{indent}- " if first else f"{indent}  "
        first = False
        if isinstance(value, tuple):
            lines.append(f"{prefix}{key}:")
            for entry in value:
                sub_first = True
                for ek, ev in entry.items():
                    sub_prefix = f"{indent}    - " if sub_first else f"{indent}      "
                    sub_first = False
                    lines.append(f"{sub_prefix}{ek}: {_render_scalar(ev)}")
            continue
        lines.append(f"{prefix}{key}: {_render_scalar(value, always_quote=always_quote)}")
    return lines


# --------------------------------------------------------------------------
# Staging (spec 0049 T-003, REQ-005/REQ-006)
# --------------------------------------------------------------------------

def _inbox_path(root: str | os.PathLike, workflow: str, source_run: str) -> Path:
    return Path(root) / "inbox" / workflow / f"{source_run}.yaml"


def _candidate_to_fields(c: Candidate) -> List[Tuple[str, object, bool]]:
    s = c.spec
    return [
        ("candidate_id", c.candidate_id, True),
        ("workflow", c.workflow, False),
        ("source_run", c.source_run, True),
        ("proposed_at", c.proposed_at, False),
        ("scope", s.scope, True),
        ("type", s.type, False),
        ("statement", s.statement, True),
        ("confidence", s.confidence, False),
        ("pit_scope", s.pit_scope, True),
        ("target_catalog", s.target_catalog, True),
        ("access_level", s.access_level, False),
        ("evidence", tuple(s.evidence), False),
    ]


def _candidate_from_raw(raw: Mapping, source_file: str) -> Candidate:
    evidence = _normalise_evidence(raw.get("evidence"), source_file, 0)
    spec = CandidateSpec(
        scope=str(raw.get("scope", "")),
        type=str(raw.get("type", "")),
        statement=str(raw.get("statement", "")),
        confidence=str(raw.get("confidence", "")),
        pit_scope=str(raw.get("pit_scope", "")),
        evidence=evidence,
        target_catalog=str(raw.get("target_catalog", "")),
        access_level=str(raw.get("access_level", "internal")),
    )
    proposed_at = raw.get("proposed_at")
    if not isinstance(proposed_at, datetime.date):
        proposed_at = datetime.date.today()
    return Candidate(
        candidate_id=str(raw.get("candidate_id", "")),
        spec=spec,
        workflow=str(raw.get("workflow", "")),
        source_run=str(raw.get("source_run", "")),
        proposed_at=proposed_at,
    )


def stage_candidates(candidates: Sequence[Candidate], *,
                     root: str | os.PathLike = "memory") -> Path:
    """Write candidates to their committed inbox file(s); return the last path
    written. Idempotent (spec AC-007): restaging the same batch — same
    ``candidate_id``s — overwrites those entries in place rather than
    duplicating them, and existing candidates in the file that are not part
    of this batch are preserved.
    """
    root = Path(root)
    by_file: Dict[Path, List[Candidate]] = {}
    for c in candidates:
        by_file.setdefault(_inbox_path(root, c.workflow, c.source_run), []).append(c)

    last_path = None
    for path, batch in by_file.items():
        existing: Dict[str, Candidate] = {}
        if path.is_file():
            for cand, _ in _load_inbox_file(path):
                existing[cand.candidate_id] = cand
        for c in batch:
            existing[c.candidate_id] = c

        ordered = sorted(existing.values(), key=lambda c: c.candidate_id)
        lines = ["# Staged memory candidates -- not yet real records.",
                 "# Reviewed and merged via normal pull-request review;",
                 "# accepted with `promote`, discarded with `discard` (spec 0049).",
                 "",
                 "candidates:"]
        for c in ordered:
            lines.extend(_render_entry(_candidate_to_fields(c)))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        last_path = path
    return last_path


def _load_inbox_file(path: Path) -> List[Tuple[Candidate, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        doc = parse_memory_file(text, str(path))
    except MemoryParseError:
        return []
    raw_items = doc.get("candidates") or []
    if not isinstance(raw_items, list):
        return []
    return [(_candidate_from_raw(r, str(path)), str(path)) for r in raw_items]


def load_inbox(root: str | os.PathLike = "memory") -> List[Tuple[Candidate, str]]:
    """Every staged candidate under ``memory/inbox/``, tagged with its source
    file. Never merged into a live-store ``query``/``point_in_time_filter``
    result (spec REQ-006, AC-008) — this is a wholly separate read path.
    """
    inbox_root = Path(root) / "inbox"
    if not inbox_root.is_dir():
        return []
    out: List[Tuple[Candidate, str]] = []
    for path in sorted(inbox_root.rglob("*.yaml")):
        out.extend(_load_inbox_file(path))
    return out


# --------------------------------------------------------------------------
# Promotion and discard (spec 0049 T-004/T-005, REQ-007..REQ-011)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PromotionResult:
    record: Record
    contradiction_warning: Optional[str]


def _record_to_fields(r: Record) -> List[Tuple[str, object, bool]]:
    fields: List[Tuple[str, object, bool]] = [
        ("id", r.id, False),
        ("scope", r.scope, True),
        ("type", r.type, False),
        ("statement", r.statement, True),
        ("evidence", tuple(r.evidence), False),
        ("confidence", r.confidence, False),
        ("corroboration_count", r.corroboration_count, False),
        ("first_seen", r.first_seen, False),
        ("last_confirmed", r.last_confirmed, False),
        ("status", r.status, False),
        ("pit_scope", r.pit_scope, True),
        ("access_level", r.access_level, False),
    ]
    if r.author is not None:
        fields.append(("author", r.author, False))
    if r.superseded_by is not None:
        fields.append(("superseded_by", r.superseded_by, False))
    # build_record()/parse_memory_file() only round-trip coexists/depends_on as
    # a single scalar (or a 1-tuple) -- the parser has no list-of-bare-scalars
    # form (only list-of-mappings). Multi-value coexists/depends_on is a
    # pre-existing 0048 limitation this spec does not extend; fail loudly
    # rather than silently drop data NFR-004 promises to preserve.
    for field_name, values in (("coexists", r.coexists), ("depends_on", r.depends_on)):
        if len(values) > 1:
            raise MemoryWriteError(
                f"cannot re-serialize {r.id}: multi-value {field_name} "
                f"{values!r} has no round-trippable form in the current "
                "YAML-subset writer (0048 parser limitation, not extended by 0049)")
        if len(values) == 1:
            fields.append((field_name, values[0], False))
    return fields


def _next_id(existing_ids: Sequence[str], *, workflow: str) -> str:
    """A fresh id in this store's existing convention: ``MEM-<NNNN>`` for the
    shared catalog, ``MEM-<PREFIX>-<NNNN>`` for a named workflow, where
    ``<PREFIX>`` is the workflow name's leading letters. Collision-checked
    against every id already in ``existing_ids`` (spec REQ-007/AC-012)."""
    prefix = "MEM" if workflow == "_shared" else f"MEM-{''.join(ch for ch in workflow.upper() if ch.isalpha())[:2]}"
    used = set(existing_ids)
    n = 1
    while True:
        candidate = f"{prefix}-{n:04d}"
        if candidate not in used:
            return candidate
        n += 1


def _load_catalog_records(path: Path) -> Tuple[List[Record], str]:
    if not path.is_file():
        return [], "internal"
    text = path.read_text(encoding="utf-8")
    doc = parse_memory_file(text, str(path))
    raw_records = doc.get("records") or []
    default_access = str(doc.get("access_level", "internal"))
    records = [build_record(r, file=str(path), access_level=default_access)
              for r in (raw_records if isinstance(raw_records, list) else [])]
    return records, default_access


def _write_catalog_records(path: Path, records: Sequence[Record], *,
                           access_level: str) -> None:
    lines = [f"access_level: {access_level}", "", "records:"]
    for r in records:
        lines.extend(_render_entry(_record_to_fields(r)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _rewrite_inbox_without(source_file: str, candidate_id: str) -> None:
    path = Path(source_file)
    remaining = [c for c, _ in _load_inbox_file(path) if c.candidate_id != candidate_id]
    if not remaining:
        path.unlink(missing_ok=True)
        return
    ordered = sorted(remaining, key=lambda c: c.candidate_id)
    lines = ["# Staged memory candidates -- not yet real records.",
             "# Reviewed and merged via normal pull-request review;",
             "# accepted with `promote`, discarded with `discard` (spec 0049).",
             "",
             "candidates:"]
    for c in ordered:
        lines.extend(_render_entry(_candidate_to_fields(c)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def promote(candidate: Candidate, *, source_file: str,
           root: str | os.PathLike = "memory",
           author: Optional[str] = None,
           as_of: Optional[datetime.date] = None,
           identity_root: str | os.PathLike = ".") -> PromotionResult:
    """Turn one staged candidate into a real, committed :class:`Record`.

    Resolves an author (unless ``author`` is given explicitly) by looking for
    a local ``identity.yml``/git identity/OS user under ``identity_root``
    (default: the current directory — where a human running the CLI from a
    repo checkout would have one, independent of where ``memory/`` itself
    lives). Assigns a fresh, collision-checked id, stamps
    ``first_seen``/``last_confirmed`` to ``as_of`` (default: today — spec
    RISK-006's deliberately conservative choice, never the observation date),
    appends the record to its declared ``target_catalog``, and removes the
    candidate from its inbox file. Raises :class:`MemoryWriteError` and writes
    nothing when the candidate would not validate as a record (spec REQ-009,
    AC-011).
    """
    root = Path(root)
    as_of = as_of or datetime.date.today()
    s = candidate.spec
    target_path = root / s.target_catalog
    live_records, catalog_access = _load_catalog_records(target_path)
    live_ids = [r.id for r in live_records]

    resolved_author = author if author is not None else resolve_author(root=identity_root)
    new_id = _next_id(live_ids, workflow=candidate.workflow)
    if new_id in live_ids:
        # _next_id()'s own search loop already avoids this in practice; this
        # is the independent guard REQ-009/AC-012 asks for, so a collision is
        # a refusal by construction rather than an emergent property of one
        # helper's internals never being wrong.
        raise MemoryWriteError(
            f"refusing to promote {candidate.candidate_id}: assigned id "
            f"{new_id!r} already exists in {target_path}")

    # Only include the structural fields build_record()'s _REQUIRED check
    # looks for when they actually hold a value — an empty/absent one must
    # trigger that check's "missing required field" raise (spec REQ-009,
    # AC-011), not sail through as a valid empty string.
    raw: Dict[str, object] = {
        "id": new_id,
        "evidence": list(s.evidence),
        "corroboration_count": len({e.get("source_run") for e in s.evidence if e.get("source_run")}),
        "first_seen": as_of, "last_confirmed": as_of, "status": "active",
        "access_level": s.access_level, "author": resolved_author,
    }
    for key, value in (("scope", s.scope), ("type", s.type), ("statement", s.statement),
                       ("confidence", s.confidence), ("pit_scope", s.pit_scope)):
        if value:
            raw[key] = value

    try:
        record = build_record(raw, file=str(target_path), access_level=s.access_level)
    except MemoryParseError as exc:
        raise MemoryWriteError(
            f"refusing to promote {candidate.candidate_id}: {exc}") from exc

    findings = validate([record])
    blocking = [f for f in findings if f.severity == "error"]
    if blocking:
        reasons = "; ".join(f.message for f in blocking)
        raise MemoryWriteError(f"refusing to promote {candidate.candidate_id}: {reasons}")

    contradiction = None
    for r in live_records:
        if r.status == "active" and r.scope == record.scope and r.type == record.type:
            if record.id not in r.coexists and r.id not in record.coexists:
                contradiction = (f"{new_id} shares scope {record.scope!r} and type "
                                 f"{record.type!r} with active record {r.id} — review "
                                 "before treating both as current (spec 0048 REQ-012).")
                break

    _write_catalog_records(target_path, [*live_records, record], access_level=catalog_access)
    _rewrite_inbox_without(source_file, candidate.candidate_id)

    return PromotionResult(record=record, contradiction_warning=contradiction)


def discard(candidate: Candidate, *, source_file: str,
           root: str | os.PathLike = "memory") -> None:
    """Remove one staged candidate from its inbox file without promoting it.

    Nothing is written to the live store. The commit that removes it is the
    audit trail for this decision (spec REQ-011) — no separate "rejected"
    record is kept, matching the "PR review is the approval workflow" design.
    """
    _rewrite_inbox_without(source_file, candidate.candidate_id)
