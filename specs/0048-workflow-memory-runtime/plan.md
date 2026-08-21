# Plan: Workflow Memory Runtime & Author Attribution

- **Spec:** 0048-workflow-memory-runtime (`spec.md`)
- **Last updated:** 2026-08-21

> HOW. Architecture, contracts, and the trade-offs taken.

## Shape

One module, `src/quantsmith/pipelines/workflow_memory.py`, plus one identity
helper. It follows the pattern every other `pipelines/` runtime uses: frozen
dataclasses in, frozen dataclasses out, standard library only, no I/O beyond
reading the files it is pointed at.

```
load_store(root)                      -> Store          REQ-001
query(store, ...)                     -> tuple[Record]  REQ-002, REQ-003
render_context(records, budget_chars) -> str            REQ-004
validate(store)                       -> tuple[Finding] REQ-005, REQ-009, REQ-010
check_decay(store, as_of)             -> tuple[Finding] REQ-006
resolve_author(env, root)             -> Author         REQ-007, REQ-008
store_version(store)                  -> str            REQ-011
```

`validate` and `check_decay` are separate because they answer different
questions — "is this record well-formed?" versus "is this record still true?" —
and a gate may want to enforce the first while only advising on the second.

## Data contracts

```python
@dataclass(frozen=True)
class Record:
    id: str
    scope: str                  # "dataset:x" | "table:x" | "field:x"
    type: str                   # schema|quirk|pattern|pitfall|decision|metric|performance
    statement: str
    evidence: tuple[Mapping[str, str], ...]  # source_run + optional sample_query
    confidence: str             # low|medium|high
    corroboration_count: int    # as DECLARED in the file
    first_seen: date
    last_confirmed: date
    status: str                 # active|stale|superseded|retired
    pit_scope: str
    access_level: str           # inherited from the manifest when absent
    author: str | None          # NEW (0048) — handle, never an email
    superseded_by: str | None   # NEW (0048) — required when status=superseded
    coexists: tuple[str, ...]   # NEW (0048) — deliberate contradiction exemption
    source_file: str            # provenance for findings; not a memory field
    source_line: int

    @property
    def corroboration_derived(self) -> int:
        return len({e["source_run"] for e in self.evidence if "source_run" in e})
```

Every new field is appended and optional, so every file `0002` committed parses
unchanged (NFR-003). A record without an author is a finding (REQ-010), not an
error — the existing store predates the field, and failing on it would make the
gate unusable on day one.

`evidence` becomes a tuple, but the parser accepts `0002`'s single-mapping form
and wraps it (REQ-014, AC-022), so no committed file needs editing.

**Declared and derived corroboration are kept side by side rather than one
replacing the other.** `corroboration_count` stays as written; `corroboration_derived`
counts distinct `source_run` values. Validation compares them (REQ-015). This is
the `0047` lesson applied: a number a human typed is a claim, and a claim that
cannot be checked against anything is exactly how `schema_version` could have
gone stale unnoticed. Here it *is* checkable, so it is checked — and the
committed store fails the check on day one (RISK-008), which is the gate
working, not the gate being wrong.

`Finding` reuses the shape the other gates' runtimes use: `severity`, `code`,
`message`, `record_id`, `source_file`, `source_line`.

## The YAML subset

No PyYAML (NFR-001), so the parser supports exactly the grammar the committed
files use:

- `key: value` mappings, two-space indentation
- `- ` list items, one level, each opening a mapping
- one level of nested mapping (`evidence:` → `source_run:`)
- `#` comments and blank lines
- scalars: bare, `'single'`, or `"double"` quoted; no block scalars, no anchors,
  no flow collections, no multi-document files

Anything else raises `MemoryParseError(file, line, reason)`. **This is the
central trade-off (RISK-001):** a permissive parser that guesses would let a
malformed record through as a plausible-looking one, and wrong memory is worse
than absent memory. Loud failure keeps the blast radius at "this file did not
load" instead of "this field means something else now". The committed store is
the parser's fixture set, so the subset is pinned by real files rather than by
an author's imagination.

## Point-in-time filtering (REQ-003, REQ-016, RISK-004, RISK-006)

**A memory store is itself look-ahead.** Knowledge recorded in 2026 did not
exist in 2020; serving it to a 2020 backtest leaks the future. This is the
subtlest leak in the whole design, and a single `first_seen <= as_of` rule gets
it wrong in *both* directions. The `type` field already carries the distinction:

| `type` | Nature | Rule under `as_of` | Why |
| --- | --- | --- | --- |
| `schema`, `quirk`, `pitfall` | Mechanical facts about how the data is built | **Always admissible** | "Join on `security_id`, tickers get reused" was true in 2005; you merely hadn't written it down. Excluding it makes a backtest re-learn it or get it wrong — a worse outcome with no leakage benefit. |
| `pattern`, `metric`, `performance` | Claims about what worked | `last_confirmed <= as_of` | These encode outcomes. Bound on `last_confirmed`, not `first_seen`: **corroboration is where the future enters a record.** A pattern first seen in 2018 but confirmed through 2026 is a 2026 artifact. |
| `decision` | A choice made at a point in time | `first_seen <= as_of` | A decision is an event; it existed from the moment it was made. |

A record must clear this rule **and** the `pit_scope` rule (REQ-016):

| `pit_scope` | Behaviour under `as_of` |
| --- | --- |
| `<= run date`, `<= decision date` | Admissible |
| `original vintage only` | **Excluded** — depends on unrevised vintage data |
| anything else | **Excluded**, and reported as a validation finding |

Unrecognised means excluded, never included. A missing record makes a workflow
ask again; a leaked record makes a backtest lie, and P4 forbids that. Because
the two rules are independent and both must pass, `pit_scope` being free text
cannot admit a record that the type rule excludes — the weaker check cannot
override the stronger one.

The strictness in row two is knowingly conservative: a pattern whose statement
never actually changed between 2018 and 2026 is excluded anyway, because
without record versioning there is no way to tell. That is the honest trade,
and record versioning (a Non-Goal here) is what would replace exclusion with
serving the contemporaneous version instead.

## Contradiction and supersession (REQ-012, REQ-013, RISK-007)

`instructions/workflow_memory.md` says "a contradiction flags it" and "no silent
overwrite — contradictions are resolved to `superseded`, not deleted". Neither is
implementable today: nothing looks for contradictions, and `status: superseded`
has nothing to point at. `superseded_by` closes the second half, and makes the
first half resolvable rather than merely reportable.

**Detection is structural, not semantic.** Two `active` records sharing `scope`
and `type` occupy the same slot: one field, one kind of claim, two live
statements. That is detectable with a dict and no model in the loop. What it
cannot do is decide whether they actually conflict — `field:volume` may
legitimately carry three distinct quirks.

So the finding is `info` severity and reads as *adjudicate this pair*, not
*this is broken*. Two properties keep it from becoming noise:

- **It is self-quieting.** Resolving a pair by marking one `superseded` removes
  it from the `active` set, so the pair is never reported again. Each pair costs
  one adjudication, ever.
- **`coexists` is an explicit exemption.** A pair that is deliberately both live
  names the other id, and the finding stops. Silencing is a reviewable line in
  the file, not achieved by deleting a record — which is exactly the "no silent
  overwrite" property the standard asks for.

Supersession validation: `status: superseded` requires `superseded_by`; the
target must resolve to a record that exists; and the graph must be acyclic
(A superseded by B superseded by A is two records both claiming to be obsolete,
leaving no current answer). All three are AC-021.

## Ranking and rendering (REQ-004, RISK-005)

Records are ranked by, in order: `confidence` (high > medium > low),
**`corroboration_derived`** descending, `last_confirmed` descending, then `id`
ascending as a total-order tiebreak — so the ordering is deterministic
(NFR-002) rather than dependent on filesystem or dict iteration order.

Ranking on the derived count rather than the declared one is the point: the
declared number is a claim, and retrieval order should not be settable by typing
a larger integer. `confidence` remains human-set and therefore still gameable —
REQ-015 constrains it by flagging `high` on a single evidence entry, but it is
a check, not a derivation. Stated plainly so nobody mistakes the ranking for a
measurement of usefulness (RISK-005).

`render_context` emits one line per record — id, scope, type, statement,
confidence, `last_confirmed` — and fills up to `budget_chars`, then appends
`"... N further record(s) omitted (ranked below the included set)."` The budget
is in characters, not tokens: the module has no tokenizer and will not pretend
to. Callers converting tokens to characters own that ratio.

Showing `last_confirmed` on every line is not decoration — it is how a reader
discounts an old record when the decay gate is only advisory (RISK-003).

## Identity resolution (REQ-007, REQ-008)

A chain, first hit wins, each step total:

| Order | Source | Handle produced |
| --- | --- | --- |
| 1 | `QF_MEMORY_AUTHOR` env var | used verbatim (must satisfy the pattern) |
| 2 | `identity.yml` at repo root — local-only, gitignored | `author:` used verbatim |
| 3 | `git config user.email` | derived, pseudonymous |
| 4 | OS username (`getpass.getuser()`) | derived, pseudonymous |
| 5 | nothing resolvable | `None` → REQ-010 finding |

Steps 1–2 give the **opaque handle** path: a person picks `jl`, and the
handle↔person table lives outside the repository. Steps 3–4 are the automatic
path for anyone who has not configured one, so attribution works with zero
setup.

Derivation: `"anon-" + sha256(salt + normalized_identity).hexdigest()[:10]`,
where `normalized_identity` is lowercased and stripped. Stable for the same
input (AC-011), distinct for different inputs (AC-012), and — because the output
is hex — **structurally incapable of containing `@`** (AC-013). That is the
point: the PII guard is not "remember not to paste your email", it is "an email
cannot survive this function".

Step 1 is checked before any subprocess runs, so CI and agent contexts never
shell out to git (AC-010, NFR-004). `git config` is invoked with a timeout and
its failure is a fall-through, not an error — a copied scaffold with no git
still resolves an author.

**The handle is pseudonymous, not anonymous.** On a ten-person desk, handle plus
commit history re-identifies the author trivially. The module docstring says so
in those words (RISK-002); a reader who believes otherwise will store something
they shouldn't.

## Gate wiring

`memory-check.sh` currently greps for field names. It gains a Python path:

```sh
if python3 -c 'import quantsmith' 2>/dev/null; then
  python3 -m quantsmith.pipelines.workflow_memory --validate --decay --as-of "$(date -u +%F)"
else
  # existing grep-based checks, unchanged
fi
```

The grep path stays as the fallback for a copied scaffold with no package
installed — consistent with "gates degrade gracefully when optional tools are
missing" (`docs/handoff.md`, Conventions To Preserve). The secret/PII scan is
untouched and keeps running either way; the new `author` validation (REQ-009) is
a second, independent guard over the same property, and AC-013 pins that the two
agree rather than contradict.

## Alternatives considered

- **Add PyYAML.** Rejected: every `pipelines/` runtime is dependency-free, and
  the scaffold is copied into repos that may not install extras. The subset
  parser is ~80 lines against a fixed fixture set.
- **Store author as the raw git email.** Rejected: it puts PII in a committed
  store and would require narrowing the existing PII scan — weakening a guard to
  add a feature.
- **SQLite index alongside the Markdown/YAML.** Deferred. At the current
  store size a linear scan is instant, and a second copy of the data is a
  synchronisation problem. Revisit when a store's scan time is measurable.
- **Rewrite `memory-check.sh` entirely in Python.** Rejected: it would strand
  adopters who copy the scaffold without the package.

## Test strategy

`tests/test_workflow_memory.py`, one test per AC, named `test_..._AC_0NN`,
matching the repo's convention. The committed `memory/` store is the primary
fixture (AC-001 asserts it parses with no edits); malformed cases are built in
`tmp_path` so no broken YAML is committed. Identity tests inject a fake
environment and never touch the real git config.
