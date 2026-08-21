# QuantSmith Knowledge Terminal

A Bloomberg-terminal-style front end for the QuantSmith **memory / knowledge
store** (spec `0057`). It is a standalone application that lives outside the SDK
runtime: QuantSmith itself stays a Markdown-and-shell scaffold with a
standard-library Python package, and this app depends on that package without
adding anything to it.

## Stack

- React 18.3 SPA (no SSR), Vite 5.4, TypeScript 5.6 (strict)
- React Router 6 (client-side; routes under `src/app/routes/`)
- Tailwind CSS 3.4 with a custom `term.*` design system (`tailwind.config.ts`)
- Zustand 5 for state, `lucide-react` icons, `clsx`
- A custom Node HTTP server (`src/server/index.ts`) with file-system API routing
  under `src/app/api/**`; a Vite dev plugin (`vite-plugins/dev-api.ts`) serves
  `/api/*` in dev so dev and prod share one request path.

## Where the data comes from

The API does **not** re-parse `memory/` in TypeScript. It shells out to the
`0057` Python view-model — the single, tested source of truth for records,
counts, trends, the knowledge graph, the git changes feed, and the review queue:

```
GET  /api/model  ->  python -m quantsmith.knowledge_console print  --root memory
POST /api/query  ->  python -m quantsmith.knowledge_console query  --root memory --question ...
GET  /api/health
```

The repo root (and thus `memory/`) is found by walking up for
`memory/manifest.yaml`; override with `QF_REPO_ROOT` / `QF_MEMORY_ROOT`, and the
Python interpreter with `QF_PYTHON`. Python must be importable — run from a
checkout of this repo (no install needed; `PYTHONPATH` is set to `src/`).

## Run it

```sh
npm install
npm run dev        # Vite dev server; /api/* handled by the dev plugin

# production
npm run build      # -> dist/ (client) + dist-server/ (Node server)
npm start          # serves both on http://127.0.0.1:8787 (HOST/PORT override)
```

## Views

Overview (analytics) · Trends · Knowledge Graph · Recent Changes · Needed Review
· Ask. The **Ask** panel uses the same pluggable engine as the SDK: a grounded
keyword engine today, a real Claude engine registered behind the identical
`QueryEngine` contract later — no change to this app or its API.

Read-only: nothing here writes to `memory/`. The approval *action* (write-back)
is the deferred `0049` write path.
