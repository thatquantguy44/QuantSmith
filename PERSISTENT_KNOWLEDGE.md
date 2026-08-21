# Persistent Knowledge

A guide to QuantSmith's institutional-memory system: what it is, what is
actually built versus planned, how to use it today, and how new knowledge gets
captured over time. This file is gated — see [How This File Stays
Honest](#how-this-file-stays-honest) — so the numbers below should never be
more than one commit stale.

## The pitch, in one story

A researcher builds a CRSP-based backtest. The standard query silently
excludes delisted stocks, which introduces survivorship bias. The backtest
looks good; walk-forward validation is 40 points worse. It takes a data
engineer two weeks to find why.

That gets written down once, as a typed record: *"CRSP's default query
excludes delisted stocks; here's the fix."* The next person who touches CRSP
gets that record served into their workflow automatically. Two weeks becomes
two minutes.

That is the entire value proposition. Everything below is how the SDK makes
that story trustworthy rather than a wiki page nobody keeps current.

## Two systems — do not conflate them

| | Workflow memory | Knowledge base |
| --- | --- | --- |
| Standard | [`instructions/workflow_memory.md`](instructions/workflow_memory.md) | [`instructions/knowledge_base.md`](instructions/knowledge_base.md) |
| Holds | Structured facts about *databases, datasets, schemas, fields, and their quirks* | A company's *unstructured* institutional knowledge (docs, memos, wiki pages) |
| Store | [`memory/`](memory/) — typed YAML, committed | External sources declared in `knowledge_sources.yml` |
| Spec | `0002` (store), `0048` (read path), `0049` (write path) | none yet |
| Runtime | [`src/quantsmith/pipelines/workflow_memory.py`](src/quantsmith/pipelines/workflow_memory.py) | none |
| Gate | `memory` | `knowledge` |

The same four `agents/knowledge/` agents are meant to serve both, but **only
the first has a runtime.** This guide is primarily about workflow memory,
since that is the half that exists. See [`docs/handoff.md`](docs/handoff.md)
item 15 for the full initiative, item 17 for exposing it to a team over MCP.

## Current status

*(Derived from the filesystem; the `persistent-knowledge` gate flags this
table if it drifts.)*

| | |
| --- | --- |
| Records in the store | **5** — `memory/_shared/datasets/example_prices/provenance.yaml` (3), `memory/quant_researcher/index.yaml` (2). All reference examples; no real institutional knowledge captured yet. |
| Spec `0048` tasks | **6 of 16 done**, 2 in-progress, 8 todo |
| Acceptance criteria verified | **14 of 23** |
| Runtime functions | `load_records`, `query`, `point_in_time_filter`, `render_context`, `validate` — the full read path |

The honest summary: **the machinery is more mature than the content.** The
read path and, as of `0049`, the write path are both built and tested; the
store itself is still five examples. Populating it with real findings —
now genuinely actionable via `propose`/`promote` rather than only aspirational
— is the highest-leverage next step, ahead of any further machinery.

## Quickstart — using the store today

```python
from quantsmith.pipelines.workflow_memory import (
    load_records, query, render_context, point_in_time_filter,
)
import pathlib, datetime

records = []
for path in [
    "memory/_shared/datasets/example_prices/provenance.yaml",
    "memory/quant_researcher/index.yaml",
]:
    records += load_records(pathlib.Path(path).read_text(), path)

# What do we know about this field?
volume_facts = query(records, scope="field:volume")

# What was knowable as of a given date? (the point-in-time firewall)
safe_for_2020_backtest = query(records, status=None, as_of=datetime.date(2020, 1, 1))

# Render into something an agent prompt can carry, budget in characters
print(render_context(safe_for_2020_backtest, budget_chars=2000))
```

Run it yourself: `PYTHONPATH=src python3 -c "..."` from the repo root, or see
`tests/test_workflow_memory.py` for more examples.

## Why point-in-time matters here specifically

**A memory store is itself a leakage vector.** Knowledge recorded in 2026 did
not exist in 2020 — serving it to a 2020 backtest is a future leak, the same
class of bug `instructions/point_in_time.md` exists to prevent everywhere else
in the SDK.

The fix is not "exclude everything before its `first_seen` date" — that is
too strict in one direction and too lax in the other. Instead, the rule
depends on what *kind* of record it is:

- **Mechanical facts** (`schema`, `quirk`, `pitfall`) are timeless. "Join on
  `security_id`, not ticker — tickers get reused" was true in 2005; nobody had
  written it down yet. Excluding it from a 2020 query makes a workflow
  re-learn a fact that was always true, for no safety benefit.
- **Claims about what worked** (`pattern`, `metric`, `performance`) are bounded
  by `last_confirmed`, not `first_seen` — because corroboration is where the
  future enters a record. A momentum pattern first observed in 2018 but
  reconfirmed through 2026 is a 2026 artifact.
- **Decisions** are bounded by `first_seen` — a decision is an event; it
  existed from the moment it was made.

This is enforced in `point_in_time_filter` / `type_rule_admits`, and it is the
one piece of this system verified by mutation testing, not just green tests —
see `tests/test_workflow_memory.py::test_predictive_type_bounded_by_last_confirmed_AC_017`
and its neighbors.

## How new knowledge gets added — today

There is a real write path now (spec `0049`): **propose → stage → promote**,
never automatic.

```sh
python -m quantsmith.pipelines.workflow_memory_cli propose \
  --root memory --workflow quant_researcher --source-run run-2026-08-21-x \
  --scope field:close_adj --type quirk \
  --statement "Adjusted close is restated after the fact." \
  --confidence low --pit-scope "<= run date" \
  --target-catalog _shared/datasets/example_prices/provenance.yaml \
  --evidence-run run-2026-08-21-x
# -> stages memory/inbox/quant_researcher/run-2026-08-21-x.yaml (committed)

python -m quantsmith.pipelines.workflow_memory_cli list-inbox --root memory
python -m quantsmith.pipelines.workflow_memory_cli promote --root memory \
  --candidate-id quant_researcher/run-2026-08-21-x/001
# -> assigns an id, stamps author + first_seen/last_confirmed, appends to
#    the target catalog, removes the candidate from the inbox
```

Staging is committed, so **a pull request touching `memory/inbox/` is the
approval workflow** — reviewed and merged like any other change, with git's
own history as the audit trail. `promote` is always a deliberate, human-run
command; nothing calls it automatically, no matter how confident a proposing
run was. `discard` removes a candidate without promoting it.

One producer is wired end to end today:
`ingestion_data_contract.candidates_from_validation()` turns `0039`'s real
schema violations and failed quality rules into candidates. `walk_forward`,
`fred_point_in_time`, and `factor_risk_model` are next, each a thin
translator against the same generic `CandidateSpec` — see
`specs/0049-workflow-memory-write-path/`'s Follow-ups.

Hand-editing a `records:` list directly still works too (every record needs
`id`, `scope`, `type`, `statement`, `confidence`, `first_seen`,
`last_confirmed`, `status`, `pit_scope` — see
[`instructions/workflow_memory.md`](instructions/workflow_memory.md) and
`memory/_shared/datasets/example_prices/provenance.yaml` for a worked
example) — `promote` is the recommended path because it stamps authorship and
a real id for you and validates before writing anything.

## Roadmap — what's next

Tracked in full in [`docs/handoff.md`](docs/handoff.md) item 15 (initiative)
and the *Planned specs* table. Summary:

| | Status |
| --- | --- |
| **`0048` read path** | Parser, point-in-time filter, `query`, `render_context`, structural validation — **done**. Decay checking (`T-006`), author attribution (`T-007`), the CLI + gate rewiring (`T-009`/`T-010`), contradiction and supersession validation (`T-014`–`T-016`) — **not yet built**. |
| **`0049` write path** | **Done.** `propose_records()`/`stage_candidates()` at the runtime boundary, a committed `memory/inbox/` staging area so pull-request review *is* the approval workflow, `promote()`/`discard()` on human action, author resolution (`resolve_author`), one worked producer (`0039`'s `candidates_from_validation`), a CLI. Built after the read path on purpose — capturing knowledge nobody retrieves would have been the failure mode. |
| **`0052`–`0054` MCP servers** | *Planned, not written.* Exposing this store (and the knowledge-base half) to a team over MCP: a resources server, a memory-graph server with `as_of` honoring the point-in-time rule, a RAG server with per-access-tier indexes. See item 17. |
| **`access_level` enforcement** | Parsed and stored on every record; **`query()` does not filter on it yet.** For a firm with real information barriers this is a blocker before any shared deployment, not a nice-to-have. Belongs with the MCP work, where caller clearance has to be a parameter rather than an assumption. |

## How this file stays honest

The `persistent-knowledge` gate (`hooks/stages/persistent-knowledge-check.sh`)
checks two things:

1. **The numbers above match the filesystem.** Record counts, task
   done/in-progress/todo counts, and acceptance-criteria-verified counts are
   derived independently and compared against what this file states.
2. **A change to the memory system arrives with an update here.** If
   `src/quantsmith/pipelines/workflow_memory.py`, `memory/**/*.yaml`, or
   `specs/0048-workflow-memory-runtime/tasks.md` changes and this file does
   not, the gate flags it — the same co-change pattern `handoff-sync` uses for
   the roadmap.

It cannot check whether the *prose* above is accurate — only the countable
parts and the fact that a related change touched this file. The same honest
limit `docs/handoff.md`'s own `handoff-sync` gate states about itself: this
defends against silence and drift, not against someone writing something
untrue on purpose.

**If you add a record, ship a `workflow_memory.py` function, or move a `0048`
task, update the table above in the same commit.** That is what keeps this a
guide instead of a snapshot.
