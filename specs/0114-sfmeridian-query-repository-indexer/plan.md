# Plan: SFMeridian — Query Repository Connector & Indexer

- **Spec:** 0114-sfmeridian-query-repository-indexer (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-22

## Approach

Build the first slice of the `sfmeridian` distributable under
`plugins/sfmeridian/` as a standard-library-only package. Configuration and
front-matter share one strict YAML-subset parser so there is exactly one way
text becomes data. Each repository kind is a small fetcher returning a
snapshot (resolved ref plus file bytes); the indexer turns snapshots into
content-addressed exemplars and aggregates the learned structure, writing
sorted JSON so a re-index of unchanged inputs writes nothing. Search is BM25
over exemplar metadata, never over SQL bodies' literals. The feedback inbox
is a directory of JSON files, so a pull request can carry a promotion.

## Architecture & Components

```text
plugins/sfmeridian/
  pyproject.toml                 # distributable "sfmeridian" 0.1.0, no dependencies
  README.md
  src/sfmeridian/
    __init__.py                  # __version__, CONTRACT_VERSION
    __main__.py, cli.py          # REQ-011
    yamlsubset.py                # REQ-002
    config.py                    # REQ-001: schema, defaults, layering, hash, overrides
    globs.py                     # ** globs for include/exclude
    repos.py                     # REQ-003: local / git / object_store snapshots
    frontmatter.py               # REQ-004
    sqlstructure.py              # REQ-005
    index.py                     # REQ-006, REQ-007: exemplars, aggregates, BM25 search
    feedback.py                  # REQ-008
    governance.py                # REQ-009: coverage, handoffs, tooling, manifests, import scan
    tools.py                     # REQ-012: shared tool registry (schemas, effects)
    agent.py                     # REQ-013: loop harness, manifests, ModelPolicy
    librarian.py                 # REQ-014: query_librarian policy + verifiers
    data/agents/query_librarian.json   # manifest
    data/coverage.json, handoffs.json, tooling_catalog.json
  fixtures/
    README.md                    # synthetic-data disclosure (0025)
    sfmeridian.fixture.yml       # synthetic config, no placeholders
    query_repo/**.sql            # ~15 synthetic lender-viewpoint queries
agents/securities_financing/sfmeridian/
  README.md                      # subgroup README
  query_librarian/{README,prompt,instructions,tasks}.md   # REQ-010
tests/test_sfmeridian_indexer.py # every AC; adds plugins/sfmeridian/src to sys.path
```

Tests live in the repo-root `tests/` (deviation from `0113` plan's
`plugins/sfmeridian/tests/`) because CI runs `pytest tests/`; `0118` adds a
packaged test entry point when the distributable is published.

## Interfaces & Data Contracts

- **Config** — `load_config(path=None, env=None) -> Config` (`.data`, `.hash`,
  `.source`); `validate_data(data, allow_placeholders=False) -> [Issue]`;
  `apply_call_overrides(config, overrides) -> dict`; `ConfigError(issues)`.
  New section `index: {dir}` (default `.sfmeridian/index`, gitignored).
  Codes: `E_CONFIG_INVALID`, `E_CONFIG_UNKNOWN_KEY`, `E_CONFIG_MISSING`,
  `E_CONFIG_TYPE`, `E_CONFIG_PLACEHOLDER`, `E_CONFIG_CREDENTIAL`,
  `E_CONFIG_UNSUPPORTED`, `E_CONFIG_WRITEBACK_TARGET`, `E_CONFIG_OVERRIDE_DENIED`.
- **Snapshot** — `RepoSnapshot(repo_id, kind, ref, files=[SourceFile(path,
  sha256, data)])`; refs: Git commit SHA, `local:<sha256>` and
  `object:<sha256>` over sorted (path, content-hash) pairs.
- **Exemplar** (JSONL, sorted by `exemplar_id`) — `exemplar_id`, `query_id`,
  `repo_id`, `ref`, `path`, `line_span`, `sql_sha256`, `normalized_sql_hash`,
  metadata fields, `review_status` (`reviewed`/`draft`/`deprecated`/
  `unreviewed`), `trust_tier`, `provenance` (`repository`/`feedback`),
  `structure`, `findings`.
- **Rejected** (JSONL) — `repo_id`, `ref`, `path`, `code`, `reason`, `line`.
- **Aggregates** — `join_graph.json`, `metric_candidates.json`,
  `filter_patterns.json`, `manifest.json`; every entry lists supporting
  exemplar IDs; literal values appear only as `<literal>`.
- **Search** — `search(index_dir, config, query, limit, profile, tags,
  include_hints) -> [Hit(score, hint, exemplar citation)]`; normalized score
  = BM25 / Σ idf·(k1+1) over query terms, `k1=1.2`, `b=0.75`.
- **Inbox** — `<inbox>/candidates/<id>.json`, `<inbox>/promoted/<id>.json`;
  candidate ID = SHA-256 of the canonical payload (first 16 hex).

## Agent Loop

`run_agent(manifest, policy, registry, ctx, inputs, verifiers)` drives
`decide → ToolCall | Finish | Escalate`. The harness, not the policy, holds
the guarantees: grant check, `human_only` refusal, budgets, verifier gate with
bounded repair, deterministic run ID (SHA-256 over manifest, inputs, policy
name, config hash, injected date), and a trace of decide/observe/verify
events with output hashes. `AgentRun.envelope()` gives the `0070`-shaped
subset. The CLI writes run records with `--save` under `<index.dir>/runs/`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Fail-closed parser and validation; review status decides eligibility; literals redacted by construction. |
| P5 Reversibility | yes | Additive package and files; the index is a rebuildable cache. |
| P6 Observability | yes | Index report counts parsed/reused/rejected per repo; rejections carry reasons and lines. |
| P9 Security & data | yes | No credentials in config; no network in tests; synthetic, disclosed fixtures. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `config.py` | T-002 |
| REQ-002 | `yamlsubset.py` | T-001 |
| REQ-003 | `repos.py`, `globs.py` | T-003 |
| REQ-004 | `frontmatter.py` | T-004 |
| REQ-005 | `sqlstructure.py` | T-005 |
| REQ-006 | `index.py` (build) | T-006 |
| REQ-007 | `index.py` (search) | T-007 |
| REQ-008 | `feedback.py` | T-008 |
| REQ-009 | `governance.py`, `data/*.json` | T-009 |
| REQ-010 | `agents/securities_financing/sfmeridian/query_librarian/` | T-010 |
| REQ-011 | `cli.py` | T-011 |
| REQ-012 | `tools.py` | T-015 |
| REQ-013 | `agent.py` | T-016 |
| REQ-014 | `librarian.py`, manifest | T-017 |
| NFR-001 | import scan | T-009, T-012 |
| NFR-002 | sorted, content-addressed output | T-006, T-012 |
| NFR-003 | local Git fixtures | T-003, T-012 |
| NFR-004 | fixtures + disclosure, credential checks | T-002, T-013 |
| NFR-005 | gates | T-014 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| YAML | Own strict subset | PyYAML dependency | NFR-001; one fail-closed reader for config and front-matter. |
| Git access | `git` CLI into a bare cache | Pure-Python Git library | No dependency; the CLI is universal and honours the adopter's credential helper. |
| Object store | Injected client protocol | Bundle an SDK | Vendor neutrality; no network code in the package. |
| SQL structure | Heuristic tokenizer, learning-only | Full parser now | Dependency-free; mistakes cost a wrong hint, not an unsafe query, because verification is separate. |
| Index format | Sorted JSONL/JSON files | SQLite index | Diffable, reviewable, byte-stable. |

## Validation Strategy

One test module, `tests/test_sfmeridian_indexer.py`, with a test per AC
(names carry the AC IDs), built on the synthetic fixtures and a temporary
local Git repository.

## Rollout, Observability & Rollback

No production surface yet. Rollback is deleting `plugins/sfmeridian/` and the
agent folder. Index health is reported by `python -m sfmeridian status`.

## Open Questions

- None blocking. (The `0081` pack reviewer was named 2026-10-22 and `0115` is built.)
