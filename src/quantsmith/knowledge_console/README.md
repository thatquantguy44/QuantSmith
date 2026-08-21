# Knowledge Console (spec `0057`)

A **read-only** analytics web app over the `memory/` knowledge store. It turns the
machine-readable store (`0002` schema, `0048` runtime) into a legible surface:
analytics, trends, an interactive knowledge graph, a recent-changes feed, a
needed-review queue, and a **pluggable natural-language query** seam.

It never writes to `memory/` — the approval *action* (write-back) is a later spec
(`0049`). This is its read surface.

## Layout

| Module | Responsibility |
| --- | --- |
| `model.py` | `load_store()` walks a `memory/` tree per its manifest into `0048` records tagged with workflow/source; `build_model()` derives the deterministic JSON view-model (counts, trends, graph, changes, review queue); `git_changes()` reads the git history feed. |
| `query.py` | The NL-query seam: a `QueryEngine` protocol, a grounded `KeywordQueryEngine` default, and `resolve_engine()`/`register_engine()` so a real LLM engine can take over later behind the same contract. |
| `server.py` | Standard-library HTTP server: `GET /api/model`, `GET /api/health`, `POST /api/query`, plus static serving of the built front end (traversal-guarded, loopback-bound, read-only). |
| `__main__.py` | CLI: `serve`, `snapshot`, `print`. |
| `../../../web/` | Vite + React + TypeScript front end (six views). Build-time tooling only — it is **not** an SDK runtime dependency. |

The backend is **standard library only** (spec NFR-001); the front end pulls in
no runtime third-party libraries and no external hosts (spec NFR-002).

## Run it (live)

```sh
# 1. build the front end once
npm --prefix web install
npm --prefix web run build

# 2. serve the API + UI (loopback, read-only) over the real memory/ store
python -m quantsmith.knowledge_console serve --root memory --static web/dist --port 8765
# open http://127.0.0.1:8765
```

During front-end development, `npm --prefix web run dev` runs Vite with hot reload;
point it at a running `serve` for the API.

## Share a snapshot (no server)

```sh
python web/build-snapshot.py            # builds a self-contained single HTML file
# -> web/dist-single/console.html : all JS/CSS inlined, the current view-model
#    embedded as window.__KB_MODEL__, zero network requests. Open it directly.
```

The front end reads `window.__KB_MODEL__` when present and otherwise fetches
`/api/model`; the Ask view runs the same grounded keyword search in-browser when
there is no server. A snapshot inherits the access level of the store it was built
from — do not share it more widely than the source `memory/` tree.

## Plugging in an LLM later

Implement the `QueryEngine` protocol (a `name` and
`answer(question, records, k) -> Answer`) and call `register_engine(engine)` at
startup. `/api/query` and the whole UI are unchanged. The engine receives records
already loaded by the caller, so it cannot widen access, and it must ground every
answer in real record ids — the same contract the keyword engine honours.
