"""Identity resolution and read-time viewer clearance (spec 0058).

Owns two things that used to be either scattered or absent:

**Who is running this process.** Relocated here, unchanged, from
``workflow_memory.py`` (spec 0049): ``resolve_author``/``derive_handle`` and
the pseudonymous-handle pattern. They moved so a *second* consumer — read-time
clearance, below — can use the exact same identity without
``workflow_memory.py`` and this module importing from each other in a cycle.
``workflow_memory.py`` re-exports both names unchanged; every existing caller
(the CLI, ``0049``'s ``promote``, existing tests) is unaffected.

**What they can see.** ``access_level`` has existed on every ``0048`` record
and every ``0056`` research item since those specs shipped, and nothing ever
enforced it — ``0048``'s own spec named this explicitly and deferred it
*"until a caller exists that has a level to enforce against."* ``0057`` built
two. This module is what makes ``access_level`` real: a committed
``access/roster.yml`` maps a resolved handle to a clearance
(``public`` < ``internal`` < ``restricted``), and
:func:`resolve_viewer_clearance` + :func:`access_level_allows` are what
``workflow_memory.query`` and both ``knowledge_console`` view-model builders
call to filter by it.

**Enforcement is opt-in and fails closed.** No roster, or a roster naming
nobody yet, is defined as *inactive* — every read path behaves exactly as it
did before this spec (spec REQ-004). The moment the roster names one person,
filtering activates for *everyone*, listed or not (REQ-005); an identity that
resolves but isn't listed gets the roster's declared ``default_clearance``,
never full access by omission (REQ-007). Every ambiguity anywhere in this
module — an unresolvable identity, an unrecognised ``access_level`` on an
item, an unrecognised clearance value — resolves toward *less* visibility,
never more (NFR-005).

Standard library only, matching every other module in this package.
"""

from __future__ import annotations

import getpass
import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Clearance vocabulary (spec REQ-001, REQ-002)
# --------------------------------------------------------------------------

#: The one canonical, ordered definition every enforcement point uses.
ACCESS_LEVELS = ("public", "internal", "restricted")
_ACCESS_RANK = {level: i for i, level in enumerate(ACCESS_LEVELS)}


def access_level_allows(item_level: str, viewer_clearance: str) -> bool:
    """Whether a viewer at ``viewer_clearance`` may see an item at ``item_level``.

    Visible iff the item's level is at or below the viewer's clearance in the
    ``public`` < ``internal`` < ``restricted`` ordering. Fails closed on
    either side of an ambiguity (spec NFR-005): an unrecognised ``item_level``
    is treated as the *most* restrictive tier (least visible), and an
    unrecognised ``viewer_clearance`` is treated as the *least* access
    (``public``) — a malformed value can never accidentally widen what is
    shown.
    """
    item_rank = _ACCESS_RANK.get(item_level, len(ACCESS_LEVELS) - 1)
    viewer_rank = _ACCESS_RANK.get(viewer_clearance, 0)
    return item_rank <= viewer_rank


# --------------------------------------------------------------------------
# Identity resolution (spec 0049 T-001, relocated unchanged for spec 0058)
# --------------------------------------------------------------------------

#: An author/roster handle must be a pseudonymous handle, never a routable
#: address. The pattern is the guard, not a convention (spec 0048 REQ-009).
AUTHOR_HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")

#: Repo-constant salt for handle derivation. Per 0048's own Open Questions this
#: makes handles comparable across clones of *this* repo; a per-store salt
#: would make them uncorrelatable between repositories instead. Starting with
#: the simpler, repo-constant choice — changing it later is a one-line change,
#: not a migration, since handles are derived, never stored raw.
_HANDLE_SALT = "quantsmith-workflow-memory-v1"


def derive_handle(identity: str) -> str:
    """A stable, pseudonymous handle for a source identity (email or username).

    Matches :data:`AUTHOR_HANDLE_RE` by construction: a fixed-length lowercase
    hex digest prefixed with ``u-`` so it always starts with a letter,
    satisfying the pattern's ``[a-z0-9]`` first character regardless of the
    input.

    **Pseudonymous, not anonymous** (0048 RISK-002, inherited unchanged here):
    the same identity always derives the same handle, so a small team is
    re-identifiable from the handle plus commit history. This is convenience
    attribution, not an authentication or privacy guarantee — and, as of
    spec 0058, not an authorization guarantee either (spec Non-Goals).
    """
    digest = hashlib.sha256(f"{_HANDLE_SALT}:{identity.strip().lower()}".encode("utf-8")).hexdigest()
    return f"u-{digest[:24]}"


def _read_identity_config(root: str | os.PathLike = ".") -> Optional[str]:
    """A local-only ``identity.yml`` (gitignored), the ``role_context.yml``
    precedent from spec 0024: a file that may carry a real identity locally
    and must never be committed.

    Deliberately parsed by a tiny, single-purpose reader rather than the
    general YAML-subset parser in ``workflow_memory.py`` — this file only
    ever needs one key (``author:``), and reusing that parser here would
    require this module to import from ``workflow_memory.py`` while
    ``workflow_memory.py`` imports identity resolution *from* this module, a
    real circular import. See ``plan.md``'s Trade-offs.
    """
    path = Path(root) / "identity.yml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line.startswith("author:"):
            continue
        value = line[len("author:"):].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        return value.strip() or None
    return None


def _git_identity() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = out.stdout.strip()
    return value or None


def _os_identity() -> Optional[str]:
    try:
        return getpass.getuser() or None
    except (OSError, ImportError, KeyError):
        return None


def resolve_author(*, override: Optional[str] = None,
                   root: str | os.PathLike = ".") -> Optional[str]:
    """Resolve an author handle, in order: ``override`` (or ``QF_MEMORY_AUTHOR``)
    -> local ``identity.yml`` -> git ``user.email`` -> OS username -> ``None``.

    Never blocks, prompts, or raises (spec 0049 REQ-001, AC-004) — a missing
    identity is a valid outcome, not an error.

    ``override`` and ``QF_MEMORY_AUTHOR`` are both explicit, caller-controlled
    values (a CLI flag, an environment setting a human chose) and are
    returned exactly as given — the same treatment ``0048``'s ``validate``
    already gives any ``author`` field: shape-checked downstream (rejected if
    it contains ``@``, spec 0048 REQ-009), never resolved or sanitised
    upstream, because the caller is asserting a handle, not handing over a
    raw identity to be derived from. Only identities this function discovers
    *itself* (local config, git, OS) — where the raw value is an email or a
    system username, never chosen as a handle — are passed through
    :func:`derive_handle`.

    This is the one identity resolution both write attribution (spec 0049)
    and read clearance (spec 0058) use — the same handle either way.
    """
    if override is not None:
        return override.strip() or None
    env = os.environ.get("QF_MEMORY_AUTHOR")
    if env:
        return env.strip() or None

    for source in (_read_identity_config(root), _git_identity(), _os_identity()):
        if source:
            return derive_handle(source)
    return None


# --------------------------------------------------------------------------
# Roster (spec REQ-003, REQ-004, REQ-005)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Finding:
    """A roster validation result. Mirrors ``workflow_memory.Finding``'s
    shape deliberately (record_id/severity/message/file/line) so the access
    gate and any future tooling can treat both kinds of finding uniformly,
    without this module importing that dataclass and reopening the
    circular-import problem identity resolution already had to solve."""

    entry_handle: str
    severity: str  # "error" | "warn" | "info"
    message: str
    file: str = ""
    line: int = 0


@dataclass(frozen=True)
class RosterEntry:
    handle: str
    label: str
    clearance: str
    source_line: int = 0


@dataclass(frozen=True)
class Roster:
    """A resolved ``access/roster.yml``.

    ``enforced`` is ``True`` iff ``entries`` is non-empty (spec REQ-004/005) —
    the single flag every caller checks before doing any filtering work at
    all. A roster that exists but names nobody yet is, by definition,
    identical to no roster.
    """

    entries: Tuple[RosterEntry, ...] = ()
    default_clearance: str = "public"
    enforced: bool = False
    source_file: str = ""


_ROSTER_RELATIVE_PATH = Path("access") / "roster.yml"


def _strip_comment(raw: str) -> str:
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


def _dequote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text


def _parse_roster_text(text: str, file: str) -> Tuple[List[RosterEntry], str]:
    """Parse the roster's specific, small shape: top-level ``default_clearance:``
    scalar and a ``people:`` list of ``handle``/``label``/``clearance`` triples.

    Deliberately not the general ``workflow_memory`` YAML subset (see
    :func:`_read_identity_config`'s docstring for why) — this format is a
    flat list of 3-field records, simple enough that a small dedicated
    parser is lower-risk here than importing the general one and reopening a
    circular dependency.
    """
    default_clearance = "public"
    entries: List[RosterEntry] = []
    current: Optional[Dict[str, object]] = None
    in_people = False

    def flush():
        if current is None:
            return
        entries.append(RosterEntry(
            handle=str(current.get("handle", "")),
            label=str(current.get("label", "")),
            clearance=str(current.get("clearance", "")),
            source_line=int(current.get("_line", 0)),
        ))

    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.strip()

        if indent == 0:
            flush()
            current = None
            in_people = False
            if content == "people:":
                in_people = True
                continue
            if ":" in content:
                key, _, value = content.partition(":")
                if key.strip() == "default_clearance":
                    default_clearance = _dequote(value)
            continue

        if not in_people:
            continue

        if content.startswith("- "):
            flush()
            current = {"_line": lineno}
            body = content[2:].strip()
            if ":" in body:
                key, _, value = body.partition(":")
                current[key.strip()] = _dequote(value)
            continue

        if current is not None and ":" in content:
            key, _, value = content.partition(":")
            current[key.strip()] = _dequote(value)

    flush()
    return entries, default_clearance


def load_roster(root: str | os.PathLike = ".") -> Roster:
    """Load ``access/roster.yml`` under ``root``.

    Missing file, unreadable file, or a file with zero ``people:`` entries
    all resolve to the same thing: an inactive roster (spec REQ-004) —
    ``enforced=False``, so every caller's filtering step becomes a no-op.
    """
    path = Path(root) / _ROSTER_RELATIVE_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return Roster()

    entries, default_clearance = _parse_roster_text(text, str(path))
    if default_clearance not in ACCESS_LEVELS:
        default_clearance = "public"

    return Roster(
        entries=tuple(entries),
        default_clearance=default_clearance,
        enforced=len(entries) > 0,
        source_file=str(path),
    )


def validate_roster(roster: Roster) -> List[Finding]:
    """Structural validation of a loaded roster (spec REQ-008, REQ-009).

    Reports every problem rather than stopping at the first, matching
    ``workflow_memory.validate``'s own posture.
    """
    findings: List[Finding] = []
    seen: Dict[str, int] = {}

    for entry in roster.entries:
        where = {"file": roster.source_file, "line": entry.source_line}

        if not entry.handle or "@" in entry.handle or not AUTHOR_HANDLE_RE.match(entry.handle):
            findings.append(Finding(
                entry.handle or "<empty>", "error",
                f"handle {entry.handle!r} is not a pseudonymous handle — an "
                "address or free text must never be committed to the roster "
                "(see workflow_memory_cli whoami)", **where))

        if entry.handle in seen:
            findings.append(Finding(
                entry.handle, "error",
                f"duplicate handle (also on line {seen[entry.handle]})", **where))
        else:
            seen[entry.handle] = entry.source_line

        if entry.clearance not in ACCESS_LEVELS:
            findings.append(Finding(
                entry.handle, "error",
                f"unknown clearance {entry.clearance!r}; expected one of "
                f"{', '.join(ACCESS_LEVELS)}", **where))

    return findings


# --------------------------------------------------------------------------
# Viewer clearance resolution (spec REQ-006, REQ-007)
# --------------------------------------------------------------------------

def resolve_viewer_clearance(*, override: Optional[str] = None,
                             root: str | os.PathLike = ".",
                             roster: Optional[Roster] = None) -> Optional[str]:
    """The current viewer's clearance, or ``None`` if enforcement is inactive.

    ``None`` is a distinct, deliberate return value from every real clearance
    string (spec plan.md's Interfaces) — it is the caller's signal to skip
    filtering entirely, so "not enforced" can never be silently confused with
    "public clearance" (which *would* filter out internal/restricted items).

    ``override`` may be a roster handle (to preview what a specific person
    sees) or a bare clearance level (``public``/``internal``/``restricted``,
    to preview a clearance directly without a roster entry) — spec REQ-014.
    """
    roster = roster if roster is not None else load_roster(root)
    if not roster.enforced:
        return None

    if override in ACCESS_LEVELS:
        return override

    handle = resolve_author(override=override, root=root)
    if handle is None:
        return roster.default_clearance

    for entry in roster.entries:
        if entry.handle == handle:
            return entry.clearance if entry.clearance in ACCESS_LEVELS else roster.default_clearance

    return roster.default_clearance
