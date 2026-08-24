# Persistent Knowledge

A guide to QuantSmith's institutional-knowledge systems — what is actually
built versus planned, how to use each one today, and how new knowledge gets
captured over time. This file is gated — see [How This File Stays
Honest](#how-this-file-stays-honest) — so the numbers below should never be
more than one commit stale.

Four things live under this umbrella, and the rest of this guide is organized
in the order they were built:

1. **Workflow memory** (`0002`/`0048`/`0049`) — the structured store and its
   read/write runtime. The oldest, most complete piece.
2. **The knowledge console & terminal** (`0057`) — two read-only front ends
   over that store: a reference web console and a Bloomberg-terminal-style app.
   Per-person viewer access control (`0058`) enforces both stores' `access_level`
   field at the same read boundary these front ends already read through.
3. **Market research & color** (`0056`, Draft) — a fictional-content-only
   reference store demonstrating the target schema for user notes, firm
   research, and tagged email color; exposed in the terminal's Research view.
4. **The general knowledge base** (`instructions/knowledge_base.md`) — the
   broader, unstructured-document standard. Still has no runtime; see
   [Two systems](#two-systems--do-not-conflate-them) below.

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
| Holds | Structured facts about *databases, datasets, schemas, fields, and their quirks* | A company's *unstructured* institutional knowledge (docs, memos, wiki pages, market research, market color) |
| Store | [`memory/`](memory/) — typed YAML, committed | Domain-specific: [`research/`](research/) (market research, reference-only) today; general sources via `knowledge_sources.yml`; the rest, none yet |
| Spec | `0002` (store), `0048` (read path), `0049` (write path), `0058` (viewer access control) | `0056` (market research, **Draft**, reference implementation only) — its `access_level` field is enforced by `0058` too |
| Runtime | [`src/quantsmith/pipelines/workflow_memory.py`](src/quantsmith/pipelines/workflow_memory.py), [`src/quantsmith/pipelines/access_control.py`](src/quantsmith/pipelines/access_control.py) | [`src/quantsmith/knowledge_console/research.py`](src/quantsmith/knowledge_console/research.py) (reads `research/` only — no MCP interface, entitlement enforcement, or email connector; see [Market research & color](#market-research--color-spec-0056--reference-only) below) |
| Gate | `memory` | `knowledge` (external sources) |
| Front end | [Knowledge console & terminal](#the-front-end--knowledge-console--terminal-spec-0057) (spec `0057`) reads **both** stores | same front end |

The same four `agents/knowledge/` agents are meant to serve both eventually,
but today workflow memory has the complete loop (write → read → view) and the
knowledge base has one narrow, reference-only slice (market research) with a
UI over it and no ingestion/retrieval runtime behind the rest. See
[`docs/handoff.md`](docs/handoff.md) item 15 for the full initiative, item 17
for exposing it to a team over MCP.

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

## The front end — knowledge console & terminal (spec 0057)

Everything above is a Python library. `0057` is what makes it *visible* —
two independent, **read-only** front ends over the same data, both sourced
from the same view-model so they cannot drift into disagreeing with each
other:

| | `web/` — reference console | `apps/knowledge-console/` — terminal |
| --- | --- | --- |
| Stack | Vite + React, plain CSS | Vite + React Router + Tailwind (custom Bloomberg-terminal `term.*` design system) + Zustand |
| Server | `quantsmith.knowledge_console.server` (stdlib `http.server`) | Custom Node HTTP server, file-system-routed `/api/*`, that **shells out to the same Python CLI** rather than re-implementing the model |
| Views | Overview, Trends, Graph, Changes, Review, Ask (6) | Overview, Trends, Graph, Changes, Review, **Research**, Ask (7) |
| Offline mode | Self-contained single-file snapshot (`window.__KB_MODEL__`) | Same pattern (`window.__KB_MODEL__` / `window.__KB_RESEARCH__`), hash-routed |
| SDK dependency | None — build tooling only, quarantined to `web/` | None — build tooling only, quarantined to `apps/knowledge-console/` |

Both read the **workflow memory** store (counts, trends, a records↔scope↔
evidence-run knowledge graph, a git changes feed, and a needed-review queue
built from `0048`'s own curation signals — freshness decay, unsupported
confidence, thin corroboration). The terminal additionally has a **Research**
view onto the market-research reference store (see below) that the reference
console does not carry.

Neither front end can write. The Review queue is deliberately read-only —
confirming or retiring a record needs a reviewer identity and audit trail,
which is `0049`'s design (a human runs `promote`/`discard`), not a button in
a UI. **Ask**, in both front ends, answers from a grounded keyword engine
that cites real record ids and says "nothing matched" rather than guessing —
a `QueryEngine` protocol a real LLM engine can register behind later with no
UI or API change.

Run either: `python -m quantsmith.knowledge_console serve` (reference
console) or `npm run dev` / `npm start` in `apps/knowledge-console/` (terminal,
needs `PYTHONPATH` set to `src/` so its Node server can shell out to Python).
See `src/quantsmith/knowledge_console/README.md` and
`apps/knowledge-console/README.md`.

## Market research & color (spec 0056 — reference only)

`0056-market-research-knowledge-base` (status: **Draft**) is the
knowledge-base half for user notes, firm research, fund-manager letters,
sell-side research, generated summaries, and explicitly tagged email market
color. It is a real, substantial spec — an MCP interface, per-access-tier
storage, entitlement enforcement, an email connector — **none of which is
built.**

What exists is a small, honest reference: [`research/`](research/) — 8
fictional items (fake authors, fake firms, fake tickers; see
`research/README.md`) spanning every `source_type` the spec names
(`user_note`, `firm_research`, `fund_manager`, `sell_side`, `generated`,
`email_tagged`), plus one superseded pair and one quarantined item, so the
schema — asset class, source type, access level, review status, provenance,
supersession — has something real and filterable to render. It is read by
`src/quantsmith/knowledge_console/research.py` and shown in the terminal's
**Research** view (`/api/research`), which carries its own on-page disclaimer
naming exactly what is and is not real.

**Absent, by design, until `0056` is actually built:** the
`knowledge://market_research/...` MCP namespace, entitlement/information-
barrier enforcement before retrieval, real secret/PII/MNPI quarantine
detection (the one quarantined reference item is hand-labeled, not detected),
an email connector, and audit logging. **Real firm, client, fund-manager,
MNPI, or licensed research content must never be committed to `research/`** —
see `research/README.md` and `0056`'s own Non-Goals.

## Roadmap — what's next

Tracked in full in [`docs/handoff.md`](docs/handoff.md) item 15 (initiative)
and the *Planned specs* table. Summary:

| | Status |
| --- | --- |
| **`0048` read path** | Parser, point-in-time filter, `query`, `render_context`, structural validation — **done**. Decay checking (`T-006`), the CLI + gate rewiring (`T-009`/`T-010`), contradiction and supersession validation (`T-014`–`T-016`) — **not yet built**. |
| **`0049` write path** | **Done.** `propose_records()`/`stage_candidates()` at the runtime boundary, a committed `memory/inbox/` staging area so pull-request review *is* the approval workflow, `promote()`/`discard()` on human action, author resolution (`resolve_author` — this closed `0048`'s own outstanding REQ-007/REQ-008), one worked producer (`0039`'s `candidates_from_validation`), a CLI. Built after the read path on purpose — capturing knowledge nobody retrieves would have been the failure mode. |
| **`0057` front end** | **Done.** Reference console (`web/`) and Bloomberg-terminal app (`apps/knowledge-console/`), both read-only, both sourced from the same Python view-model. See [The front end](#the-front-end--knowledge-console--terminal-spec-0057) above. Per-viewer access-level enforcement is now built (`0058`, below); the approval *action* (write-back UI) remains a named, deferred gap. |
| **`0058` viewer access control** | **Done.** A committed, opt-in `access/roster.yml` maps a resolved pseudonymous handle (`0049`'s identity resolution, unchanged) to a `public`/`internal`/`restricted` clearance, enforced once at the read boundary in `workflow_memory.query()` and both `0057` view-model builders. Inactive with no roster or an empty one (today's behavior, unchanged); activates for every viewer, not only listed ones, the moment the roster names one person. `whoami` and `preview-access` CLI commands, an `access-check.sh` gate. Explicitly not authentication — same local-per-person trust model `0049` established for write attribution. See `specs/0058-viewer-access-control/`. |
| **`0059` morning market brief** | **Done.** The first real runtime slice of `0056`'s generated-summaries flow (`src/quantsmith/pipelines/market_brief.py`): free-API commentary (NewsAPI, Alpha Vantage `NEWS_SENTIMENT`, Finnhub) → a deterministic headline set and sentiment rollup → grounded analysis from a new `agents/economists/morning_brief_writer/` agent → a `pending_review` candidate staged to a local-only, gitignored root, never `research/`. Does not build `0056`'s promotion mechanics, MCP exposure, or entitlement enforcement. See `specs/0059-morning-market-brief/`. |
| **`0056` market research** | *Draft — reference implementation only.* Real spec (MCP namespace, entitlement enforcement, email connector, quarantine detection) not built; a small fictional-content-only `research/` store + terminal view exists to prove the schema. `0058` enforces its `access_level` field the same way it does workflow memory's; `0059` builds its first generated-content producer. See [Market research & color](#market-research--color-spec-0056--reference-only) above. |
| **`0052`–`0054` MCP servers** | *Planned, not written.* Exposing workflow memory and the knowledge base to a team over MCP: a resources server, a memory-graph server with `as_of` honoring the point-in-time rule, a RAG server with per-access-tier indexes. `0058`'s roster is designed to be reusable by this work, not replaced by it — real authentication for a shared/multi-tenant deployment is still this work's job, not `0058`'s. See item 17. |

## How this file stays honest

The `persistent-knowledge` gate (`hooks/stages/persistent-knowledge-check.sh`)
checks two things:

1. **The numbers above match the filesystem.** Record counts, task
   done/in-progress/todo counts, and acceptance-criteria-verified counts are
   derived independently and compared against what this file states.
2. **A change to any of the four systems arrives with an update here.** If
   `src/quantsmith/pipelines/workflow_memory.py` or `workflow_memory_cli.py`,
   `memory/**/*.yaml`, `specs/0048-workflow-memory-runtime/tasks.md`,
   `src/quantsmith/knowledge_console/*`, `web/src/*`,
   `apps/knowledge-console/src/*`, or `research/*.yaml` changes and this file
   does not, the gate flags it — the same co-change pattern `handoff-sync`
   uses for the roadmap.

It cannot check whether the *prose* above is accurate. And unlike the
workflow-memory numbers, it has **no independent ground truth for the
front-end/research sections at all** — there is no analogous "true count" of
terminal views or research items it derives from the filesystem the way it
does record and task counts, so any number stated in those two sections is
asserted, not gate-checked; only *that* a related change touched this file is
verified, never *what* was written. This defends against silence and drift,
not against someone writing something untrue on purpose — the same honest
limit `docs/handoff.md`'s own `handoff-sync` gate states about itself.

**If you add a record, ship a `workflow_memory.py` function, move a `0048`
task, change a front-end view, or touch the research reference store, update
the relevant section above in the same commit.** That is what keeps this a
guide instead of a snapshot.
