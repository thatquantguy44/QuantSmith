# Spec: SFMeridian — Query Repository Connector & Indexer

- **ID:** 0114-sfmeridian-query-repository-indexer
- **Status:** Approved
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** Joshua Lutkemuller, CFA (2026-10-22, with `0113` and the Phase 1 go-ahead)
- **Last updated:** 2026-10-22

> WHAT and WHY. References to the parent spec are written `0113` R-nnn /
> A-nnn / N-nnn (its `REQ-`/`AC-`/`NFR-` IDs) so the spec gate never reads
> them as this spec's own IDs.
>
> Phase 1 of the SFMeridian roadmap
> (`specs/0113-seclending-intelligence-plugin/roadmap.md`). This child refines,
> and may tighten but not loosen, what `0113` fixes. Every requirement here
> traces to a `0113` requirement.

## Problem & Context

SFMeridian answers securities-lending questions from an adopter's databases by
learning from the adopter's own repository of reviewed SQL queries (`0113`
REQ-004–REQ-006). Nothing can be grounded until the plugin can (a) read a
configuration that says where those queries live, (b) fetch them reproducibly
from Git, a local folder, or an object store, (c) tell reviewed queries from
drafts, unannotated files, and malformed ones, and (d) turn them into cited,
searchable exemplars plus the structure later phases need: the join graph,
metric definitions, filters, and parameter templates. It also needs the
reviewed path by which new exemplars are added, and machine-readable forms of
the `0113` roster, handoff map, and tooling catalog so they can be checked.

First deployment decisions (`0113`, 2026-10-22): agency lender / beneficial
owner viewpoint; PostgreSQL, Oracle, and Databricks SQL dialects (SQLite for
offline tests); lexical retrieval only.

## Goals

- A configuration loader that fails closed and makes the query repository a
  pure configuration value.
- Reproducible, incremental indexing of one or more query repositories.
- Exemplars, join graph, metric candidates, and filter patterns, every one
  cited to repository, ref, path, and line span.
- Deterministic lexical search that respects review status.
- A human-reviewed feedback inbox.
- Machine-checkable roster, handoff map, and tooling catalog.
- The shared tool registry and the agent loop harness every SFMeridian agent
  runs on, so agents are bounded, verified tool loops rather than only
  contract files (`0113` R-028, R-029).
- The first SFMeridian loop agent, `query_librarian`.

## Non-Goals

- No database connections, catalog introspection, or semantic mapping (`0115`).
- No SQL composition, verification, or execution (`0116`). Structure
  extraction here is for learning; it is never a safety check.
- No embeddings (owner decision: lexical only).
- No network access in tests; Git tests use local repositories.
- No real query text, schemas, or counterparties in the repository; fixtures
  are synthetic and disclosed.

## Requirements

| ID | Requirement | Traces to | Priority |
| --- | --- | --- | --- |
| REQ-001 | The plugin shall load configuration from one file (YAML subset or JSON) named by argument or `SFMERIDIAN_CONFIG`, merge built-in defaults → file → `SFMERIDIAN__*` environment overrides, validate it against a published schema (unknown keys, wrong types, missing required fields, unresolved `<placeholder>` values, credentials embedded in values, `read_only: false`, unsupported dialects or retrieval modes, and write-back targets classed as lending, trading, or books-and-records all fail with named codes), support a validate-only mode, and expose a stable hash of the resolved configuration. Per-call overrides are limited to an allowlist and may only tighten safety fields. | `0113` R-003, R-004, R-020, R-026 | must |
| REQ-002 | The configuration and query front-matter shall be parsed by a strict, standard-library YAML-subset parser (block mappings and sequences, flow lists and maps of scalars, quoted and plain scalars, folded and literal blocks, comments) that rejects anything else — anchors, aliases, tags, tabs, duplicate keys, multi-line flow — with file and line. | `0113` N-003, K-005 | must |
| REQ-003 | The plugin shall fetch query repositories of kind `local`, `git` (cloned bare into a cache, resolved to a commit SHA from the configured `ref`), and `object_store` (through a caller-injected client; no SDK bundled), apply include/exclude globs (`**` supported), refuse paths that escape the repository root, and identify each snapshot by a deterministic ref. | `0113` R-004 | must |
| REQ-004 | The plugin shall parse front-matter from a leading `-- ---` comment block, or from a sidecar `<name>.yml` when the repository declares `metadata_convention: sidecar`; validate required fields (all files: `id`, `title`, `intent`, `review_status`; additionally for `reviewed`: `owner`, `dialect`, `profile`, `params`, `tables`, `pit_columns`, `grain`, `reviewed_by`, `reviewed_on`); reject malformed or inconsistent files (bad syntax, unknown keys, placeholders in a reviewed file, parameters used but not declared or declared but not used, duplicate query IDs) with a reason; and index files with no front-matter as `unreviewed`. | `0113` R-005 | must |
| REQ-005 | The plugin shall extract SQL structure deterministically with a standard-library tokenizer: statement count and kind, CTE names, base tables and aliases, join edges with keys, parameters and parameter style (`:name`, `%(name)s`, `?`, `$n`), filter columns and operators (literal values redacted), select-list metric expressions, and a normalized SQL hash, across the SQLite, PostgreSQL, Oracle, and Databricks quoting rules. | `0113` R-006, R-020 | must |
| REQ-006 | The indexer shall build content-addressed, sorted JSONL exemplars and derived artifacts — join graph (support counts, exemplar IDs), metric candidates (with a conflict flag when one name has several expressions), filter patterns — each citing repository, ref, path, and line span; re-indexing an unchanged repository shall write nothing; the index shall never contain result rows or secrets. | `0113` R-006, N-001, N-005 | must |
| REQ-007 | The plugin shall provide deterministic BM25 search over exemplars with a normalized score in `[0, 1)`, a configurable minimum score, and review-status eligibility: `reviewed` always; `draft` and `unreviewed` only as flagged hints when the repository allows them; `deprecated` and rejected never. | `0113` R-009 (retrieval half), RISK-004 | must |
| REQ-008 | The plugin shall provide a feedback inbox — propose, list, promote, discard — where candidates carry provenance, are invisible to search until promoted, and are promoted only by a configured promoter who is not the proposer, using pseudonymous handles (never email addresses). | `0113` R-014 | must |
| REQ-009 | The plugin shall ship machine-readable `coverage.json` (C-01…C-09), `handoffs.json` (the `0113` specialist handoff map), and `tooling_catalog.json`, with validators: coverage rows have distinct workflows, never-boundaries, and creating child specs, and built agents exist; every handoff agent exists and appears in a declared workflow; tooling entries carry valid rings and, in strict mode, completed admission reviews for every `adopt`/`trial` entry; and no core module imports a non-standard-library package. | `0113` R-015, R-021, R-027 | must |
| REQ-010 | The SDK shall add the `query_librarian` agent (coverage row C-01) under `agents/securities_financing/sfmeridian/`, with the four contract files, a `Spec-Driven Role` section, a catalog row, and regenerated registry and skills export. | `0113` R-015 | must |
| REQ-012 | The plugin shall provide one tool registry used by apps and agents alike: each tool has a name, description, JSON-Schema input (validated before the handler runs), and an effect (`read`, `index`, `propose`, `human_only`); this slice registers `config.validate`, `repos.index`, `repos.status`, `queries.search`, `queries.get`, `index.rejections`, `index.findings`, `index.metrics`, `index.joins`, `feedback.propose`, `feedback.list`, `governance.validate`, and the `human_only` `feedback.promote` and `feedback.discard`. | `0113` R-001, R-029 | must |
| REQ-013 | The plugin shall provide the agent loop harness: manifests (goal, tool grant, verifiers, budgets, repair limit, human checkpoints, never-boundary) loaded from data; a loop of decide → tool call → observe → verify that refuses non-granted and `human_only` tools, enforces step and tool-call budgets, completes only when every verifier passes (feeding failures back for bounded repair), treats escalation as an outcome, survives policy errors, and records a deterministic run ID and trace; and a `ModelPolicy` over a caller-injected completion function that parses one JSON action per step and escalates after two malformed answers. | `0113` R-028 | must |
| REQ-014 | `query_librarian` shall run as a loop agent with a deterministic policy (validate → index → status → rejections → findings → metric conflicts → staged inbox → finish, escalating on invalid configuration or unreachable repositories) and three verifiers: every finding cites evidence observed in the run, every rejected file is reported, and drafted front-matter is never marked reviewed. | `0113` R-014, R-028 | must |
| REQ-011 | The plugin shall provide a CLI (`python -m sfmeridian`) for config validation, indexing, status, search, feedback, and governance validation, emitting JSON. | `0113` R-001 | should |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Portability | Package code imports only the Python 3.11+ standard library. |
| NFR-002 | Determinism | Two index runs over the same configuration and snapshot produce byte-identical artifacts; search ties break by exemplar ID. |
| NFR-003 | Offline tests | No test touches the network; Git is exercised with local repositories. |
| NFR-004 | Data safety | Fixtures are synthetic and disclosed (`0025`); config validation rejects credentials in values; the index stores SQL and metadata only. |
| NFR-005 | Catalog consistency | `run-stage.sh` gates pass under `QF_STAGE_ENFORCE=1`. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given configs with a missing required field, an unknown key, a placeholder, an embedded credential, `read_only: false`, an unsupported dialect, embeddings retrieval, and a books-and-records write-back target, when validated, then each fails with its named code; given the fixture config, then it validates and its hash is stable across loads and environment-variable ordering; and a non-allowlisted or loosening per-call override is denied. (`0113` A-003, A-030 config half) | REQ-001 |
| AC-002 | Given YAML-subset inputs, when parsed, then the template and fixture config equal PyYAML's reading where PyYAML is installed, and anchors, tags, tabs, duplicate keys, and multi-line flow are rejected with a line number. | REQ-002 |
| AC-003 | Given a `local` repository and a `git` repository at a pinned commit, both declared only in configuration, when indexed, then both are indexed, every exemplar records its repository, resolved ref, and path, excluded globs are skipped, a path escaping the root is refused, and the package source holds no repository location. (`0113` A-004) | REQ-003 |
| AC-004 | Given the synthetic repository's valid, malformed, inconsistent-parameter, duplicate-ID, and un-annotated files, when indexed, then valid files carry all fields, each bad file is rejected with its reason, and the un-annotated file is `unreviewed`. (`0113` A-005) | REQ-004 |
| AC-005 | Given fixture SQL with CTEs, aliases, multi-way joins, `USING`, every parameter style, backtick and double-quoted identifiers, comments, and string literals, when extracted, then tables, joins, parameters, filters (literals redacted), and metric expressions match the expected values, and statement kind and count are reported. | REQ-005 |
| AC-006 | Given the synthetic repository, when indexed twice, then the join graph, metric candidates (including the `utilization` conflict), and filter patterns match the expected extraction, every artifact cites file, ref, and line span, the second run writes nothing, and no artifact contains a literal value or credential. (`0113` A-006) | REQ-006 |
| AC-007 | Given search queries, when run, then reviewed exemplars rank first with scores in `[0, 1)`, drafts and unannotated files appear only as hints from a repository that allows them, deprecated and rejected files never appear, results below the minimum score are dropped, and ties are deterministic. | REQ-007 |
| AC-008 | Given a proposed correction, when searched, then it is absent; when promoted by its proposer, by a non-promoter, or with an email-shaped handle, then promotion is refused; when promoted by a configured promoter, then it is searchable with `feedback` provenance. (`0113` A-014) | REQ-008 |
| AC-009 | Given the shipped catalogs, when validated against `agents/`, then coverage, handoff, and tooling checks pass (tooling in non-strict mode), strict mode lists every pending admission review, a duplicated workflow or a missing agent fails, and the core-import check finds only standard-library imports. (`0113` A-015, A-025, A-031 catalog half) | REQ-009 |
| AC-010 | Given the agent catalog, when the gates run, then `query_librarian` has its four files, a `Spec-Driven Role` section, a catalog row, a registry entry, and an exported skill. | REQ-010 |
| AC-011 | Given the fixture config, when the CLI validates, indexes, searches, lists tools, and runs `query_librarian`, then each command exits 0 with JSON output, and an invalid config exits non-zero with codes. | REQ-011 |
| AC-015 | Given the registry, when listed and called, then apps and agents see the same tools and schemas, an invalid input is refused before its handler runs with `E_TOOL_INPUT`, an unknown tool returns `E_TOOL_UNKNOWN`, and promotion and discard are `human_only`. (`0113` A-033) | REQ-012 |
| AC-016 | Given scripted policies, when one calls a non-granted tool, one calls `feedback.promote`, one loops past the step budget, one raises, and one finishes with an uncited finding and then repairs it, then the runs end `denied`, `denied`, `budget_exhausted`, `failed`, and `completed` respectively, the repair is visible in the trace, a model policy's malformed answers escalate, and replaying a run yields the same run ID and trace. (`0113` A-032) | REQ-013 |
| AC-017 | Given the synthetic repository, when `query_librarian` runs, then it completes with findings for all four rejected files, the `utilization` conflict, and the unannotated file, each citing observed evidence, drafts marked `draft`, and an invalid configuration or unreachable repository escalates. | REQ-014 |
| AC-012 | Given the package source, when its imports are scanned, then only standard-library modules are imported; and the full test module runs without network access. | NFR-001, NFR-003 |
| AC-013 | Given two runs of the indexer and search, when compared, then artifacts are byte-identical and search results identical. | NFR-002 |
| AC-014 | Given the fixtures, when the `data-provenance` and `secret-scan` gates run, then the disclosure is complete and no secret is found; and all gates pass under enforcement. | NFR-004, NFR-005 |

## Data & Dependencies

- `0113` (approved): configuration contract, metadata convention, roster,
  handoff map, tooling catalog.
- Pattern reuse without import: `0049` reviewed write path (propose → promote),
  `0048` pseudonymous handles, `0027` source-catalog style.
- `git` CLI for `git` repositories (present in CI and developer machines).
- Synthetic fixtures: `plugins/sfmeridian/fixtures/` with a disclosure.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The heuristic tokenizer misreads unusual SQL. | Wrong join edges or metric candidates are learned. | Extraction is learning-only and cited; findings recorded per exemplar; verification is a separate fail-closed component (`0116`); a stricter parser is a catalogued option. |
| RISK-002 | Front-matter or SQL comments carry prompt-injection text. | Later model steps are steered. | Parsed as data only; nothing in this phase passes text to a model. |
| RISK-003 | A Git URL or object key embeds a credential. | Credential lands in config, logs, or index. | Validation rejects credential-shaped values; errors redact URIs; credentials come from the environment's Git credential helper, never config. |
| RISK-004 | Unreviewed SQL is learned as institutional knowledge. | Errors laundered into answers. | Default `reviewed_only`; hints flagged; promotion needs a distinct configured promoter. |

## Assumptions & Open Questions

- Assumption: adopters can add front-matter to the queries they want treated
  as reviewed; others index as hints or not at all, by repository policy.
- Open (carried from `0113`, not blocking this phase): the `0081` pack reviewer.

## Exceptions

None.
