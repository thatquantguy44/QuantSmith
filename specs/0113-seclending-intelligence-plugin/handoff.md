# SFMeridian — Handoff (pick up here)

- **Spec family:** `0113` (foundation) and children `0114`–`0121`
- **Last updated:** 2026-10-23
- **Owner / approver:** Joshua Lutkemuller, CFA
- **Branch:** `codex/0116-sfmeridian-governed-sql-composition` (local draft;
  the preceding SFMeridian branch merged to `main` in PR #125)

This is the single entry point for the next agent working on the SFMeridian
plugin.

## Start here (in order)

**The `0116` spec was approved and built on 2026-10-23; T-001 through T-012
are complete: the synthetic execution fixture, `sql.verify`
with exact-context tokens and adversarial checks, and four-dialect policy with
timeout, normalized cost guard, configurable token TTL, and the token-only
query execution seam with redaction, provenance, and replay, plus retrieval-
first SQL composition, the governed metric-source `Reader`, and governed-first
`ask` routing with a bounded shadow tail, the shared SQL/ask tool contracts,
and runtime write-back refusal, loop agents C-03 and C-04, and bounded W7–W12
specialist handoff payloads, deterministic workload assurance and boundary
hardening, CLI/configuration integration, synchronized documentation, and
release verification. Next is `0117`: grounded answering and the hallucination
evaluation gate.**

0. **Baseline verified (2026-10-23)**: SFMeridian tests 73 passed, 2 skipped;
   full suite 1572 passed, 18 skipped. The steward completed with 4/5 metrics
   bound and six amendments staged. Clean-clone enforced gates have no findings;
   owner-local ignored venture files remain outside the tracked baseline.
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
   8. ~~the shared tools and write-back runtime refusal~~ (T-008 done);
   9. ~~agents `sql_composer` (C-03) and `sfmeridian_orchestrator` (C-04)~~ (T-009 done);
   10. ~~bounded W7–W12 specialist handoff payloads~~ (T-010 done);
   11. ~~repeatability, rejection/fabrication counters, overhead, import and
       redaction hardening~~ (T-011 done);
   12. ~~docs, counts, registry, skills export, gates, full suite, commit, push,
       and final handoff~~ (T-012 done).
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
| [`0116`](../0116-sfmeridian-governed-sql-composition/spec.md) | Governed tier, grounded SQL composition, verification & execution; agents `sql_composer` (C-03), `sfmeridian_orchestrator` (C-04) | **Built**, Approved | `tests/test_sfmeridian_sql.py` (17 passed; AC-001–AC-018) |
| `0117`–`0120` | Grounding & evaluation gate; packaging & surfaces; analytics agents; reporting checks | Reserved | — |

Last verified state (2026-10-23): full suite **1572 passed, 18 skipped**;
SFMeridian suite **73 passed, 2 skipped**; clean-clone enforced gates pass;
ruff is clean on the `0116` runtime and SFMeridian tests.

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
    governed/                        # the ONLY package that may import quantsmith (packs, Reader, ask, tools)
    handoff.py                       # inert, validated W7–W12 evidence payloads; never invokes receivers
    assurance.py                     # deterministic safety, rejection, fabrication, overhead/cost counters
    research/                          # 0121 research tools, policy (C-10 lending_data_researcher), bundle
    data/coverage.json                 # roster C-01…C-10 (C-01–C-04, C-10 built)
    data/handoffs.json                 # 37 existing agents SFMeridian hands work to
    data/tooling_catalog.json          # screened third-party catalog (admission reviews pending)
    data/pack_amendments.json          # 0115 proposals for the 0081 pack (status: proposed)
    data/agents/*.json                 # manifests of built loop agents
  fixtures/                            # SYNTHETIC (disclosed in fixtures/README.md)
agents/securities_financing/sfmeridian/   # four-file contracts for built agents
templates/sfmeridian/sfmeridian.yml       # adopter config template (validates with placeholders)
```

## 3. Pick up here: specify and build `0117`

`0115` and `0116` are built. The next dependency-ordered phase is `0117`,
grounded answering and hallucination evaluation. Scope comes from `roadmap.md`
(row `0117`) and parent tasks T-018, T-019, T-030 (grounding half), and T-035.

**First steps**

1. Create `specs/0117-sfmeridian-grounded-answering-evaluation/` from
   `templates/spec/` (spec, plan, tasks). Write parent references as `0113`
   R-nnn / A-nnn / N-nnn / K-nnn so the spec gate does not read them as local IDs.
   Parent ACs to realize: `0113` A-012, A-013, A-016, A-022, and the grounding
   half of A-026; preserve the tier metrics required by T-035.
2. Get the owner's approval of the `0117` spec before building (each child so far
   was approved before code).

**What to build, and what it plugs into**

| Piece | Build on | Notes |
| --- | --- | --- |
| `answer.ground` | `0116` execution provenance, cited rows, `0070` envelopes; `0063` term/viewpoint conventions; `0008` metric definitions | Deterministically extract numeric and factual claims, resolve each citation, recompute supported values within configured tolerance, reject undefined terms or mixed viewpoints, and emit only cite/correct/remove/abstain outcomes. Never add a new fact. |
| Grounded `ask` finish | `sfmeridian_orchestrator`, governed `0080` answers, and shadow-tail results | Put every answer through `answer.ground`; preserve clarification and unavailable outcomes; strip unsupported claims or abstain. Reject action-phrased specialist output where A-026 requires a decision-support boundary. |
| Versioned golden-question fixture | `0116` deterministic SQLite fixture, query repository, catalog, and known results | Add answerable, unanswerable, adversarial, viewpoint, tier-routing, and clearance cases. Keep every record synthetic and `0025`-disclosed; never encode a real schema, name, position, or query. |
| `eval.run` release gate | Golden cases plus deterministic runs over three fixed seeds | Report identifier fabrication, execution accuracy, result match, unsupported claims, viewpoint errors, abstention precision/recall, exemplar reuse, governed-tier share, tier agreement, and wrong-tier rate. Block unless NFR-002 passes: fabrication 0, unsupported claims ≤1%, viewpoint errors 0, execution accuracy ≥90%, and unanswerable abstention recall ≥95%; require tier agreement 100% and wrong-tier 0 on governed cases. |
| `answer_grounding_reviewer` (C-05) | Existing loop harness, shared tool registry, `coverage.json`, and C-04 handoff | Build the manifest, deterministic policy/verifiers, four-file agent contract, catalog/registry/skills updates, and golden runs. Its never-boundary is strict: it may cite, correct to cited evidence, remove, or abstain—never invent. |
| Assurance and release evidence | `assurance.py`, access/redaction controls, stage gates | Prove repeatability, threshold failure blocking, no secret or restricted-value leakage, and optional connector skips. Coordinate with reserved `0103` methods but do not wait for that spec. |

**Inputs `0116` already provides to `0117`**

- Deterministic synthetic execution data and expected results; four-dialect
  policies; verified, token-only execution; and replayable provenance.
- Governed-first `ask`, the metric-source `Reader`, and typed clarification /
  unavailable outcomes, plus recorded tier and citations.
- Loop agents C-03/C-04, shared tool contracts, bounded repair/escalation,
  specialist handoffs, and deterministic safety/overhead assurance.
- The unreviewed `0081` pack caveat remains required until the named review is
  completed; write-back remains refused.

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
git checkout codex/0116-sfmeridian-governed-sql-composition && git pull
uv run --frozen python -m pytest tests/test_sfmeridian_*.py -q
QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh
cd plugins/sfmeridian && PYTHONPATH=src:../../src python -m sfmeridian --config fixtures/sfmeridian.mapping.yml --today 2026-10-22 agent run semantic_mapping_steward
```

Expected: 73 passed, 2 skipped; gates exit 0; the steward run is `completed` with
4/5 governed metrics bound and 6 amendments staged (it writes under
`fixtures/.sfmeridian/`, which is gitignored — delete it afterwards).
