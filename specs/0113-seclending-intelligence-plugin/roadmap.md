# Roadmap: SFMeridian — Securities Finance Intelligence Plugin

- **Spec:** 0113-seclending-intelligence-plugin (`spec.md`, `plan.md`, `tasks.md`)
- **Last updated:** 2026-10-22

> The ordered child-spec roadmap (REQ-018). Each phase is one or more bounded
> child specs, written and approved one at a time through the normal SDD gates.
> A phase starts only when the previous phase's exit criteria hold. Durations
> are planning estimates for one engineer, not commitments.
>
> **Current state and where to pick up: [`handoff.md`](handoff.md).** Built:
> Phases 0, 1, 2, 2b. Next: Phase 3 (`0116`).

## Reserved Child Specs

| Spec | Title | Scope | Depends on | Coverage rows closed | Tasks |
| --- | --- | --- | --- | --- | --- |
| `0114` | Query repository connector & indexer | Tool registry and agent loop harness (REQ-028/029); config loader and schema; `local`/`git`/`object_store` fetchers at pinned refs; front-matter parser; exemplar store, join graph, metric/filter extraction; lexical index; feedback inbox; `coverage.json`; agent `query_librarian`. | `0113`; `0049` pattern; `0027` source catalog | C-01 | T-005–T-009, T-017 (C-01) |
| `0115` | Schema catalog, semantic mapping & access (built) | Catalog snapshots (introspect/file), drift reconciliation, concept mapping seeded from `0081` `securities_financing_prime` on `0008` rules (plus drafted pack amendments) and governed-metric source-query bindings, viewpoint/unit declarations, secret pointers, allowlists, redaction, clearance; agent `semantic_mapping_steward`. | `0114`; `0063`; `0008`; `0081`; `0058`; `secrets_management` | C-02 | T-010–T-013, T-032 (binding), T-033 |
| `0116` | Governed tier, grounded SQL composition, verification & execution | Governed-first routing through `0080` and the `Reader` over metric source queries; retrieval-first composer for the tail; deterministic verifier with tokens and cost guard; read-only execution seam over `0023`; provenance and `0070` envelope; agents `sql_composer`, `sfmeridian_orchestrator`. | `0115`; `0080`; `0070`; `0023`; `adapters/llm_runtime/` | C-03, C-04 | T-014–T-017, T-031, T-032, T-034 |
| `0117` | Grounded answering & hallucination evaluation | Grounding check, recompute, viewpoint enforcement, abstention; synthetic fixture DB and query repo; golden-question set, metrics, thresholds, release gate; agent `answer_grounding_reviewer`. | `0116`; `0063`; `0025`; coordinates with `0103` | C-05 | T-018, T-019, T-035 |
| `0118` | Plugin packaging & app surfaces | `plugins/sfmeridian/` distributable; Python API; MCP server on `0052`; Claude Code plugin via `0110`; cross-surface contract tests; SemVer per `0047`; second-dialect fixture. | `0117`; `0052`; `0110`; `0047` | — (surfaces) | T-001 (schemas), T-020–T-023, T-025 |
| `0119` | Securities-lending analytics agents and specialist workflows | Agents `utilization_specials_analyst`, `recall_buyin_risk_analyst`, `lending_revenue_analyst`; workflows W2–W5 and W7–W12 wiring the optimization, risk, portfolio-management, knowledge, and ML handoffs (`plan.md` handoff map); decision-support envelope producers (REQ-022). | `0118`; `0028`; `0066`; `0067`; `0013`; `0006`/`0046` | C-06, C-07, C-08 | T-026 (part) |
| `0120` | Lending reporting completeness checks | Agent `lending_reporting_check`; field-completeness and consistency checks for SFTR / Rule 10c-1a style datasets; never submits; regulatory dates confirmed by adopter counsel. | `0119`; `0069` when written | C-09 | T-026 (part) |
| `0121` | Adaptive securities-finance dataset research (built) | Incorporates the Dataset Intake Investigator POC and its adaptive EDA spec: research context, reviewed read-only templates with static checks, pushed-down exact aggregates, securities-finance rule pack, coverage ledger, budgets, evidence-linked recommendations, reproducible bundle; agent `lending_data_researcher`, workflow W13. | `0114`; `0063`; `0066` | C-10 | `0121` T-001–T-018 |

## Phases

### Phase 0 — Foundation (`0113`) · ~1 week

Spec, plan, tasks, roadmap, configuration template, front-matter convention,
roster and coverage matrix, evaluation protocol, and the governed-first design
on `0080`/`0081`. Ships documents only.

**Exit:** `0113` approved; `tooling_catalog.md` screened (done) with
admission reviews scheduled for the `adopt` entries; the open questions in `spec.md` answered (done 2026-10-22: agency
lender viewpoint; PostgreSQL, Oracle, Databricks; lexical retrieval; `0119`
before `0120`) and a named reviewer assigned for the `0081` `securities_financing_prime` pack; `spec`,
`spec-index`, and `handoff-sync` gates clean.

### Phase 1 — Learn the query repository (`0114`) · built

A configured repository (local and Git at a pinned ref) indexes into
exemplars, join graph, metric candidates, and a lexical index; the feedback
inbox works; `query_librarian` exists.

**Exit:** AC-003–AC-006, AC-014, AC-015 pass; re-index of an unchanged
repository is a no-op; the synthetic repository's golden extraction matches.

### Phase 2 — Know the schema and the meaning (`0115`) · built

Catalog snapshots and drift; `0063` concept mapping with viewpoint and unit;
access controls and redaction.

**Exit:** AC-007, AC-008, AC-017, AC-029 pass; the `0081` pack amendments
are proposed and the pack review is scheduled (reviewed is preferred, not
required, to proceed); drifted exemplars are excluded; no
credential appears in any artifact (secret-scan clean).

**Status (2026-10-22):** built and Approved. The exit criteria are met by
`0115` AC-004 (drift), AC-007 (governed ratio; by-counterparty utilization is
refused, see `0115` Exceptions), AC-010/AC-011 (clearance, redaction,
credentials), and AC-005/AC-013 (all five pack metrics, amendments proposed,
caveat). The pack reviewer is named (Joshua Lutkemuller, CFA); the review
itself is pending, so governed answers carry the unreviewed-pack caveat.

### Phase 2b — Dataset research (`0121`) · built

Added 2026-10-22 at the owner's direction (incorporating the Dataset Intake
Investigator POC). Gives every later phase a trusted view of each lending
dataset before answers depend on it; its template static check is the seed
of `0116`'s verifier.

**Exit:** `0121` AC-001–AC-024 pass except AC-016 (live connectors), which
stays open until nonproduction environments exist.

### Phase 3 — Grounded SQL (`0116`) · ~3–4 weeks · **MVP** · **next (not started)**

Retrieval-first composition, deterministic verification, read-only execution,
provenance and replay; the end-to-end `ask` tool in shadow mode.

**Exit (MVP):** AC-009–AC-011, AC-021, AC-027, AC-028, AC-030 pass; every
question that maps to a governed metric is answered at tier `governed`; the adversarial verifier suite
rejects 100% of cases; identifier-fabrication rate in *executed* SQL is 0 on a
preliminary golden set; `ask` answers lookup and aggregation questions on the
synthetic database with citations.

**Starting brief:** `handoff.md` §3 (what to build, which `0114`/`0115` modules
and `0080`/`0023` interfaces each piece plugs into, and the fixture database it
still needs).

### Phase 4 — Grounded answers, measured (`0117`) · ~2–3 weeks

Grounding check and abstention; the versioned golden set and release gate.

**Exit:** AC-012, AC-013, AC-016, AC-022 pass; tier-agreement rate 100% and
wrong-tier rate 0 on the governed golden questions; NFR-002 thresholds met on the
synthetic golden set over three seeds; the eval report is reproducible.

### Phase 5 — Ship as a plugin (`0118`) · ~2 weeks

Distributable package; Python API, MCP server, Claude Code plugin; contract
tests; PostgreSQL, Oracle, and Databricks SQL dialects.

**Exit:** AC-001, AC-002, AC-020, AC-023 pass; `sfmeridian 1.0.0`
tagged with a release note; a reference app (a minimal CLI chat over the MCP
server) answers the golden set with identical results to the Python API.

**Pilot:** one named desk in shadow mode on the adopter's real query
repository with an adopter-private golden set; promotion of the pilot to
live use requires the NFR-002 thresholds on the private set as well.

### Phase 6 — Expand (`0119`, `0120`, options) · ongoing

- `0119` analytics agents and workflows W2–W5 (utilization/specials monitor,
  recall and buy-in risk, revenue attribution, PIT borrow-cost feed to backtests),
  then W7–W12 in this order: W10 borrow-aware portfolio decisions (ML forecasts
  and PM constraints), W7 inventory allocation, W8 collateral optimization, W11
  counterparty and liquidity review, W9 fee and capacity pricing, W12 plugin
  governance (model risk, MLOps, knowledge curation).
- `0120` reporting completeness checks.
- Options, each needing its own spec and evaluation evidence: fine-tuning on
  promoted exemplars; query-index resources over `0052`; integration with
  `0104` knowledge graph (counterparty and security relationships); scheduled
  daily packs through `0055`/`0060`; dashboards through `0015`–`0018`.

## Milestones & KPIs

| Milestone | Phase | KPI |
| --- | --- | --- |
| M1 Repository learned | 1 | ≥ 95% of annotated synthetic queries indexed as `reviewed`; 0 malformed files silently accepted. |
| M2 Schema-aware | 2 | 100% of semantic-mapping concepts resolve to catalog objects; drift detected on every seeded change. |
| M3 MVP grounded SQL | 3 | Fabrication in executed SQL = 0; adversarial rejection = 100%; exemplar-reuse rate reported. |
| M4 Measured | 4 | NFR-002 thresholds met on synthetic golden set (3 seeds). |
| M5 Plugin 1.0 | 5 | Identical results across surfaces; one reference app integrated. |
| M6 Pilot live | 5–6 | NFR-002 thresholds met on the adopter-private golden set; desk sign-off. |

## Dependencies on Other Programs

- `0080` natural-language analytics and `0081` domain packs (both Draft):
  **hard dependency** for the governed tier from Phase 3. Pinned `quantsmith`
  version, isolated in `governed/` (RISK-013). Reviewing the
  `securities_financing_prime` pack removes the unreviewed-pack caveat and
  makes `0080` write-back eligible (still off by default, REQ-026).

- `0103` evaluation (reserved): shares red-team and LLM-judge methods; `0117`
  does not wait for it and uses deterministic metrics first.
- `0069` regulatory/legal knowledge pack (reserved): `0120` cites it when
  written; until then regulatory context is labelled `unverified`.
- `0104` knowledge graph (reserved): optional Phase 6 integration.
- `0064`/`0068` short-term-markets runtimes and ingestion (reserved): no
  blocking dependency; the plugin consumes adopter databases, not these feeds.

## Change Control

Adding a child spec, an agent, or a tool to the contract requires amending
`spec.md`/`plan.md` first (new `REQ-*`/coverage row), then flowing through
the gates. Reordering phases requires an owner decision recorded here.
