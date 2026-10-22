# Plan: SFMeridian — Adaptive Securities-Finance Dataset Research

- **Spec:** 0121-sfmeridian-adaptive-dataset-research (`spec.md`)
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-22

## Approach

Implement the POC spec inside SFMeridian rather than beside it. The POC's
deterministic intake checks are ported unchanged into the plugin as the
`intake` family; its adaptive design (coverage ledger, tool catalog,
pushdown, budgets, recommendations, bundle) is built on what `0114` already
provides: the shared tool registry (the catalog becomes `research.*` tools),
the loop harness (the planner/executor loop, budgets, stop reasons), read-only
database profiles, and the strict configuration reader. Securities finance
enters through the research context (`dataset_kind`, viewpoint, thresholds)
and a declarative rule pack keyed by dataset kind.

The safety property is structural: the agent can only run SQL rendered from
plugin-owned templates, each of which passes the static checks `0116`'s
verifier will enforce, with values bound and identifiers drawn from the
dataset's declared, non-excluded columns. Files are loaded into an in-memory
SQLite table so one template path serves files and databases.

## Architecture & Components

```text
plugins/sfmeridian/src/sfmeridian/research/
  context.py     REQ-002  research context validation (no invented context)
  intake.py      REQ-001  POC file intake (CSV/TSV/JSON), loader generator
  templates.py   REQ-004  reviewed SELECT templates, dialect rendering, static check
  sources.py     REQ-003/005/007/015  dataset loading, read-only executor, budgets, provenance
  evidence.py    REQ-009  evidence registry, coverage ledger, findings, session
  rules.py       REQ-008  securities-finance rule pack (dataset_kind → rules)
  analysis.py    REQ-006/007/014  the deterministic tool implementations
  charts.py      REQ-012  Vega-Lite specs + validation
  recommend.py   REQ-011  §9 recommendation contract
  bundle.py      REQ-012  run bundle and manifest
  tools.py       REQ-006  research.* registration (effects execute_read / read / report)
  policy.py      REQ-010  ResearchPolicy, verifiers, run_research
  cli.py         REQ-012  `sfmeridian research run`, bundle `rerun.py`
data/agents/lending_data_researcher.json   REQ-017 manifest
fixtures/research/  fixture_db.py, sfmeridian.research.yml, contexts/, POC sample
```

Loop (on the `0114` harness):

```text
research.start ─▶ intake ─▶ schema ─▶ summaries ─▶ grain ─┬─▶ wider-grain probe (if repeats + probe columns)
                                                         ▼
          time ─▶ missingness by date & segment (per column with nulls) ─▶ domain rules ─┬─▶ rule by segment
                                                                                         ▼
          numeric ─▶ categories ─▶ relationships ─▶ segments ─▶ target ─▶ availability ─▶ reference
          ─▶ charts ─▶ recommendations ─▶ finish (probe again, close ledger, write bundle)
budget exhausted at any point ─▶ finish(stop_reason=budget_exhausted) ─▶ run status budget_exhausted
```

## Interfaces & Data Contracts

- **Config** — `datasets[]` (`id`, `source`, `profile`, `object`, `object_type`,
  `path`, `columns`, `order_by`, `filters`, `version`, `dataset_kind`,
  `contract`, `max_rows`) and `research.output_dir`.
- **Connections** — `ctx.clients["connections"][profile] = {"connect", "paramstyle"}`;
  SQLite `secret_ref: sqlite-file:<path>` opens read-only (`mode=ro`).
- **Templates (v1)** — `count_rows`, `column_summary`, `group_counts`,
  `nulls_by_group`, `key_repeats`, `key_missing`, `rule_counts`,
  `rule_counts_by_group`, `segment_numeric`, `consistency`, `extract`; limited
  templates fetch one extra row to detect truncation.
- **Evidence** — `{evidence_id, tool, summary, value, scope, method,
  denominator, exclusions, warnings, queries[]}`; IDs are SHA-256 of the
  record without timings.
- **Coverage** — one entry per family: `completed | blocked | skipped |
  budget_exhausted` with reason and evidence IDs.
- **Recommendation** — the POC §9 fields plus `finding_id` and `executes: false`.
- **Effects** — `execute_read` (rendered read-only SQL), `report` (local bundle).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Only rendered templates run; static check before execution; context-only thresholds; scope labels on every result. |
| P5 Reversibility | yes | Read-only; bundles are local files; nothing is repaired. |
| P6 Observability | yes | Evidence registry, coverage ledger, query log, manifest, trace. |
| P9 Security & data | yes | Injected connections, no credentials in config or bundle, sensitive values withheld, excluded columns never queried, untrusted text marked. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `intake.py` | T-001 |
| REQ-002 | `context.py` | T-002 |
| REQ-003 | config `datasets[]`, `sources.load_dataset` | T-003 |
| REQ-004 | `templates.py`, `sources.Executor` | T-004 |
| REQ-005 | executor provenance | T-005 |
| REQ-006 | `analysis.py`, `tools.py` | T-006 |
| REQ-007 | pushdown templates | T-006 |
| REQ-008 | `rules.py` | T-007 |
| REQ-009 | `evidence.py` | T-008 |
| REQ-010 | `policy.py`, harness changes | T-009 |
| REQ-011 | `recommend.py` | T-010 |
| REQ-012 | `bundle.py`, `charts.py`, `cli.py` | T-011 |
| REQ-013 | sensitive/excluded handling, untrusted text | T-012 |
| REQ-014 | `inspect_availability` | T-013 |
| REQ-015 | consistency probes, view limitation | T-014 |
| REQ-016 | live smoke test (skipped unless injected) | T-015 |
| REQ-017 | agent files, catalogs, W13 | T-016 |
| NFR-001 | import scan | T-017 |
| NFR-002 | timing-free artifacts | T-011 |
| NFR-003 | static check, read-only connections | T-004 |
| NFR-004 | evidence fields | T-008 |
| NFR-005 | gates | T-018 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Where the POC lands | Inside SFMeridian on its registry and harness | Separate intake tool beside the plugin | One loop, one tool contract, one safety model. |
| SQL source | Plugin-owned templates | Model or repository SQL | Execution safety without waiting for `0116`. |
| Files | Load into in-memory SQLite | Separate Python analysis path | One template path; identical semantics. |
| Charts | Vega-Lite JSON | matplotlib PNGs | Stdlib only; host apps render. |
| Availability checks | Extract-based, labelled | SQL timestamp parsing | Offsets parse identically in Python across dialects. |
| POC watcher | Not carried | Port it | `0113` excludes scheduling infrastructure. |

## Validation Strategy

`tests/test_sfmeridian_research.py`: one test per AC (POC names for AC-001…
AC-018) over a deterministic synthetic SQLite fixture with planted issues
and benign extremes; Python recomputation for pushdown correctness; a
subprocess rerun from the bundle; wrapped connections for transient failures
and mid-run mutation; scripted model policies for injection and sensitivity.

## Rollout, Observability & Rollback

Offline and synthetic only. Live connector smoke (AC-016) needs injected
nonproduction pointers. Rollback: delete `research/`, the manifest, the agent
folder, and the catalog rows.

## Open Questions

- Enable SQL Server (templates exist; config gate closed)?
- First desk's collateral margin and materiality thresholds.
