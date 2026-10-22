"""Access and data handling: caller clearance, column redaction, scrubbing.

Spec ``0115`` REQ-009–REQ-011 (realizing ``0113`` REQ-017, NFR-004, RISK-006).

* **Clearance** comes from a ``0058`` roster (``access.clearance_source``):
  ``default_clearance`` plus ``people: [{handle, clearance, roles}]`` with the
  ordering ``public < internal < restricted``. As in ``0058``, a roster with no
  people means enforcement is *inactive*; a named roster that cannot be read
  fails closed (the caller is treated as ``public``). Unknown handles get the
  default; an unrecognised clearance value resolves to ``public``.
* **Column classes** — ``access.column_classes`` maps ``table.column`` to a
  redaction class and ``access.redaction_classes`` maps each class to the
  clearance it requires. A caller below that clearance never sees the
  column's values: research treats it as sensitive (values withheld,
  parameters redacted) and :func:`redact_rows` masks it in any result rows.
* **Scrubbing** — :func:`scrub` removes credential-shaped text (URI
  passwords, ``password=``/``token=``-style pairs, bearer tokens) from any
  string the plugin writes to a trace, log, or bundle.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import yamlsubset

__all__ = ["LEVELS", "Caller", "allows", "caller", "column_requirements", "redact_rows", "scrub", "scrub_value",
           "withheld_columns"]

LEVELS = ("public", "internal", "restricted")
_RANK = {level: i for i, level in enumerate(LEVELS)}
REDACTED = "<redacted>"

_URI_CRED = re.compile(r"(://[^/\s:@]+:)[^/\s@]+(@)")
_PAIR_CRED = re.compile(r"(?i)\b(password|passwd|pwd|token|api[_-]?key|secret|access[_-]?key)(\s*[=:]\s*)([^\s,;&'\"]+)")
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}")


def allows(item_level: str, clearance: str) -> bool:
    """Whether ``clearance`` may see an item at ``item_level`` (unknown levels deny)."""
    return item_level in _RANK and clearance in _RANK and _RANK[clearance] >= _RANK[item_level]


@dataclass(frozen=True)
class Caller:
    handle: str
    clearance: str
    active: bool                       # False: no roster or an empty roster (0058 REQ-004)
    source: str | None = None
    roles: tuple = ()
    notes: tuple = field(default_factory=tuple)

    def sees(self, level: str) -> bool:
        return not self.active or allows(level, self.clearance)

    def as_dict(self) -> dict[str, Any]:
        return {"handle": self.handle, "clearance": self.clearance if self.active else "unrestricted",
                "enforcement": "active" if self.active else "inactive", "roles": list(self.roles),
                "source": self.source, "notes": list(self.notes)}


def caller(config: Any, handle: str) -> Caller:
    """Resolve ``handle``'s clearance from the configured ``0058`` roster."""
    source = config.data.get("access", {}).get("clearance_source")
    if not source:
        return Caller(handle, "unrestricted", False, None)
    path = config.resolve_path(source)
    try:
        roster = yamlsubset.parse(Path(path).read_text(encoding="utf-8"), str(path)) or {}
    except (OSError, yamlsubset.YamlSubsetError) as exc:
        return Caller(handle, "public", True, source, notes=((f"roster unreadable ({type(exc).__name__}); "
                                                             "failing closed to public"),))
    people = roster.get("people") or []
    if not people:
        return Caller(handle, "unrestricted", False, source)
    default = roster.get("default_clearance", "public")
    default = default if default in _RANK else "public"
    for person in people:
        if isinstance(person, dict) and person.get("handle") == handle:
            level = person.get("clearance")
            return Caller(handle, level if level in _RANK else "public", True, source,
                          tuple(person.get("roles") or ()))
    return Caller(handle, default, True, source)


def column_requirements(config: Any) -> dict[str, dict[str, str]]:
    """``table.column`` (lower case) -> ``{class, level}`` from the access section."""
    access = config.data.get("access", {})
    classes = access.get("redaction_classes") or {}
    out = {}
    for col, cls in sorted((access.get("column_classes") or {}).items()):
        out[col.lower()] = {"class": cls, "level": classes.get(cls, "restricted")}   # unknown class: most restrictive
    return out


def _table_of(obj: str) -> str:
    return obj.rsplit(".", 1)[-1].lower()


def withheld_columns(config: Any, who: Caller, obj: str, columns: Sequence[str]) -> list[str]:
    """Columns of table/view ``obj`` whose values ``who`` may not see."""
    reqs = column_requirements(config)
    table = _table_of(obj)
    out = []
    for c in columns:
        req = reqs.get(f"{table}.{c.lower()}") or reqs.get(f"{obj.lower()}.{c.lower()}")
        if req and not who.sees(req["level"]):
            out.append(c)
    return out


def redact_rows(rows: Sequence[Mapping[str, Any]], withheld: Sequence[str]) -> list[dict[str, Any]]:
    hidden = set(withheld)
    return [{k: (REDACTED if k in hidden and v is not None else v) for k, v in r.items()} for r in rows]


def scrub(text: str) -> str:
    text = _URI_CRED.sub(rf"\1{REDACTED}\2", text)
    text = _PAIR_CRED.sub(rf"\1\2{REDACTED}", text)
    return _BEARER.sub(rf"\1{REDACTED}", text)


def scrub_value(value: Any) -> Any:
    """``scrub`` applied to every string inside ``value``."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, dict):
        return {k: scrub_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub_value(v) for v in value]
    return value
