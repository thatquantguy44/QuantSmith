# Plan: Viewer Access Control

- **Spec:** 0058-viewer-access-control (`spec.md`)
- **Status:** Approved
- **Author:** quantsmith
- **Last updated:** 2026-08-21

> HOW. This plan requires an approved `spec.md`. Every requirement in the spec
> appears in the traceability matrix below.

## Approach

A new module, `access_control.py`, becomes the single owner of two things
that were previously either absent or scattered: *who is running this
process* (relocated from `workflow_memory.py`, unchanged) and *what can they
see* (new). Nothing about `0049`'s identity resolution changes — it moves
house so a second consumer (read-side clearance) can use it without
`workflow_memory.py` and the new module importing from each other in a
cycle. `workflow_memory.py` re-exports the relocated names so no existing
import breaks.

Enforcement itself is deliberately **not** pushed into `query()`'s or the
view-model builders' pure cores as an implicit, filesystem-touching step —
that would make every existing test (0048's 26, 0057's suite) start doing
disk I/O and risk nondeterminism creeping into functions whose whole point is
determinism (`0048` NFR-002, `0057` NFR-004). Instead, each pure function
gains one new *optional, plain-value* parameter (`viewer_clearance: Optional[str]`),
defaulting to `None` (`= see everything`, today's behavior, unchanged). The
*_from_root* / server-facing wrappers — which already touch disk to load the
store — are where `access_control.resolve_viewer_clearance()` actually runs,
and they pass the resolved string down into the pure core. This keeps the
"filter once, at the boundary" property from the spec's Goals while keeping
every existing pure-function test passing byte-for-byte.

## Architecture & Components

```
                    access/roster.yml  (committed, opt-in)
                            |
                  access_control.load_roster()
                            |
        +-------------------+--------------------+
        v                                         v
resolve_author()                    resolve_viewer_clearance()
(relocated from workflow_memory,      (new: resolve_author() -> handle,
 re-exported there unchanged)          look up in roster, apply
        |                               default_clearance, fail closed)
        |                                         |
        v                                         v
 0049 promote() (writes, unchanged)   access_level_allows(item_level, clearance)
                                                   |
                    +------------------------------+------------------------------+
                    v                                                             v
     workflow_memory.query(records, viewer_clearance=None)      knowledge_console.model.build_model(
     -- pure, no I/O; unchanged when clearance omitted             store, viewer_clearance=None) -- pure
                    ^                                                             ^
                    |                                                             |
     workflow_memory.query_as_of_root(...)  [I/O wrapper, NEW,       knowledge_console.model.build_model_from_root(...)
      used only where a caller has a root path                        resolves viewer_clearance via
      but no clearance yet resolved]                                  access_control, then calls build_model()
                                                                                    |
                                                                     knowledge_console.research.build_research_model(
                                                                       store, viewer_clearance=None) -- pure, same pattern
                                                                                    |
                                                                     knowledge_console.research.build_research_model_from_root(...)
```

Both `web/`'s stdlib server and the terminal's Node server (which shells out
to `python -m quantsmith.knowledge_console print|research`) call the
`_from_root` wrappers exclusively — so enforcement lands in both front ends
by touching two Python functions, with zero JavaScript/TypeScript changes on
either side. This is the same "one Python source of truth, two thin clients"
architecture `0057` already established for the data itself; this spec
extends it to cover clearance too.

## Interfaces & Data Contracts

```python
# access_control.py

ACCESS_LEVELS = ("public", "internal", "restricted")

def access_level_allows(item_level: str, viewer_clearance: str) -> bool: ...
    # unrecognized item_level -> treated as "restricted" (least visible);
    # unrecognized viewer_clearance -> treated as "public" (least access) --
    # both directions fail toward LESS visibility (spec NFR-005).

# relocated from workflow_memory.py, behavior unchanged:
AUTHOR_HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
def derive_handle(identity: str) -> str: ...
def resolve_author(*, override=None, root=".") -> Optional[str]: ...

@dataclass(frozen=True)
class RosterEntry:
    handle: str
    label: str
    clearance: str

@dataclass(frozen=True)
class Roster:
    entries: Tuple[RosterEntry, ...]
    default_clearance: str
    enforced: bool          # True iff entries is non-empty (spec REQ-004/005)
    source_file: str

def load_roster(root: str | PathLike = ".") -> Roster: ...
    # missing file or empty `people:` -> Roster(entries=(), default_clearance="public",
    # enforced=False, source_file="")

def resolve_viewer_clearance(*, override: Optional[str] = None,
                              root: str | PathLike = ".",
                              roster: Optional[Roster] = None) -> Optional[str]:
    ...
    # Returns None when roster.enforced is False (caller's signal to skip
    # filtering entirely -- distinct from a real clearance string, so "not
    # enforced" can never be confused with "public clearance").

def validate_roster(roster: Roster) -> List[Finding]: ...
    # Finding reused from workflow_memory (imported, not redefined) --
    # duplicate handle, unrecognized clearance, email/free-text-shaped handle.
```

```python
# workflow_memory.py (extended)
def query(records, *, scope=None, type=None, min_confidence=None,
          status="active", as_of=None,
          viewer_clearance: Optional[str] = None) -> List[Record]: ...
    # unchanged filters, then: if viewer_clearance is not None, drop any
    # record where access_control.access_level_allows(r.access_level,
    # viewer_clearance) is False.

# re-exported, not reimplemented:
from .access_control import AUTHOR_HANDLE_RE, derive_handle, resolve_author  # noqa: F401
```

```python
# knowledge_console/model.py (extended)
def build_model(store, *, as_of=None, changes=None, generated_at=None,
                 viewer_clearance: Optional[str] = None) -> Dict: ...
    # pure; filters store.records by viewer_clearance (when not None) before
    # computing counts/trends/graph/review_queue/findings -- REQ-011.

def build_model_from_root(root="memory", *, as_of=None, generated_at=None,
                           with_changes=True,
                           viewer_override: Optional[str] = None) -> Dict: ...
    # I/O wrapper: loads the roster, resolves viewer_clearance (honoring
    # viewer_override as an explicit handle/clearance for preview -- REQ-014),
    # then calls build_model(..., viewer_clearance=resolved).
```

```python
# knowledge_console/research.py (extended, identical pattern)
def build_research_model(store, *, as_of=None, generated_at=None,
                          viewer_clearance: Optional[str] = None) -> Dict: ...
def build_research_model_from_root(root="research", *, as_of=None,
                                    generated_at=None,
                                    viewer_override: Optional[str] = None) -> Dict: ...
```

**Time-alignment / leakage:** unaffected — clearance filtering is orthogonal
to the point-in-time firewall (`0048` REQ-003) and is applied independently;
a record must clear *both* the `as_of` bound and the clearance check to be
returned, same "both must pass" composition `0048`'s own
`point_in_time_filter` already uses for `pit_scope` + type rules.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Fail-closed on every ambiguity (NFR-005); enforcement composes with existing filters rather than replacing them; the pure/impure split means a test exercising `query(..., viewer_clearance=...)` cannot accidentally hit the filesystem. |
| P5 Reversibility | yes | `access/roster.yml` is an ordinary committed file, edited and reviewed like `memory/inbox/` candidates; deleting it (or emptying `people:`) reverts to today's unfiltered behavior exactly (REQ-004). |
| P6 Observability | yes | REQ-013 (who-am-I) and REQ-014 (preview) make the *effect* of a roster change inspectable before and after it merges; the access gate (REQ-015) makes a malformed roster a visible CI finding, not a silent misconfiguration. |
| P9 Security & data | yes | This spec's entire purpose is closing a named, real access-control gap. Explicitly not authentication (spec Non-Goals) — stated plainly rather than implied. Reuses, never duplicates, `0049`'s pseudonymity guarantee (NFR-002). |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `ACCESS_LEVELS` canonical tuple in `access_control.py` | T-001 |
| REQ-002 | `access_level_allows()` | T-001 |
| REQ-003 | `load_roster()` + small dedicated roster parser | T-002 |
| REQ-004, REQ-005 | `Roster.enforced` flag, computed from entry count | T-002 |
| REQ-006 | relocated `resolve_author()`/`derive_handle()`, re-exported from `workflow_memory` | T-001 |
| REQ-007 | `resolve_viewer_clearance()` default-clearance fallback | T-003 |
| REQ-008, REQ-009 | `validate_roster()` | T-003 |
| REQ-010 | `query(..., viewer_clearance=...)` | T-004 |
| REQ-011 | `build_model(..., viewer_clearance=...)`, `build_research_model(..., viewer_clearance=...)`, and their `_from_root` wrappers | T-005 |
| REQ-012 | no change needed — filtering removes items pre-render; existing badge rendering is untouched | T-005 (verified, not built) |
| REQ-013 | CLI `whoami` subcommand | T-006 |
| REQ-014 | CLI `--viewer-override` on `print`/`research`/`query`; `preview-access` subcommand | T-006 |
| REQ-015 | `hooks/stages/access-check.sh` | T-007 |
| NFR-001 | stdlib only throughout | T-001..T-007 |
| NFR-002 | relocation, not duplication, of identity code | T-001 |
| NFR-003 | plain-value `viewer_clearance` param on every pure function | T-004, T-005 |
| NFR-004 | full existing suite re-run unmodified as a regression gate | T-008 |
| NFR-005 | unrecognized-value handling in `access_level_allows`/`resolve_viewer_clearance` | T-001, T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Where identity code lives | New `access_control.py`; `workflow_memory.py` re-exports | Duplicate `derive_handle`/salt into a new module | A second copy of a security-relevant hash risks silent drift (two salts = two incompatible handle spaces) — moving once, re-exporting, is the only option with zero duplication risk. |
| Where filtering happens | Pure functions take a plain `viewer_clearance` string; only `_from_root` wrappers touch disk/env | Filtering inside `query()`/builders by resolving from disk internally | Keeps `0048` NFR-002 and `0057` NFR-004's determinism guarantees intact and avoids adding filesystem I/O (and its failure modes) to functions whose existing tests assume none. |
| Enforcement default | Opt-in: absent/empty roster = unfiltered (today's behavior) | Enforcement on by default, deny-all until configured | An unannounced behavior change the moment this spec ships would lock out every existing solo deployment of the scaffold. Opt-in with a documented, safe default (RISK-002) is the adoption-friendly and honest choice. |
| Roster identity | Pseudonymous handle (same as write attribution) | Raw email/username in the roster | Reuses `0048`/`0049`'s existing pseudonymity guarantee rather than reopening the exact PII surface those specs closed (RISK-003). |
| Roster parser | Small, dedicated parser in `access_control.py` | Reuse `workflow_memory.parse_memory_file` | Reusing it would require `access_control.py` to import from `workflow_memory.py`, which already needs to import identity helpers *from* `access_control.py` — a real circular import. The roster's shape (flat 3-field records) is simple enough that a small dedicated parser is lower risk than a larger shared-parser extraction refactor under this spec's scope. |

## Validation Strategy

`tests/test_access_control.py`, one test per AC, named `test_..._AC_0NN`,
plus targeted additions to the existing `0048`/`0057` test files for the new
optional parameters (kept in those files since they exercise `query`/
`build_model`/`build_research_model` directly, not `access_control` itself):

- Identity/vocabulary: AC-001 (ordering), AC-005–AC-007 (resolution +
  fallback + no-raise), AC-008–AC-009 (roster validation findings).
- Opt-in/fail-open-until-configured: AC-002, AC-003, AC-004 — run against
  real fixture trees (empty, absent, and one-entry rosters), never mocked.
- Enforcement at the boundary: AC-010 (`query`), AC-011 (both view-model
  builders, asserting the restricted item is absent from the *serialized
  JSON*, not merely unflagged), AC-012 (the single-file snapshot build).
- REQ-012 (badge still shows on visible items) verified as a regression
  check against `0057`'s existing render tests — no new UI test needed,
  since nothing about *how* a visible item renders changes.
- CLI: AC-014 (`whoami` output matches `resolve_author()`'s own return value
  for the same environment, asserted by calling both and comparing), AC-015
  (preview command against a fixture roster + fixture store).
- Gate: AC-016, AC-017 — fixture roster files under `tmp_path`, `access-check.sh`
  run via `subprocess` exactly as `0049`'s gate test runs `memory-check.sh`.

**Regression gate (NFR-004):** the full pre-existing suite (290 tests as of
`0049`) is run unmodified at the end of implementation; zero of them may
change behavior or require edits to keep passing, since every new parameter
introduced defaults to preserving prior behavior.

## Rollout, Observability & Rollback

- **Rollout:** additive. `access/roster.yml` ships with zero entries
  (enforcement inactive) — adopting the spec's *code* and adopting its
  *enforcement* are two separate, independently reversible steps; a team
  opts into enforcement by adding their first roster line.
- **Observability:** `whoami` and the preview command make the system's
  current behavior inspectable on demand; the access gate surfaces roster
  problems in the same PR that introduces them.
- **Rollback:** delete `access/roster.yml` (or empty its `people:` list) to
  fully disable enforcement without touching code. Reverting the code itself
  means deleting `access_control.py`, the re-exports in `workflow_memory.py`,
  the new optional parameters (all additive, all default to prior behavior),
  and `access-check.sh`.
- **Blast radius:** zero to any deployment that never creates a roster; for
  one that does, blast radius is exactly the people and content named in
  that roster, reviewed via the same PR process as everything else.

## Open Questions

- Multiple handles per person, and time-boxed/expiring clearance — both
  named in spec.md's Open Questions, deferred as roster-editing-frequency
  problems rather than mechanism gaps.
- Whether `0056`'s `entitlement_class` (e.g. "vendor-licensed") should later
  compose with clearance rather than staying a separate, unenforced field —
  explicitly out of scope here (spec Assumptions).
