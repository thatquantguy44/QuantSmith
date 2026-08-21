# Plan: Knowledge Console — analytics & UI for the memory store

- **Spec:** 0057-knowledge-console (`spec.md`)
- **Status:** Approved
- **Author:** quantsmith
- **Last updated:** 2026-08-21

> HOW. This plan requires an approved `spec.md`. Every requirement in the spec
> appears in the traceability matrix below.

## Approach

A three-layer design, each layer testable on its own and importing (never
re-implementing) the `0048` `workflow_memory` runtime:

1. **Model layer** (`src/quantsmith/knowledge_console/model.py`) — a filesystem
   store-loader plus a pure view-model builder. `load_store(root)` walks a
   `memory/` tree per its `manifest.yaml`, reads each `index.yaml`/
   `provenance.yaml` with `workflow_memory.load_records`, and returns records
   tagged with their workflow and source file. `build_model(store, as_of)`
   turns that into one JSON-serialisable dict: counts, trends, graph, changes,
   review queue, findings. It is a pure function of (store, as_of, changes) so it
   is trivially deterministic (NFR-004) and reused verbatim by both the live API
   and the static build.

2. **Query layer** (`src/quantsmith/knowledge_console/query.py`) — the NL-query
   seam. A `QueryEngine` protocol (`answer(question, records, k) -> Answer`), a
   `KeywordQueryEngine` implementation (term-overlap ranking, grounded, empty on
   no match), and `resolve_engine()` which returns a registered LLM engine if one
   exists (via `register_engine`/an env hook) and the keyword engine otherwise.
   This is the pluggable point: a future LLM engine implements the protocol and
   registers; nothing else changes.

3. **Serve layer** (`server.py`, `__main__.py`) — a stdlib
   `ThreadingHTTPServer` with a hand-rolled router: `GET /api/model`,
   `GET /api/health`, `POST /api/query`, and static file serving for the built
   front end (with directory-traversal protection). No third-party web
   framework.

The **front end** (`web/`, Vite + React + TypeScript) is a single-page app with
six views. It fetches `/api/model` when served, or reads an embedded
`window.__KB_MODEL__` when opened as a static snapshot. All charts and the graph
are drawn with hand-written SVG/Canvas — no chart library, no CDN (NFR-002).

The **static build** is produced by `scripts/build_console_snapshot.py` (or the
`__main__` `snapshot` subcommand): run the Vite single-file build, then inject
`window.__KB_MODEL__ = <build_model(...)>` into the HTML. The result opens in a
browser with no server and no network (REQ-012) — this is what ships as the
shareable preview and the Artifact.

## Architecture & Components

```
                    memory/ (manifest + index/provenance YAML)      git log
                              |                                         |
        workflow_memory.load_records / Record / validate / query       |
                              v                                         v
  knowledge_console/model.py : load_store() -> Store(records, workflow-tagged)
                              : git_changes(root) -> [Change]
                              : build_model(store, as_of, changes) -> dict
                              |                              |
             +----------------+                             +----------------+
             v                                                               v
  knowledge_console/query.py                              knowledge_console/server.py
   QueryEngine (protocol)                                   GET  /api/health
   KeywordQueryEngine (default)                             GET  /api/model   -> build_model(...)
   resolve_engine() / register_engine()                     POST /api/query   -> resolve_engine().answer
                              |                              GET  /*           -> web/dist static
                              +--------------------------------------+
                                                                     v
                                          web/ (Vite+React+TS SPA), or single-file snapshot
                                          Views: Overview | Trends | Graph | Changes | Review | Ask
```

Responsibilities:

- **model.py** owns *what the data means*: parsing the tree, deriving counts,
  trend series, graph nodes/edges, the review queue, and running `validate`.
  Pure and stdlib-only.
- **query.py** owns *answering in natural language*, grounded in records. The
  keyword engine is the floor; the protocol is the ceiling a real LLM plugs into.
- **server.py** owns *transport*: routing, JSON, static files, loopback binding,
  404s. It holds no domain logic beyond calling model/query.
- **web/** owns *presentation*: rendering the model, drawing charts/graph,
  posting questions. It contains no source of truth — everything it shows comes
  from the model.

## Interfaces & Data Contracts

**`load_store(root: str | Path) -> Store`** — `Store.records` are
`workflow_memory.Record` with `source_file` set and a `workflow` attribution
carried alongside (via a parallel mapping or a light wrapper, since `Record` is
frozen). `Store.freshness_days` comes from the manifest (default 90).

**View-model JSON** (`build_model`) — stable key order, ISO dates, sorted lists:

```jsonc
{
  "generated_at": "<iso8601 UTC>",         // wall clock; excluded from determinism checks
  "as_of": "YYYY-MM-DD",
  "freshness_days": 90,
  "counts": {"total": N, "by_type": {...}, "by_status": {...},
             "by_confidence": {...}, "by_access_level": {...}, "by_workflow": {...}},
  "records": [ {"id","scope","type","statement","confidence",
                "corroboration_count","corroboration_derived","first_seen",
                "last_confirmed","status","pit_scope","access_level","author",
                "workflow","source_file","days_since_confirmed","overdue",
                "evidence_runs":[...]}... ],   // sorted by id
  "trends": {"cumulative_by_date":[{"date","count"}],
             "confirmations_by_month":[{"month","count"}],
             "staleness":{"fresh":n,"overdue":n},
             "by_type_series": {...}},
  "graph": {"nodes":[{"id","label","kind","meta"}], "edges":[{"source","target","kind"}]},
  "changes": [ {"hash","author","date","subject","files":[...]} ],  // newest first
  "review_queue": [ {"record_id","severity","reasons":[...],
                     "scope","type","last_confirmed","access_level"} ],
  "findings": [ {"record_id","severity","message","file"} ]
}
```

**Query contract** (`POST /api/query`, and `QueryEngine.answer`):

```jsonc
// request
{"question": "why not use adjusted close", "k": 5}
// response
{"answer": "<grounded prose or 'Nothing in the store matched ...'>",
 "citations": ["MEM-0002", ...],   // real record ids only; [] when nothing matched
 "mode": "keyword",                // engine identity; a real LLM reports e.g. "llm:<name>"
 "matched": true}
```

`QueryEngine` protocol: `answer(question: str, records: Sequence[Record], k: int)
-> Answer`. The caller passes records **already loaded (and, in a later access-
aware world, already filtered)**, so an engine never widens access. Grounding is
the engine's contract: citations reference only ids present in `records`.

**Time-alignment / leakage:** the console is a *reporting* surface, not a
research input, so it does not feed backtests. It still honours the firewall in
spirit — record detail shows `pit_scope` and `last_confirmed` so a reader never
mistakes a recently-confirmed pattern for a historical one, and the model reuses
`0048`'s constants rather than inventing parallel rules.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | View-model is a pure function of (store, as_of, changes); ordering is total, so output is reproducible (NFR-004, AC-002). No leakage path: the console is read-only reporting and reuses `0048`'s point-in-time vocabulary rather than redefining it. |
| P5 Reversibility | yes | Nothing is written to `memory/` (NFR-003). Removing the console removes a directory; the store is untouched. The static snapshot is a disposable artifact. |
| P6 Observability | yes | The console *is* observability for the store: trends, decay, and a review queue make the store's health legible. `GET /api/health` and honest empty-state rendering (NFR-005) make the console itself observable. |
| P9 Security & data | yes | Stdlib only, loopback bind, directory-traversal-guarded static serving, no secrets. Access level shown on every record; grounding prevents fabricated answers (NFR-006). Residual gap — per-viewer access enforcement — is named, not hidden (RISK-003). |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `load_store()` walks manifest → `load_records` per file, tags workflow/source | T-001 |
| REQ-002 | `build_model()` counts + record detail, pure/deterministic | T-002 |
| REQ-003 | trend derivation (cumulative, confirmations, staleness) in `build_model` | T-002 |
| REQ-004 | `build_graph()` nodes/edges in model layer | T-003 |
| REQ-005 | `git_changes()` subprocess with degrade-to-empty | T-004 |
| REQ-006 | `build_review_queue()` combining freshness + findings + corroboration | T-005 |
| REQ-007 | `server.py` router: `/api/model`, `/api/health`, `/api/query`, static | T-006 |
| REQ-008 | `QueryEngine` protocol + `resolve_engine`/`register_engine` | T-007 |
| REQ-009 | `KeywordQueryEngine` term-overlap, grounded, empty-on-no-match | T-007 |
| REQ-010 | `web/` SPA with six views | T-008, T-009 |
| REQ-011 | `api.ts` embedded-vs-fetch; Ask view server-vs-local fallback | T-008 |
| REQ-012 | single-file snapshot builder injecting `window.__KB_MODEL__` | T-010 |
| REQ-013 | record detail + citations always carry id/source/last_confirmed/access | T-002, T-009 |
| NFR-001 | stdlib-only backend; no `pyproject` deps added | T-001..T-007 |
| NFR-002 | hand-drawn SVG/Canvas; `web/` tooling quarantined | T-009 |
| NFR-003 | read-only; loopback; traversal guard; 404 test | T-006 |
| NFR-004 | total ordering; `generated_at` excluded from determinism | T-002 |
| NFR-005 | empty/absent store & git degrade to empty model | T-001, T-004 |
| NFR-006 | citations reference only real ids; explicit no-match | T-007 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Backend transport | stdlib `http.server` | FastAPI/Flask | NFR-001: no runtime dep, runs in a copied scaffold with nothing installed. The API is three routes; a framework is not earned. |
| Front-end delivery | Vite/React app **and** self-contained single file | server-rendered HTML from Python | The user asked for a real interactive web app; React gives that. The single-file build keeps a shareable, server-less preview and satisfies the Artifact sandbox (REQ-012). |
| Charts/graph | hand-drawn SVG/Canvas | a chart/graph library (d3, recharts) | NFR-002: no CDN, no external host, small bundle, and the single-file build stays self-contained. The store is small enough that bespoke drawing is cheap. |
| NL query v1 | grounded keyword engine behind a protocol | ship an LLM now | Spec Non-Goal: the seam is the deliverable; a model is opt-in later. Keyword is honest, deterministic, and testable, and proves the contract. |
| Approvals | read-only review *queue* | write-back approve/retire | `0048` defers the approval state machine; mutating memory without a reviewer identity + audit trail would be the wrong first move (RISK-001). |

## Validation Strategy

`tests/test_knowledge_console.py`, one test per AC, named `test_..._AC_0NN`:

- Model: AC-001 (load + workflow tagging), AC-002 (byte-identical rebuild),
  AC-003 (counts sum to total), AC-004 (cumulative monotone, ends at total),
  AC-005 (staleness split at 90 days), AC-006 (graph edges), AC-008 (review
  queue reasons), AC-015 (empty store).
- Changes: AC-007 — run against this repo's real git history (non-empty) and
  against a temp dir with no git (empty, no error).
- Server: AC-009 (`/api/model`, `/api/health`), AC-010 (query cites MEM-0002),
  AC-011 (no-match empty citations), AC-014 (404 + traversal guard) — driven with
  `http.client` against an ephemeral server on port 0.
- Query: AC-012 (default engine is keyword).
- Front end: AC-013 is asserted structurally — a test confirms the built/snapshot
  HTML references `window.__KB_MODEL__` and the API module prefers it. (Full DOM
  testing is a follow-up; the data-source contract is what AC-013 pins.)

All backend tests are stdlib + pytest; none require Node. The front-end build is
exercised by the snapshot builder in CI-optional fashion (documented), so a
Node-less checkout still passes the Python suite.

## Rollout, Observability & Rollback

- **Rollout:** additive. New package `knowledge_console`, new `web/` dir, new
  spec, one console entry in `pyproject` scripts. No existing module changes.
- **Observability:** `GET /api/health`; the console surfaces its own empty state;
  the review queue is the store's health dashboard.
- **Rollback:** delete `src/quantsmith/knowledge_console/`, `web/`, the test, and
  the script entry. `memory/` and `workflow_memory` are untouched (P5).
- **Blast radius:** near zero — read-only, loopback, no data written, no runtime
  dependency added.

## Open Questions

- Per-viewer access enforcement (vs. display-only access level) — deferred; named
  in RISK-003 so the gap is visible.
- A real LLM engine's configuration/key location — out of scope; the contract is
  ready for it.
- Large-store graph layout (clustering/LOD) — follow-up if the store outgrows a
  single readable graph.
