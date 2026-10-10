"""Reference runtime for spec 0111 — schema evolution and drift.

Vendors and upstream teams change schemas: a column is added, renamed, widened
from int to float, made nullable, or dropped. Whether that change is safe depends
on who reads what. This module answers it the way schema registries do:

* **Backward compatible** — a reader on the *new* schema can read data written
  with the *old* one (safe to upgrade consumers first, then replay history).
* **Forward compatible** — a reader on the *old* schema can read data written with
  the *new* one (safe to upgrade producers first).
* **Full** — both.

``compatibility`` classifies every change and says which direction it breaks;
``check`` enforces a declared mode; ``detect_drift`` compares the rows a feed
actually delivered against the declared schema, so drift is caught before load,
not after a backtest has consumed it.

Guarantees held by construction:

* REQ-004 / AC-004 — every field-level change is classified (added, removed, type
  widened/narrowed/changed, nullability tightened/relaxed, default changed) with
  the direction(s) it breaks; a change list is never summarized away.
* REQ-005 / AC-005 — ``check`` returns a violation for every change that breaks
  the declared mode, so a breaking change cannot be approved silently.
* REQ-006 / AC-006 — ``detect_drift`` reports unknown columns, missing required
  columns, nulls in non-nullable columns, and type mismatches, with row counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

TYPES = ("bool", "int", "long", "float", "double", "decimal", "string", "date", "timestamp")

# Promotions a reader may apply to a writer's value (Avro-style widening).
WIDENING: Dict[str, Tuple[str, ...]] = {
    "int": ("long", "float", "double", "decimal"),
    "long": ("float", "double", "decimal"),
    "float": ("double",),
    "date": ("timestamp",),
}

MISSING = object()

_PY_TYPES: Dict[str, Tuple[type, ...]] = {
    "bool": (bool,),
    "int": (int,),
    "long": (int,),
    "float": (int, float),
    "double": (int, float),
    "decimal": (int, float),
    "string": (str,),
    "date": (str,),
    "timestamp": (str,),
}


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    nullable: bool = False
    default: Any = MISSING

    @property
    def has_default(self) -> bool:
        return self.default is not MISSING


@dataclass(frozen=True)
class Schema:
    name: str
    version: str
    fields: Tuple[Field, ...]

    def __post_init__(self) -> None:
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            raise ValueError(f"schema {self.name}@{self.version} has duplicate fields")
        for f in self.fields:
            if f.type not in TYPES:
                raise ValueError(f"{self.name}.{f.name}: unknown type '{f.type}'")

    def by_name(self) -> Dict[str, Field]:
        return {f.name: f for f in self.fields}


@dataclass(frozen=True)
class Change:
    field: str
    kind: str
    detail: str
    breaks_backward: bool  # new reader cannot read old data
    breaks_forward: bool  # old reader cannot read new data


@dataclass(frozen=True)
class Compatibility:
    changes: Tuple[Change, ...]

    @property
    def backward(self) -> bool:
        return not any(c.breaks_backward for c in self.changes)

    @property
    def forward(self) -> bool:
        return not any(c.breaks_forward for c in self.changes)

    @property
    def full(self) -> bool:
        return self.backward and self.forward


def _widens(src: str, dst: str) -> bool:
    return dst in WIDENING.get(src, ())


def compatibility(old: Schema, new: Schema) -> Compatibility:
    """Classify every field-level change between two schema versions."""
    o, n = old.by_name(), new.by_name()
    changes: List[Change] = []
    for name in sorted(set(o) | set(n)):
        a, b = o.get(name), n.get(name)
        if a is None and b is not None:
            # New reader reading old data needs a value for the missing field.
            ok_back = b.has_default or b.nullable
            changes.append(Change(name, "added",
                                  f"{b.type}{' nullable' if b.nullable else ''}"
                                  f"{' with default' if b.has_default else ''}",
                                  breaks_backward=not ok_back, breaks_forward=False))
            continue
        if b is None and a is not None:
            # Old reader reading new data needs a value for the dropped field.
            ok_fwd = a.has_default or a.nullable
            changes.append(Change(name, "removed", a.type,
                                  breaks_backward=False, breaks_forward=not ok_fwd))
            continue
        assert a is not None and b is not None
        if a.type != b.type:
            if _widens(a.type, b.type):
                changes.append(Change(name, "type_widened", f"{a.type} -> {b.type}",
                                      breaks_backward=False, breaks_forward=True))
            elif _widens(b.type, a.type):
                changes.append(Change(name, "type_narrowed", f"{a.type} -> {b.type}",
                                      breaks_backward=True, breaks_forward=False))
            else:
                changes.append(Change(name, "type_changed", f"{a.type} -> {b.type}",
                                      breaks_backward=True, breaks_forward=True))
        if a.nullable and not b.nullable:
            changes.append(Change(name, "nullability_tightened", "nullable -> required",
                                  breaks_backward=True, breaks_forward=False))
        elif b.nullable and not a.nullable:
            changes.append(Change(name, "nullability_relaxed", "required -> nullable",
                                  breaks_backward=False, breaks_forward=True))
        if a.has_default != b.has_default or (
            a.has_default and b.has_default and a.default != b.default
        ):
            changes.append(Change(name, "default_changed",
                                  f"{a.default if a.has_default else '(none)'} -> "
                                  f"{b.default if b.has_default else '(none)'}",
                                  breaks_backward=False, breaks_forward=False))
    return Compatibility(tuple(changes))


def check(old: Schema, new: Schema, mode: str) -> List[str]:
    """Violations of ``mode`` (``backward`` | ``forward`` | ``full`` | ``none``)."""
    if mode not in ("backward", "forward", "full", "none"):
        raise ValueError(f"unknown compatibility mode '{mode}'")
    out: List[str] = []
    for c in compatibility(old, new).changes:
        if mode in ("backward", "full") and c.breaks_backward:
            out.append(f"{c.field}: {c.kind} ({c.detail}) breaks backward compatibility")
        if mode in ("forward", "full") and c.breaks_forward:
            out.append(f"{c.field}: {c.kind} ({c.detail}) breaks forward compatibility")
    return out


@dataclass(frozen=True)
class DriftReport:
    unknown_columns: Dict[str, int] = field(default_factory=dict)
    missing_required: Dict[str, int] = field(default_factory=dict)
    null_violations: Dict[str, int] = field(default_factory=dict)
    type_mismatches: Dict[str, int] = field(default_factory=dict)
    rows: int = 0

    @property
    def clean(self) -> bool:
        return not (self.unknown_columns or self.missing_required
                    or self.null_violations or self.type_mismatches)

    def findings(self) -> List[str]:
        out: List[str] = []
        for label, counts in (("unknown column", self.unknown_columns),
                              ("missing required column", self.missing_required),
                              ("null in non-nullable column", self.null_violations),
                              ("type mismatch", self.type_mismatches)):
            out += [f"{label} '{c}': {n}/{self.rows} rows" for c, n in sorted(counts.items())]
        return out


def detect_drift(schema: Schema, rows: Sequence[Mapping[str, Any]]) -> DriftReport:
    """Compare delivered rows to the declared schema before loading them."""
    fields = schema.by_name()
    unknown: Dict[str, int] = {}
    missing: Dict[str, int] = {}
    nulls: Dict[str, int] = {}
    mism: Dict[str, int] = {}
    for row in rows:
        for col in row:
            if col not in fields:
                unknown[col] = unknown.get(col, 0) + 1
        for name, f in fields.items():
            if name not in row:
                if not f.nullable and not f.has_default:
                    missing[name] = missing.get(name, 0) + 1
                continue
            val = row[name]
            if val is None:
                if not f.nullable:
                    nulls[name] = nulls.get(name, 0) + 1
                continue
            ok = isinstance(val, _PY_TYPES[f.type])
            if f.type != "bool" and isinstance(val, bool):
                ok = False  # bool is an int subclass; do not accept it as a number
            if not ok:
                mism[name] = mism.get(name, 0) + 1
    return DriftReport(unknown, missing, nulls, mism, len(rows))


def evolve_rows(
    old: Schema, new: Schema, rows: Sequence[Mapping[str, Any]]
) -> List[Dict[str, Any]]:
    """Read old-schema rows with the new schema (backward read), or raise.

    Added fields get their default (or None if nullable); removed fields are
    dropped; widened types are promoted. Refuses when the change is not backward
    compatible, so a breaking change cannot be papered over in a replay.
    """
    violations = check(old, new, "backward")
    if violations:
        raise ValueError("not backward compatible: " + "; ".join(violations))
    nf = new.by_name()
    out: List[Dict[str, Any]] = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for name, f in nf.items():
            if name in row:
                val = row[name]
                if val is not None and f.type in ("float", "double") and isinstance(val, int):
                    val = float(val)
                new_row[name] = val
            else:
                new_row[name] = f.default if f.has_default else None
        out.append(new_row)
    return out


def first_violation(history: Sequence[Schema], mode: str) -> Optional[Tuple[int, List[str]]]:
    """First adjacent pair in a version history that violates ``mode``, if any."""
    for i in range(1, len(history)):
        v = check(history[i - 1], history[i], mode)
        if v:
            return i, v
    return None
