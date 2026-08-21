# Plan: Workflow Memory Write Path

- **Spec:** 0049-workflow-memory-write-path (`spec.md`)
- **Status:** Approved
- **Author:** quantsmith
- **Last updated:** 2026-08-21

> HOW. This plan requires an approved `spec.md`. Every requirement in the spec
> appears in the traceability matrix below.

## Approach

Four pieces, in dependency order:

1. **Identity** (`resolve_author`, `derive_handle`) — finishes `0048`
   REQ-007/REQ-008 directly in `workflow_memory.py`, since `promote` cannot
   stamp an author without it. Resolution order: `QF_MEMORY_AUTHOR` env →
   local `identity.yml` (gitignored, `role_context.yml` precedent) → `git
   config user.email` → OS username (`getpass.getuser()`) → `None`. A resolved
   email/username is never stored raw — `derive_handle` runs it through a
   stable, repo-constant-salted hash into the same pattern `0048`'s `validate`
   already enforces (`_AUTHOR_RE`), reusing that constant rather than
   duplicating it.

2. **Candidates** (`Candidate` dataclass, `propose_records`) — a candidate is
   deliberately **not** a `Record`. It carries what a proposer knows at
   observation time (`scope`, `type`, `statement`, `confidence`, `pit_scope`,
   `evidence`, `target_catalog`) and omits what only a reviewer can supply
   (`id`, `author`, `first_seen`). This is the type-level enforcement of
   NFR-005: there is no code path that turns a `Candidate` into a live
   `Record` except `promote`.

3. **Staging** (`stage_candidates`, `load_inbox`) — candidates serialize to
   `memory/inbox/<workflow>/<source_run>.yaml` using a small deterministic
   writer (sorted keys where order doesn't carry meaning, stable field order
   otherwise) so two stagings of identical input are byte-identical (NFR-003).
   `load_inbox` walks `memory/inbox/**/*.yaml` and parses each with `0048`'s
   existing `parse_memory_file` — no second parser.

4. **Promotion** (`promote`, `discard`) — `promote` is the one function that
   touches a live catalog file. It: validates the candidate would become a
   legal `Record` (reusing `0048`'s `validate` machinery on the hypothetical
   result), assigns an id, resolves/stamps author and dates, appends one YAML
   list entry to the target catalog by rewriting that file's `records:` list
   with the new entry added (parsed via `parse_memory_file`, re-serialized
   deterministically — existing entries pass through unchanged in content,
   even though the file is rewritten), and rewrites the source inbox file with
   that one candidate removed. `discard` is the same inbox-rewrite half
   without any live-catalog write.

A thin CLI (`workflow_memory_cli.py`) wraps these four pieces for a human.
`ingestion_data_contract.py` gets one pure function
(`candidates_from_validation`) translating its own result type into the
generic candidate-input shape — the worked producer integration.

## Architecture & Components

```
              CandidateSpec (scope, type, statement, confidence,
              pit_scope, evidence, target_catalog)
                        |
         propose_records(specs, workflow, source_run)
                        v
                  Candidate (in memory, nothing written)
                        |
         stage_candidates(candidates) --------> memory/inbox/<workflow>/<run>.yaml
                        |                                  |
                        |                        load_inbox() reads it back
                        v                                  |
                     (PR opened, reviewed, merged — the approval workflow)
                        |                                  |
                        v                                  v
              promote(candidate, source_file)     discard(candidate, source_file)
                        |                                  |
                        v                                  v
        memory/<target_catalog>.yaml            memory/inbox/.../<run>.yaml
        gains one Record (id, author,             loses that one candidate,
        first_seen/last_confirmed stamped)         nothing else changes
```

`ingestion_data_contract.candidates_from_validation(result, dataset_scope,
source_run, target_catalog) -> List[CandidateSpec]` sits upstream of
`propose_records`, translating `SchemaViolation`/`QualityRuleResult` into
`pitfall`/`quirk` candidate specs. It imports `workflow_memory`'s
`CandidateSpec`; `workflow_memory` does not import anything from
`ingestion_data_contract` — the dependency runs one way, keeping the memory
module the generic, reusable side.

## Interfaces & Data Contracts

```python
@dataclass(frozen=True)
class CandidateSpec:
    scope: str
    type: str                          # one of 0048's RECORD_TYPES
    statement: str
    confidence: str                    # one of 0048's CONFIDENCE_LEVELS
    pit_scope: str
    evidence: Tuple[Mapping[str, str], ...]
    target_catalog: str                # path relative to memory/, e.g.
                                        # "quant_researcher/index.yaml" or
                                        # "_shared/datasets/example_prices/provenance.yaml"
    access_level: str = "internal"

@dataclass(frozen=True)
class Candidate:
    spec: CandidateSpec
    workflow: str
    source_run: str
    proposed_at: datetime.date         # today, at propose_records() time —
                                        # informational only; NOT first_seen

def resolve_author(*, override: Optional[str] = None) -> Optional[str]: ...
def derive_handle(identity: str) -> str: ...

def propose_records(specs: Sequence[CandidateSpec], *, workflow: str,
                     source_run: str) -> List[Candidate]: ...

def stage_candidates(candidates: Sequence[Candidate], *,
                      root: str = "memory") -> Path: ...   # returns the file written/updated

def load_inbox(root: str = "memory") -> List[Tuple[Candidate, str]]: ...  # (candidate, source_file)

@dataclass(frozen=True)
class PromotionResult:
    record: Record
    contradiction_warning: Optional[str]  # REQ-010; None when no collision

def promote(candidate: Candidate, *, source_file: str, root: str = "memory",
            author: Optional[str] = None,
            as_of: Optional[datetime.date] = None) -> PromotionResult: ...
    # raises MemoryWriteError (new, ValueError subclass) on REQ-009 refusal

def discard(candidate: Candidate, *, source_file: str,
            root: str = "memory") -> None: ...
```

`ingestion_data_contract.py` adds:

```python
def candidates_from_validation(
    result: IngestionValidationResult, *, dataset_scope: str,
    source_run: str, target_catalog: str,
) -> List[CandidateSpec]: ...
```

**Time-alignment / leakage:** `first_seen`/`last_confirmed` are stamped at
promotion time, never backdated to the observation run (RISK-006) — this is
the conservative direction under `0048`'s P4 firewall reasoning: it can only
exclude a candidate from an `as_of` query it might legitimately belong in,
never admit one early. `pit_scope` on a candidate passes through unchanged
from proposal to promotion; `promote` does not infer or widen it.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | `Candidate` cannot become a `Record` outside `promote`; `promote` reuses `0048`'s own `validate` rather than a parallel check, so the write path can never accept something the read path would reject. `first_seen` stamped conservatively late (RISK-006), never early. |
| P5 Reversibility | yes | Every write lands in git history (staging and promotion are both ordinary committed file changes); `discard` is a normal file edit; nothing bypasses version control (NFR-002/NFR-005). |
| P6 Observability | yes | AC-016's CLI output and REQ-015's gate coverage make both "what's pending" and "what's broken" visible without opening YAML by hand — extending `0057`'s console's own observability role to the write side, on the read side only (the console itself stays read-only). |
| P9 Security & data | yes | No credential, no network call (NFR-002). Author resolution never stores a raw email/username (RISK-003, inherits `0048`'s RISK-002 caveat explicitly rather than silently). |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `resolve_author()` resolution chain | T-001 |
| REQ-002 | `derive_handle()`, reusing `0048`'s `_AUTHOR_RE` | T-001 |
| REQ-003 | `CandidateSpec` dataclass | T-002 |
| REQ-004 | `propose_records()` | T-002 |
| REQ-005 | `stage_candidates()` deterministic YAML writer | T-003 |
| REQ-006 | `load_inbox()` | T-003 |
| REQ-007 | `promote()` id assignment, stamping, catalog append | T-004 |
| REQ-008 | `promote()` inbox-file rewrite | T-004 |
| REQ-009 | `promote()` validate-before-write + collision check | T-004 |
| REQ-010 | `promote()` contradiction check via `0048` scope+type scan | T-004 |
| REQ-011 | `discard()` | T-005 |
| REQ-012 | `ingestion_data_contract.candidates_from_validation()` | T-006 |
| REQ-013 | `workflow_memory_cli.py` | T-007 |
| REQ-014 | `templates/docs/run_card.md` "Memory proposed" line | T-008 |
| REQ-015 | `hooks/stages/memory-check.sh` inbox validation | T-009 |
| NFR-001 | stdlib only throughout | T-001..T-007 |
| NFR-002 | no network/DB in any new function | T-001..T-005 |
| NFR-003 | deterministic YAML writer (sorted/stable field order) | T-003, T-004 |
| NFR-004 | catalog rewrite preserves untouched entries verbatim in content | T-004 |
| NFR-005 | `Candidate`/`Record` type separation; no auto-promote caller | T-002, T-004 |
| NFR-006 | `MemoryWriteError` with file/id/reason; gate reports inbox findings | T-004, T-009 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Candidate vs. Record | A separate, lighter `Candidate` type | Reuse `Record` with optional `id`/`author`/`first_seen` | Reusing `Record` would make every `0048` consumer (`query`, `validate`, `render_context`) defend against half-populated records forever. A distinct type makes "not yet real" a compile-time fact, not a runtime check everywhere else has to remember. |
| Target catalog | Caller-supplied, explicit `target_catalog` on `CandidateSpec` | Infer the catalog from `scope`/`workflow` | Inference is guessable-wrong (a `field:*` scope doesn't name its dataset directory) in a way that would silently misfile a record. The proposer already knows where its own finding belongs. |
| `first_seen` timing | Stamped at promotion | Stamped at proposal (the observation date) | Roadmap-consistent and conservative under `0048`'s leakage reasoning (RISK-006): a candidate isn't "known" by the store until a human accepted it. |
| Contradiction handling | Warn, don't block (REQ-010) | Refuse to promote until resolved | Mirrors `0048`'s own RISK-007 stance: many same-scope-same-type pairs legitimately coexist (three real quirks on one field). Blocking by default would train people to route around the check. |
| Approval mechanism | Git PR review over `memory/inbox/`, plus a local `promote` CLI | A bespoke approval-state UI/DB | The repository already has a reviewed-merge workflow; building a second one duplicates it for no new guarantee, and contradicts `0057`'s console staying read-only. |

## Validation Strategy

`tests/test_workflow_memory_write_path.py`, one test per AC, named
`test_..._AC_0NN`:

- Identity: AC-001 (env override short-circuits), AC-002 (git-derived handle,
  pattern + no `@` + stable), AC-003 (different identities → different
  handles), AC-004 (no identity → `None`, no raise).
- Candidates/staging: AC-005 (propose writes nothing), AC-006 (staged file
  parses via `0048`'s parser), AC-007 (byte-identical restaging), AC-008
  (inbox never leaks into `query`/`point_in_time_filter`).
- Promotion: AC-009 (id/author/dates stamped, sibling records untouched —
  asserted by diffing the target file's other entries before/after), AC-010
  (inbox file loses only the promoted one), AC-011 (missing-field refusal),
  AC-012 (id-collision refusal), AC-013 (contradiction warns, still
  promotes), AC-014 (discard removes one, leaves the rest).
- Producer integration: AC-015, run against a real `validate_ingestion` call
  with a deliberately broken row set (real schema violation, real failed
  rule), not a hand-built `IngestionValidationResult`.
- CLI: AC-016, driven with `subprocess` against a `tmp_path` scratch
  `memory/` tree (never the real one), one invocation per subcommand.
- Docs/gate: AC-017 (template contains the new field — a static content
  check, not a renderer test, matching how other run-card fields are
  verified), AC-018 (gate run against a fixture inbox file with a missing
  field, asserting the finding names the file).

All tests stdlib + pytest, no new dependency, no network.

## Rollout, Observability & Rollback

- **Rollout:** additive to `workflow_memory.py`; new files
  (`workflow_memory_cli.py`, `memory/inbox/` convention, this spec's test
  file) with no changes to existing `0048`/`0057` call sites or their tests.
- **Observability:** the CLI's `list-inbox` is the day-to-day visibility tool;
  the memory gate (REQ-015) is the CI-time one.
- **Rollback:** delete `workflow_memory_cli.py`, the four new functions plus
  `CandidateSpec`/`Candidate`/`PromotionResult`/`MemoryWriteError` from
  `workflow_memory.py`, and `memory/inbox/` if anything was ever staged.
  `0048`'s read path and `0057`'s console are untouched either way — they
  never call anything this spec adds.
- **Blast radius:** zero to the live store until the first `promote` call;
  even then, one record append per call, always inside a normal git commit.

## Open Questions

- Batch-promote (one inbox file, many candidates, one call) — deferred per
  spec's Open Questions; add if one-at-a-time proves tedious in practice.
- CLI `--force` past a contradiction warning — starting without one (spec
  Open Questions); add only if the warn-don't-block default causes real
  friction.
