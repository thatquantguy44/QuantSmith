# SFMeridian — Handoff (pick up here)

- **Spec family:** `0113` (foundation) and children `0114`–`0121`
- **Last updated:** 2026-10-23
- **Owner / approver:** Joshua Lutkemuller, CFA
- **Branch:** `codex/0116-sfmeridian-governed-sql-composition` (local draft;
  the preceding SFMeridian branch merged to `main` in PR #125)

This is the single entry point for the next agent working on the SFMeridian
plugin.

## Start here (in order)

**The `0116` spec was approved on 2026-10-23. Implementation is in progress;
T-001 through T-007 are built: the synthetic execution fixture, `sql.verify`
with exact-context tokens and adversarial checks, and four-dialect policy with
timeout, normalized cost guard, configurable token TTL, and the token-only
query execution seam with redaction, provenance, and replay, plus retrieval-
first SQL composition, the governed metric-source `Reader`, and governed-first
`ask` routing with a bounded shadow tail. Next is T-008: shared tool contracts
and runtime write-back refusal.**

0. **Baseline verified (2026-10-23)**: SFMeridian tests 67 passed, 1 skipped;
   the steward completed with 4/5 metrics bound and six amendments staged.
   The full gate has unrelated pre-existing venture catalog/index/count
   findings on `main`; the `0116` targeted spec gate has no findings.
1. **Continue the approved build in this order** (each step depends on the one
   before):
   1. ~~a synthetic SQLite fixture database matching
      `fixtures/catalog/fixture_db.catalog.json`~~ (T-001 done);
   2. ~~`sql.verify` and its adversarial suite~~ (T-002 done);
   3. ~~dialect policies, timeout/cost guard, and token TTL~~ (T-003 done);
   4. ~~`sql.execute` (the read-only seam, runs only verified SQL)~~ (T-004 done);
   5. ~~`sql.compose` (`reuse` → `adapt` → `generate`)~~ (T-005 done);
   6. ~~the `0080` `Reader` over `available` metric sources~~ (T-006 done);
   7. ~~governed-first routing (`ask`) through `0080` `answer()`~~ (T-007 done);
   8. **the shared tools and write-back runtime refusal (T-008 next);**
   9. agents `sql_composer` (C-03) and `sfmeridian_orchestrator` (C-04);
   10. docs, counts, registry, skills export, gates, full suite, commit, push,
      and update this file.
2. **Done when** `roadmap.md` Phase 3's exit criteria hold (`0113` A-009–A-011,
   A-021, A-027, A-028, A-030 pass; the adversarial suite rejects every case;
   `ask` answers lookup and aggregation questions on the synthetic database with
   citations), and §1 of this file says `0116` is built.

## 1. Where things stand

| Spec | What | Status | Tests |
| --- | --- | --- | --- |
| [`0113`](spec.md) | Foundation: requirements, tool contract, roster C-01…C-10, handoff map, workflows W1–W13, tooling catalog | Approved | (via children) |
| [`0114`](../0114-sfmeridian-query-repository-indexer/spec.md) | Config, query-repository indexer, search, feedback inbox, tool registry, agent loop harness; agent `query_librarian` (C-01) | **Built**, Approved | `tests/test_sfmeridian_indexer.py` (17 ACs) |
| [`0115`](../0115-sfmeridian-schema-catalog-mapping-access/spec.md) | Catalog snapshots, drift exclusion, governed semantic mapping, metric-source availability, pack amendments, access controls; agent `semantic_mapping_steward` (C-02) | **Built**, Approved | `tests/test_sfmeridian_mapping.py` (17 ACs) |
| [`0121`](../0121-sfmeridian-adaptive-dataset-research/spec.md) | Adaptive dataset research (Dataset Intake Investigator POC); agent `lending_data_researcher` (C-10) | **Built**, Approved; AC-016 (live connectors) open | `tests/test_sfmeridian_research.py` (24 ACs, 1 skipped) |
| [`0116`](../0116-sfmeridian-governed-sql-composition/spec.md) | Governed tier, grounded SQL composition, verification & execution; agents `sql_composer` (C-03), `sfmeridian_orchestrator` (C-04) | **Approved — implementation in progress; T-001–T-007 built** | `tests/test_sfmeridian_sql.py` (AC-001–AC-010) |
| `0117`–`0120` | Grounding & evaluation gate; packaging & surfaces; analytics agents; reporting checks | Reserved | — |

Last verified state (2026-10-22, commit `a793d48`): full suite **1587 passed,
1 skipped**; `QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh` exit 0; ruff clean on
`plugins/sfmeridian/src` and the three SFMeridian test modules.

## 2. Where the code is

```text
plugins/sfmeridian/                    # separate distributable "sfmeridian" 0.1.0, stdlib only, Python 3.11+
  README.md                            # user-facing overview and quick start
  src/sfmeridian/
    config.py, yamlsubset.py           # 0114: fail-closed config, strict YAML subset
    repos.py, frontmatter.py, sqlstructure.py, index.py, feedback.py   # 0114: indexing, search, inbox
    tools.py                           # shared tool registry (effects: read/index/propose/execute_read/report/human_only)
    agent.py                           # loop harness: grants, budgets, verified finish, escalation, ModelPolicy
    governance.py                      # coverage/handoffs/tooling/manifest validators, CONTRACT_TOOLS, import scan
    librarian.py                       # C-01 query_librarian
    catalog.py, mapping.py, access.py  # 0115
    semantic_tools.py, steward.py      # 0115 tools; C-02 semantic_mapping_steward
    governed/packs.py, reader.py, ask.py # the ONLY package that may import quantsmith (0081/0008/0080 bridge)
    research/                          # 0121 research tools, policy (C-10 lending_data_researcher), bundle
    data/coverage.json                 # roster C-01…C-10 (C-01, C-02, C-10 built)
    data/handoffs.json                 # 37 existing agents SFMeridian hands work to
    data/tooling_catalog.json          # screened third-party catalog (admission reviews pending)
    data/pack_amendments.json          # 0115 proposals for the 0081 pack (status: proposed)
    data/agents/*.json                 # manifests of built loop agents
  fixtures/                            # SYNTHETIC (disclosed in fixtures/README.md)
agents/securities_financing/sfmeridian/   # four-file contracts for built agents
templates/sfmeridian/sfmeridian.yml       # adopter config template (validates with placeholders)
```

## 3. Pick up here: build `0116`

Owner decision (2026-10-22): build `0115` then `0116`. `0115` is done; `0116` is
next. Scope comes from `roadmap.md` (row `0116`) and `0113` tasks T-014, T-015,
T-016, T-031, T-032 (Reader half), T-034 (refusal half), and T-017 (C-04).

**First steps**

1. Create `specs/0116-sfmeridian-governed-sql-composition/` from
   `templates/spec/` (spec, plan, tasks). Write parent references as `0113`
   R-nnn / A-nnn / N-nnn / K-nnn so the spec gate does not read them as local IDs.
   Parent ACs to realize: `0113` A-009, A-010, A-011, A-021, A-027, A-028, A-030.
2. Get the owner's approval of the `0116` spec before building (each child so far
   was approved before code).

**What to build, and what it plugs into**

| Piece | Build on | Notes |
| --- | --- | --- |
| `sql.verify` — deterministic static verifier with verification tokens | `sqlstructure.extract` (statement kind/count, tables, joins, params, write keywords); `catalog.Resolver` for identifier resolution; `index_dir/join_graph.json` for observed join keys | Fail closed: one read-only statement, every identifier resolves in the latest snapshot, bound parameters only, PIT predicate for as-of questions (`grounding.require_pit_predicate_for_as_of`), row limit, timeout, optional `EXPLAIN` cost guard (`databases[].explain_cost_limit`). Adversarial suite is part of the DoD. |
| `sql.execute` — read-only execution seam | `quantsmith.quant.agentic_quant.sql_data.SQLDataSource` (wrap; expose `query` only, never `execute`/`transaction`) or an injected adopter driver (same injection shape as `catalog.connect` / `research.sources.Executor`) | Only executes SQL carrying a valid verification token. Provenance: query hash, composition path, profile, catalog `snapshot_id`, as-of, parameters (sensitive redacted), row count, `0070` run ID. Apply `access.withheld_columns`/`redact_rows` to results. |
| `0080` `Reader` over metric sources | `mapping.validate_mapping(...)["metric_sources"]` (only `available` sources); `governed_tier.metric_sources` column maps; `quantsmith.nl_analytics.execute.Reader = Callable[[QueryPlan], Sequence[Fact]]` | Run each source query through `sql.verify` → `sql.execute` with the plan's as-of and filters as parameters; emit `0008` `Fact` rows. Unavailable metrics are reported, never served (`0113` A-028). Lives in `governed/`. |
| Governed-first routing (`ask`) | `quantsmith.nl_analytics.respond.answer(question, AnswerContext(layer, reader, as_of, interpret_context, viewer_clearance, ...))`; `governed.packs.compile_layer(bound_bindings)` gives the `SemanticLayer` | Route: answer → return (tier `governed`); clarification among governed candidates → return, no fall-through; no governed metric → fall through to `reuse`/`adapt`/`generate`. Record the tier. Pass `access.caller(...).clearance`. Lives in `governed/`. |
| `sql.compose` — retrieval-first composer | `queries.search` (reviewed first), `queries.get`, `catalog.describe`, `glossary.lookup`; model calls only through an injected completer (as `agent.ModelPolicy`) | `reuse` (bind parameters of a reviewed exemplar) → `adapt` → `generate` (constrained to catalog + bound concepts). Record path and source exemplars. Generated SQL never becomes an exemplar without human promotion. |
| Write-back refusal | `config.py` already rejects lending/trading/books-and-records targets | `0116` adds the runtime refusal with a reason (`0113` A-030). |
| Agents `sql_composer` (C-03), `sfmeridian_orchestrator` (C-04) | `data/coverage.json` rows C-03/C-04 already list their planned tools and verifiers | Same pattern as `steward.py`: deterministic policy, verifiers, manifest in `data/agents/`, four contract files, catalog rows, registry + skills export. Add the new tool names to `governance.CONTRACT_TOOLS` (they are already listed under "0116-0118"). |

**Inputs 0115 already provides to 0116**

- Fixture mapping config `plugins/sfmeridian/fixtures/sfmeridian.mapping.yml`:
  9 valid bindings; metric sources `lending_revenue` and `on_loan_value` are
  `available`; `client_debit_balance` is deliberately unbound.
- Catalogs v1/v2 under `fixtures/catalog/` (v2 drops `sec_lending_book.status`,
  which makes the `on_loan_value` source `unavailable` — use it for A-028's drift case).
- The fixture query repository references tables (`sec_lending_book`,
  `lendable_inventory`, …) that the `0121` research SQLite database does **not**
  have. To execute metric source queries end to end, `0116` needs a synthetic
  SQLite database matching `fixtures/catalog/fixture_db.catalog.json` (build it
  deterministically, like `fixtures/research/fixture_db.py`, and disclose it).

## 4. Open decisions (owner)

| Decision | Blocks | Default until decided |
| --- | --- | --- |
| Review of the `0081` `securities_financing_prime` pack and the six staged amendments (reviewer: Joshua Lutkemuller, CFA) | Nothing (caveat applies) | Pack stays `draft`; governed answers carry the unreviewed-pack caveat; write-back stays off |
| Tooling admission reviews (`0113` T-037), including database drivers | Any optional extra shipping in `0116` | Drivers injected by the host; no extras |
| SQL Server (`mssql`) enablement | `mssql` profiles | `E_CONFIG_UNSUPPORTED` |
| First-desk collateral margin and materiality thresholds | `0119` analytics | Research context thresholds supplied per run |
| `0121` AC-016 live connectors | Live research runs | Skipped test; SQLite fixture only |

Recorded tightening (no decision needed unless the owner disagrees): utilization
by counterparty is refused (`0115` Exceptions).

## 5. Conventions and gotchas (learned building 0114/0115/0121)

- **Commits:** Conventional Commits; owner's git identity; **no** `Co-Authored-By`
  or session trailers (the `agent-attribution` gate rejects them). No attribution
  footer on GitHub posts.
- **Spec gate:** every `REQ-*`/`NFR-*` must appear in `plan.md` or `tasks.md` by
  its exact ID — ranges like `NFR-001–NFR-005` are not expanded.
- **After any agent change:** `python3 scripts/build_agent_registry.py` and
  `PYTHONPATH=src python3 -m quantsmith.skills_export build`; commit both
  (SFMeridian skills are registry-only, not materialized). Update the coverage row,
  `agents/README.md`, `agents/securities_financing/README.md`, and
  `agents/securities_financing/sfmeridian/README.md`.
- **Doc counts:** a new agent or spec bumps counts in `README.md` (badges, runtime
  table), `docs/handoff.md`, and `docs/sdk_plan.md`; `doc-counts` fails otherwise.
  Also add rows to `specs/README.md` and the root `README.md` runtime table.
- **Imports:** the plugin core is stdlib only; `governance.check_imports()` fails on
  anything else outside `governed/`.
- **Ruff:** keep `ruff check plugins/sfmeridian/src tests/test_sfmeridian_*.py`
  clean (`ISC004` needs parenthesized implicit concatenations).
- **Python:** the plugin requires 3.11+; CI runs `uv run --frozen python -m pytest tests/ -q`.
  The full suite takes about 6 minutes.
- **Secret scan:** deliberate fake credentials in tests need the
  `# qf:allow-secret (deliberate fake)` marker.
- **Fixtures:** synthetic only; every new fixture gets a row in
  `plugins/sfmeridian/fixtures/README.md`.
- **Tests:** copy `plugins/sfmeridian/fixtures` into `tmp_path`; write changed
  configs next to the source file so relative paths still resolve.

## 6. Verify before you start

```sh
git checkout claude/seclending-intelligence-plugin && git pull
uv run --frozen python -m pytest tests/test_sfmeridian_indexer.py tests/test_sfmeridian_mapping.py tests/test_sfmeridian_research.py -q
QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh
cd plugins/sfmeridian && PYTHONPATH=src:../../src python -m sfmeridian --config fixtures/sfmeridian.mapping.yml --today 2026-10-22 agent run semantic_mapping_steward
```

Expected: 57 passed, 1 skipped; gates exit 0; the steward run is `completed` with
4/5 governed metrics bound and 6 amendments staged (it writes under
`fixtures/.sfmeridian/`, which is gitignored — delete it afterwards).
