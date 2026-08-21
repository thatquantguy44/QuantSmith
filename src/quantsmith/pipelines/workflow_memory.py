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
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

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
#: pattern is the guard, not a convention (spec REQ-009).
_AUTHOR_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
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
          as_of: Optional[datetime.date] = None) -> List[Record]:
    """Select records, in deterministic rank order.

    Every filter is opt-in except ``status``, which defaults to ``"active"``:
    a caller who does not say otherwise wants what the store currently
    believes, not what it has retired. Pass ``status=None`` for every record
    regardless of lifecycle.

    ``as_of`` applies the point-in-time firewall (``point_in_time_filter``).
    It is deliberately a parameter rather than a default: a query with no
    ``as_of`` is unbounded and returns everything, which is right for "what do
    we know about this dataset" and wrong for anything feeding a backtest.
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

    return findings
