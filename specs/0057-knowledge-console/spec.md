# Spec: Knowledge Console — analytics & UI for the memory store

- **ID:** 0057-knowledge-console
- **Status:** Approved
- **Author:** quantsmith
- **Approver:** repository owner
- **Last updated:** 2026-08-21

> WHAT and WHY only. No implementation detail — that belongs in `plan.md`.

## Problem & Context

`specs/0002-workflow-memory/` defined the persistent memory store and
`specs/0048-workflow-memory-runtime/` made it machine-readable — a parser,
typed `Record`s, point-in-time-aware `query`, and `validate`. Two gaps remain,
and both grow with the store:

1. **Nothing shows the store to a human.** Every consumer of `0048` is a
   program (an agent priming a prompt, a gate validating records). A person who
   wants to answer "what does the firm know, how confident is it, what is going
   stale, what needs a second look" must open YAML by hand and hold the whole
   store in their head. That does not scale past the seed records, and it is the
   question a research lead, a reviewer, or a former-skeptic stakeholder
   actually asks. The value of institutional memory is only realised when it is
   *legible*.

2. **The curation lifecycle has no surface.** `instructions/workflow_memory.md`
   names a lifecycle — prime → learn → confirm → **curate** — and `0048`
   produces exactly the signals curation needs (freshness decay, unsupported
   confidence, missing authorship, low corroboration). Nothing collects those
   into a queue a person can work through. Findings exist; a worklist does not.

This spec builds a **read-only web console** over the existing store: analytics
and trends, an interactive knowledge graph, a recent-changes feed, and a
needed-review (approvals) queue — plus a **pluggable natural-language query
seam** that ships with a grounded keyword engine today and accepts a real LLM
backend later without a rewrite. It is deliberately a *reader*: it never mutates
the store (see Non-Goals), so it is safe to run against a live memory tree.

## Goals

- Turn the `0048` runtime into a legible surface: counts, trends, and per-record
  detail, computed from the committed store with no hand-editing of YAML.
- Show the store as a graph — records linked to the datasets, scopes, evidence
  runs, and workflows they belong to — so relationships are visible, not
  reconstructed mentally.
- Surface recent changes to the store (git history over `memory/`) alongside
  each record's own `last_confirmed`, so "what moved lately" is answerable.
- Collect the curation signals `0048` already computes into one **needed-review
  queue**, with the reason each record is on it.
- Answer natural-language questions against the store through a **pluggable**
  query interface: a grounded, citation-first keyword engine by default; a real
  LLM engine registrable later behind the same contract.
- Ship as a runnable web app (a small standard-library API server + a built
  single-page front end) **and** as a self-contained static snapshot that can be
  opened with no server, so the same UI serves both a live tree and a shareable
  preview.

## Non-Goals

- **Writing to the store (an approval *state machine*).** The queue shows what
  needs review and why; it does not confirm, retire, or edit records. Mutating
  memory needs a reviewer identity to route to and an audit trail —
  `specs/0048` explicitly defers the approval workflow to a later spec, and this
  console is its read surface, not that workflow. The UI states plainly that
  actions are advisory.
- **Shipping an LLM.** This spec builds the *seam* (a stable query contract and a
  keyword fallback), not a model, model weights, an API key path, or a vendor
  integration. Wiring a specific model is a later, opt-in change behind the
  contract defined here.
- **Re-implementing the `0048` runtime.** Parsing, typing, point-in-time rules,
  ranking, and validation are `workflow_memory`'s job and are imported, not
  copied. This spec adds a filesystem store-loader and a view/model layer on top.
- **Authentication, multi-user accounts, or write access control.** The console
  is a local/trusted-network read tool for v1; it binds loopback by default and
  serves whatever the running user can already read on disk.
- **Editing the record schema.** No new record fields. Access level is surfaced
  and respected in display; it is not redefined.
- **A charting/graph third-party stack.** No CDN, no runtime chart library — see
  NFR-002. Visualisations are drawn from the store's own data.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Load the whole committed store from a `memory/` root: read `manifest.yaml`, then every `index.yaml`/`provenance.yaml` it governs (shared + per workflow), into `0048` `Record` objects, tagging each record with the workflow (or `_shared`) it came from and its source file. | must |
| REQ-002 | Build one JSON view-model from a loaded store and an as-of date: per-record detail, aggregate counts (by type, status, confidence, access level, workflow), and the store's freshness policy. Deterministic for a fixed store + as-of. | must |
| REQ-003 | Derive trend series from record dates: cumulative record count by `first_seen`, confirmations by month from `last_confirmed`, and a staleness split (fresh / overdue) against `freshness_days` as of the as-of date. | must |
| REQ-004 | Build a graph model: nodes for each record, dataset/scope, evidence run, and workflow; edges linking a record to its workflow, its scope, and each distinct evidence run. Node and edge sets are deterministic. | must |
| REQ-005 | Build a recent-changes feed from git history over `memory/` (commit hash, author, date, subject, changed memory files), degrading to an empty feed — never an error — when git or history is unavailable. | must |
| REQ-006 | Build a needed-review queue: every record carrying at least one curation signal — overdue for re-validation (freshness), a `validate()` error/warn finding, high confidence unsupported by corroboration, or `active` with fewer than two distinct evidence runs — each item naming its reasons and a severity. | must |
| REQ-007 | Expose the whole view-model over an HTTP API from the standard library only: `GET /api/model`, `GET /api/health`, and `POST /api/query`. Read-only; no endpoint mutates the store. | must |
| REQ-008 | Define a natural-language query contract (`question`, optional `k`) → grounded answer with a list of record-id citations and the engine mode used. Resolve the active engine from configuration, falling back to a keyword engine when none is registered. | must |
| REQ-009 | Ship a keyword query engine that ranks records by term overlap over statement/scope/type, returns the top-k as citations, and returns an explicit "nothing matched" answer rather than inventing one when overlap is zero. | must |
| REQ-010 | Serve a single-page front end with distinct views for Overview/analytics, Trends, Knowledge Graph, Recent Changes, Needed Review, and Ask (NL query). | must |
| REQ-011 | The front end reads its data from an embedded `window.__KB_MODEL__` when present, otherwise from `GET /api/model`; the Ask view posts to `/api/query` when served and falls back to an in-browser keyword search when running from an embedded snapshot. | must |
| REQ-012 | Emit a self-contained static build (one HTML file, all CSS/JS inlined, the current view-model embedded, no external network requests) that renders the full UI with no server. | should |
| REQ-013 | Display each record's `access_level` and, in every list and citation, never present a record without its provenance (id, source file, `last_confirmed`), so a shown claim is always traceable. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Backend dependencies | Python standard library only (plus the existing `workflow_memory` module). No new entry in `pyproject.toml` `dependencies`. |
| NFR-002 | Front-end dependencies | No runtime third-party libraries and no external hosts (no CDN, no remote fonts): charts and the graph are drawn from first principles. Build-time dev tooling (Vite/React/TS) is confined to `web/` and never becomes an SDK dependency. |
| NFR-003 | Read-only | No code path writes, deletes, or renames anything under `memory/`. The API binds loopback by default. |
| NFR-004 | Determinism | Identical store + identical as-of ⇒ byte-identical view-model JSON (stable ordering everywhere). |
| NFR-005 | Degradation | A missing `memory/`, absent git, or empty store yields a well-formed empty model, never a stack trace to the user. |
| NFR-006 | Grounding | Every answer the query layer returns carries citations to real record ids or states that nothing matched; it never fabricates a record id. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the committed `memory/` store, when it is loaded, then records from `_shared/datasets/example_prices/provenance.yaml` and `quant_researcher/index.yaml` are all present, each tagged with its workflow (`_shared` or `quant_researcher`) and source file, and no file is edited. | REQ-001 |
| AC-002 | Given a loaded store and a fixed as-of date, when the view-model is built twice, then the two JSON documents are byte-identical. | REQ-002, NFR-004 |
| AC-003 | Given the committed store, when counts are computed, then `by_type`, `by_status`, `by_confidence`, `by_access_level`, and `by_workflow` sum to the total record count. | REQ-002 |
| AC-004 | Given records with known `first_seen` dates, when the cumulative trend is built, then the series is non-decreasing and its final value equals the total record count. | REQ-003 |
| AC-005 | Given a store `freshness_days` of 90 and an as-of date, when the staleness split is computed, then a record last confirmed 200 days earlier is counted overdue and one confirmed 30 days earlier is counted fresh. | REQ-003 |
| AC-006 | Given the committed store, when the graph is built, then every record node has an edge to its workflow node and to its scope node, and evidence-run nodes exist for each distinct `source_run`. | REQ-004 |
| AC-007 | Given a checkout with git history touching `memory/`, when the changes feed is built, then it lists commits newest-first with hash/author/date/subject; given no git, then it is an empty list and no error is raised. | REQ-005, NFR-005 |
| AC-008 | Given the committed store, when the review queue is built, then `MEM-0001` (declared `corroboration_count: 4` on one evidence entry) appears with an unsupported-confidence reason, and any record whose `last_confirmed` is older than `freshness_days` as of the as-of date appears with a freshness reason. | REQ-006 |
| AC-009 | Given the API server over the committed store, when `GET /api/model` is called, then it returns HTTP 200 and a JSON body whose record count matches the loaded store; when `GET /api/health` is called, then it returns 200. | REQ-007 |
| AC-010 | Given the API server, when `POST /api/query` is sent `{"question": "why not use adjusted close"}`, then the response cites `MEM-0002` (the vintage quirk) among its citations and names the engine mode. | REQ-008, REQ-009, NFR-006 |
| AC-011 | Given `POST /api/query` with a question sharing no terms with any record, when answered, then the citations list is empty and the answer states nothing matched — no record id is invented. | REQ-009, NFR-006 |
| AC-012 | Given no LLM engine is registered, when the active engine is resolved, then the keyword engine is returned and the model it reports is `keyword`. | REQ-008 |
| AC-013 | Given the built front end, when it loads with `window.__KB_MODEL__` defined, then it renders from the embedded model and issues no network request for `/api/model`. | REQ-011 |
| AC-014 | Given a request to a path that neither exists as a static asset nor matches an API route, when served, then the server responds 404 without traceback and without reading outside the served directory. | REQ-007, NFR-003 |
| AC-015 | Given an empty or missing `memory/` root, when the view-model is built, then every section is present and empty (zero records, empty trends/graph/changes/queue) and no error is raised. | NFR-005 |

## Data & Dependencies

- **Reads:** `memory/manifest.yaml`, `memory/**/index.yaml`,
  `memory/**/provenance.yaml` — committed, metadata-only, already
  secret/PII-scanned by `memory-check.sh`; and `git log` over `memory/` for the
  changes feed.
- **Imports:** `quantsmith.pipelines.workflow_memory` (Record, load_records,
  query, validate, rank_key, freshness constants) — the `0048` runtime.
- **Consumed by:** a human operator (browser) and, later, an LLM engine
  registered behind the query contract.
- **Access:** records inherit `access_level`; the console *displays* it and never
  widens it. It does not enforce a per-viewer barrier — v1 is a trusted-reader
  tool (see Non-Goals); enforcing viewer level is a later spec, and the console
  makes access level visible so that gap is obvious rather than hidden.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A read console drifts into a write tool by accretion, and an unaudited edit path mutates institutional memory. | High — silent corruption of the record of record. | Read-only is a requirement (NFR-003) with a test that a bogus mutating request 404s (AC-014); the approval *action* is explicitly a later spec, and the UI says actions are advisory. |
| RISK-002 | The NL query layer answers confidently from nothing — the exact failure `instructions/knowledge_base.md` forbids. | High — a fabricated answer about what the firm "knows". | Grounding is an NFR (NFR-006) and an AC (AC-011): zero overlap returns an empty citation list and an explicit "nothing matched", never an invented id. The contract carries citations, not just prose. |
| RISK-003 | Surfacing a restricted record in a shared preview leaks it. | High — an access-level breach via the convenience of a static snapshot. | Access level is shown on every record (REQ-013); the static build is generated from whatever tree the operator points at, and the docs state that a snapshot inherits the source's access level and must not be shared more widely than the source. Enforcement-by-viewer is named as a deferred gap, not pretended. |
| RISK-004 | Bringing a Node/Vite toolchain into a "Markdown-and-shell scaffold" bloats the repo and breaks the copy-in model. | Medium — the SDK stops being cheap to adopt. | The front end is confined to `web/`; the *runtime* is stdlib-only (NFR-001) and the built single file is self-contained (REQ-012). An adopter who never opens `web/` pays nothing; the server runs without Node. |
| RISK-005 | The graph is unreadable at scale — every record wired to every dataset becomes a hairball. | Medium — a visualisation that obscures rather than reveals. | v1's store is small; the layout is deterministic and filterable by workflow/type, and node kinds are visually distinct. Large-store layout (clustering, level-of-detail) is a named follow-up, not a v1 promise. |
| RISK-006 | The changes feed shells out to `git` and hangs or errors in an odd checkout. | Low-Medium — a blank or broken page. | The feed degrades to empty on any git failure (AC-007, NFR-005); the subprocess is bounded and never blocks on input. |

## Assumptions & Open Questions

- Assumption: the store is small enough (tens to low hundreds of records) that
  the whole view-model fits in memory and in one HTTP response. Pagination is a
  follow-up if that stops being true.
- Assumption: the operator running the console may already read the whole
  `memory/` tree on disk; the console adds no new read authority.
- Open question: should freshness be the only "overdue" signal, or should
  predictive records decay faster than mechanical ones? Starting with the single
  `freshness_days` policy `0048`/the manifest already define; a per-type policy
  is a change to the manifest, not the console.
- Open question: the query contract returns record-id citations; should it also
  return spans/offsets within a statement? Deferred — ids are enough to ground
  and to render, and spans matter mainly once a real LLM composes prose.
- Open question: where an LLM engine's key/config lives when one is registered.
  Out of scope here by design; the contract takes records already filtered by
  the caller, so the engine never widens access.

## Delivery surfaces

The view-model and query API defined here are consumed by two independent front
ends, both read-only and both honouring the grounding contract (NFR-006):

1. **`web/`** — the reference SPA (Vite + React + hand-drawn charts, no runtime
   third-party libraries), served by the standard-library API server in
   `src/quantsmith/knowledge_console/server.py`, plus a self-contained snapshot
   (REQ-012). This is the surface REQ-007–REQ-013 and every AC are written
   against, and it is what keeps the SDK stdlib-only.

2. **`apps/knowledge-console/`** — a Bloomberg-terminal-style application on a
   heavier stack (React Router, Tailwind, Zustand, `lucide-react`, a custom Node
   HTTP server with file-system API routing). It is a **separate application,
   not part of the SDK runtime**: it adds nothing to `pyproject.toml`, and its
   Node server does not re-implement the model — it shells out to this package's
   Python CLI (`python -m quantsmith.knowledge_console print|query`), so both
   surfaces read the *same* single source of truth and cannot drift. The heavy
   stack lives entirely under `apps/` and is invisible to an adopter who never
   opens that directory; QuantSmith stays a Markdown-and-shell scaffold with a
   stdlib Python package. NFR-001/NFR-002 continue to bind the SDK; they were
   never claims about a downstream application.

## Exceptions

None. The console adds a read surface and a runtime over standards that already
exist (`0002`, `0048`); it introduces no deviation from
`instructions/engineering_principles.md`. The Node/Vite tooling under `web/` is
build-time only and is quarantined from the SDK's runtime dependencies by
NFR-001/NFR-002; the heavier `apps/knowledge-console/` terminal is a separate
downstream application (see Delivery surfaces) that consumes this package's CLI
rather than adding to it — a deliberate boundary, not an exception to the
constitution.
