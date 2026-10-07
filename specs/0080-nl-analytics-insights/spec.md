# Spec: Natural-Language Analytics — Visualization, Interpretation, and Write-Back

- **ID:** 0080-nl-analytics-insights
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** — (pending owner review)
- **Last updated:** 2026-10-07

> WHAT and WHY only. Implementation lives in `plan.md`.

## Problem & Context

The Data Analyst track has every piece except the one a user actually talks to.
Metrics are governed (`0008`), dashboards render to seven tools from one
`DashboardSpec` (`0014`–`0018`), storytelling has a standard
(`instructions/data_storytelling.md`), access is enforced at the read boundary
(`0058`), and agentic runs have a replayable envelope (`0070`). But every one of
those surfaces assumes someone already knows which metric, which slice, and
which chart they want. The question a desk actually asks — *"how did funding
cost move this week by desk, and what drove it?"* — has no path through the
SDK: nothing turns it into a governed query, nothing picks an honest chart for
the answer, nothing states what the numbers mean without inventing numbers, and
nothing records the answer so tomorrow's question can build on today's.

The handoff tracks the gap twice and closes it nowhere:
`agents/analytics/data_visualization/` is a P3 `proposed` row in
`docs/handoffs/future_features.md`, and "insights across days" (what changed
since yesterday, this week) has no owner at all — the morning brief (`0059`) and
the scheduled daily report (`0055`/`0060`) each produce one day's output and
forget it.

This spec defines a natural-language analytics workflow: a user's question
becomes a **typed, governed query plan** (never free-form SQL); the plan runs
against the semantic layer under the viewer's clearance; the result gets a
**deterministically chosen chart** and a **deterministically computed insight
set**; the answer goes **back to the user in chat**, and — when requested and
approved — the insights are **published to a database** as append-only,
provenance-carrying records that later questions can compare against.

It supports two decisions: *what does the data say about my question right now*
(chat), and *what should the organization remember about it* (write-back).

## Goals

- A user can ask a data question in natural language and get back a chart, a
  plain-language interpretation, and the exact interpretation of their question
  the system used — in one chat response.
- The language model, when used, only ever proposes a **plan over governed
  metrics**; it can never execute code or SQL, widen access, or state a number
  the computation did not produce.
- Chart selection and insight computation are deterministic and reproducible,
  so the same question over the same data gives the same answer.
- Publishing results to a database is opt-in, declared, approved, append-only,
  idempotent, and reversible — never a side effect of asking a question.
- Persisted insights make multi-day questions ("what changed since yesterday")
  answerable point-in-time.
- Promote `agents/analytics/data_visualization/` from `proposed` into a built,
  narrow agent, and give the workflow an owning agent.

## Non-Goals

- **Free-form text-to-SQL.** The plan vocabulary is the governed metric
  registry (`0008`); a question outside it gets a clarification, not a
  generated query. Ad hoc SQL exploration stays with `sql-integration-agent`
  and a human.
- **Choosing an LLM provider or model.** The interpreter seam is
  provider-neutral via `adapters/llm_runtime/`; selection is an adopter
  decision.
- **Database drivers, connection strings, or credentials in the SDK.** Reads
  and writes go through caller-injected callables, as in `0032`/`0059`.
- **Writing to source or fact tables**, updating or deleting existing business
  data, or any write that is not an append of insight records to a declared
  target.
- **Causal claims.** Interpretation describes levels, changes, contributions,
  and outliers; it does not assert why something happened.
- **A new chat UI or hosted service.** Chat delivery is a returned payload. The
  first surface is a route in the existing, local `0057` Knowledge Console
  (REQ-021); Slack and any hosted service stay out of scope.
- **Forecasting or model fitting** on the queried data.
- **New dashboard renderers.** A chart spec *may* be promoted to a
  `DashboardSpec` panel; rendering stays with `0015`–`0018`.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall accept a natural-language question with caller context (viewer identity/clearance, as-of timestamp, optional prior-turn plan) and produce a typed `QueryPlan` that references only governed metrics (`0008`), their declared dimensions, filters on declared dimension values, a time window and grain, an optional comparison (prior period, same period prior year, a named prior insight), and an optional rank/limit. The plan shall have no field capable of carrying SQL or executable code. | must |
| REQ-002 | When a question cannot be resolved to exactly one valid plan (unknown metric, undeclared dimension, ambiguous synonym, missing time window with no declared default), the system shall return a clarification request naming the candidates it considered, never a guessed plan. Every default it applies (e.g. default window) shall be declared in configuration and echoed back in the response. | must |
| REQ-003 | The system shall provide a pluggable interpreter seam: a deterministic keyword/synonym interpreter ships as the baseline, and an LLM interpreter (via `adapters/llm_runtime/`) plugs into the same seam without caller changes. Every interpreter's output shall pass the same plan validator before execution. | must |
| REQ-004 | Before execution, the plan shall be checked against the viewer's clearance (`0058`). Metrics, dimensions, and datasets above the viewer's clearance shall be indistinguishable from nonexistent (existence masking) in both the answer and any clarification. | must |
| REQ-005 | The system shall execute a validated plan through the `0008` semantic layer over rows supplied by a caller-injected, read-only data-access executor, respecting the as-of timestamp. The result shall carry row counts, data freshness (latest period observed), and a content hash of plan and result. | must |
| REQ-006 | The system shall choose a `ChartSpec` deterministically from the result's shape using a declared form rule (time series → line; one categorical dimension → sorted bar; single value → KPI with comparison delta; two measures → scatter; otherwise table), using `dashboard_spec.CHART_TYPES`. Every chart spec shall carry a title that states the finding, units, axis labels, a source/as-of footnote, and a text alternative, and shall be promotable to a `DashboardSpec` `Panel`. | must |
| REQ-007 | The system shall compute a deterministic insight set from the result: current level, change versus the comparison (absolute and percent), top and bottom contributors to the change and their share, trend direction over the window, outliers against a declared trailing baseline, and concentration. Each insight shall carry the exact values it rests on. | must |
| REQ-008 | The chat narrative — whether rendered from a template or written by an LLM — shall state only numbers present in the insight set or result; a grounding validator shall reject any narrative containing an unbacked numeric claim and flag causal language. Triggered caveats (small sample, stale data, partial period, synthetic data per `0025`) shall be included. | must |
| REQ-009 | The system shall return a `ChatResponse` containing: a one-sentence headline answer, supporting insights, the chart spec with a portable rendering (Vega-Lite JSON) and a Markdown-table fallback, the plan echoed back in plain language ("how I read your question"), caveats, and citations (metric definitions and owners, source, as-of). | must |
| REQ-010 | When requested, the system shall publish insight records to a database target declared in a write-back contract (target name, schema, idempotency key, allowed columns). Records are append-only and carry provenance: run id, question hash, plan hash, metric-definition versions, as-of, created-at, author handle, interpreter mode. Writes are idempotent on the key, dry-run by default, executed by a caller-injected writer, and never touch source or fact tables. | must |
| REQ-011 | A non-dry-run write shall require an explicit approval on the request unless the target's contract declares `auto_approve: true`; every committed write batch shall be reversible by run id through the same injected writer. | must |
| REQ-012 | A question may compare against persisted prior insights ("since yesterday", "vs last week's answer"); the comparison shall read the write-back store as-of the request and shall never modify persisted history. | should |
| REQ-013 | Every request shall emit a `0070` run envelope (context manifest; prompt manifest when an LLM is used; audit events for interpret, validate, execute, chart, interpret-insights, narrate, deliver, write) sufficient for the `0070` replay engine to reproduce the plan, result, chart spec, and insight set. | must |
| REQ-015 | The system shall apply the analytics domain packs (`0081`) selected by the dataset's `sources/*.yml` domain tags: pack vocabulary extends interpretation, pack units and conventions govern display (e.g. basis points for yield moves), pack additivity governs aggregation and contributor insights, and pack caveats and chart conventions are added to the response. A term that is a conflict between selected packs yields a clarification. | must |
| REQ-016 | When any applied pack is not `reviewed`, the response shall carry an "unreviewed domain pack" caveat naming it, and database write-back shall be refused; write-back is eligible only when every applied pack is `reviewed` (`0081` REQ-005). | must |
| REQ-017 | When no pack matches, the system shall use generic behavior (unit and additivity taken from the `0008` definition only) and say so in the response; packs may only restrict interpretation, never widen access or enable an insight the generic rules forbid. | must |
| REQ-018 | When any pack is applied, the response and its `0070` envelope shall record where the pack catalog came from (`0081` REQ-013: local or bundled, location, package version, content hash). Domain tags supplied with no pack catalog at all shall be a configuration error, never a silent generic answer. | must |
| REQ-019 | Language-model calls shall go through a caller-injected completion callable that follows the `adapters/llm_runtime/` contract, so the runtime package stays free of network code and no provider or gateway is assumed. The backend shall be chosen by configuration, not code, using QuantMeridian's `llm-profiles/1` format unchanged (`schema_version`, `default_profile`, `default_profile_env`, and per profile `enabled`, `label`, `api_style`, `model` or `model_env`, `base_url_env`, `auth`, `header_envs`, `limits`, `data_classes`, `uses`, `fallback_profile`), so one profiles file serves both repositories. The SDK shall ship standard-library backends in `quantsmith.adapters.llm_runtime` (documented in `adapters/llm_runtime/`) for every `llm-profiles/1` `api_style`: `anthropic_messages`, `openai_chat_completions` (covering self-hosted vLLM/Ollama, LiteLLM-style gateways, and Azure OpenAI through `base_url_env` and `header_envs`), and `none` (keyword interpreter and template narrator, no model). A profile is used for a role only if its `uses` lists that role (`interpreter`, `narrator`); `limits` (`timeout_ms`, `max_retries`, `max_output_tokens`, `per_job_token_cap`) are enforced per answer; `fallback_profile` is tried on a transport failure, never on a validation failure. Endpoints, models, and credentials come only from the named environment variables, never from the file. The run envelope records the profile, `api_style`, model, and token usage when reported; no key, token, or authorization header is ever logged or persisted. Further flexibility — a declared generic HTTP/JSON shape, an import-path callable for SDK-based providers (Bedrock, Vertex), and a token-command credential — shall be proposed to QuantMeridian as an additive `llm-profiles` revision rather than added unilaterally, because `llm-profiles/1` rejects unknown fields; until then any caller can still inject its own completion callable. | must |
| REQ-020 | The SDK shall provide an LLM interpreter and an LLM narrator on that backend. The interpreter asks for a `QueryPlan` as JSON; malformed output or a plan the validator rejects yields `clarification_needed` with the reason and no execution. The narrator's output passes the REQ-008 grounding check; a rejected narrative is replaced by the template narrative and the response carries a caveat saying so. | must |
| REQ-021 | The `0057` Knowledge Console shall gain an analytics question route that calls `answer()` under the console's own viewer-clearance resolution (`0058`, including `preview-access` overrides) and shows the headline, chart (Vega-Lite), insights, plan echo, caveats, and citations. It binds to localhost by default; any write-back it starts follows REQ-010, REQ-011, and REQ-023. | must |
| REQ-022 | A publish request may opt in to proposing its insights as a `0048` knowledge candidate. A candidate is created only after a committed (not dry-run) write succeeds and every applied domain pack is `reviewed`; it cites the run id, plan hash, record keys, metric-definition versions, and as-of; it enters review as a candidate and is never promoted automatically. A dry run shows the candidate it would propose. When no candidate is created, the response states why. | should |
| REQ-023 | A committed write shall record the approver's pseudonymous handle (`0049`) alongside the author's. Per-request confirmation stays required unless the contract declares `auto_approve: true`. A contract may declare `approver_roles` (checked against an optional `roles` list on `access/roster.yml` entries) and `require_distinct_approver`. A target that declares `approver_roles` is refused while the roster has no entries, and a refused approval returns `write_rejected` with the reason. | must |
| REQ-014 | The SDK shall add two narrow agents: `agents/analytics/data_visualization/` (chart choice, encoding, color, accessibility — promoting the `proposed` backlog row) and `agents/analytics/nl_analytics/` (question → plan → response orchestration, clarification, write-back request), each handing off to `metrics_semantic_layer`, `data_storytelling`, and `sql-integration-agent` rather than duplicating them. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Reproducibility | The same question, registry, rows, as-of, configuration, and interpreter version yield byte-identical plan, result, chart spec, and insight set. |
| NFR-002 | Point-in-time correctness | No row with period after the as-of contributes to any result, comparison, baseline, or prior-insight lookup. |
| NFR-003 | Security boundary | Standard library only in the runtime; no database driver, network call, connection string, or credential in the SDK; data access read-only; writes only to declared targets through an injected writer. |
| NFR-004 | Privacy | Audit events store question and result hashes plus redacted text per the access level; `adapters/llm_runtime/` privacy flags (`contains_pii`, `contains_mnpi`, `contains_restricted_positions`) are propagated from the dataset's declared classification. |
| NFR-005 | Latency (deterministic path, excluding data fetch and LLM calls) | < 2 s end-to-end for 100,000 fact rows on a developer laptop. |
| NFR-006 | Honest failure | Every non-answer (clarification, access-masked, empty result, stale data, write rejected) returns a typed status and a user-readable reason; no path returns an empty chart or a silent no-op. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a registry and the question "funding cost by desk last week", when interpreted by the baseline interpreter, then the plan names the governed metric, the declared `desk` dimension, and the resolved window, and the plan type has no field that accepts SQL or code. | REQ-001 |
| AC-002 | Given a question naming an undefined metric or an ambiguous synonym, when interpreted, then the response status is `clarification_needed`, lists the candidate metrics considered, and no execution occurs. | REQ-002, NFR-006 |
| AC-003 | Given a question with no time window and a configured default window, when answered, then the default is applied and echoed in the plan description. | REQ-002 |
| AC-004 | Given a stub LLM interpreter that returns (a) a valid plan and (b) a plan referencing an undeclared dimension, when each runs through the seam, then (a) executes and (b) is rejected by the same validator used for the baseline. | REQ-003 |
| AC-005 | Given a viewer with `internal` clearance and a `restricted` metric, when the viewer asks about that metric, then the response is indistinguishable from asking about a nonexistent metric, including in clarification candidates. | REQ-004 |
| AC-006 | Given fact rows spanning periods before and after the as-of, when a plan executes, then only rows at or before the as-of contribute, and the result reports row count, latest period observed, and a stable content hash. | REQ-005, NFR-002 |
| AC-007 | Given results shaped as a time series, a single categorical breakdown, a single value, a two-measure pair, and a two-dimension breakdown, when a chart is chosen, then the chart types are `line`, `bar` (sorted descending), `kpi`, `scatter`, and `table` respectively, and each carries title, units, axis labels, footnote, and text alternative. | REQ-006 |
| AC-008 | Given a chart spec, when promoted, then it yields a valid `DashboardSpec` `Panel` that the Power BI profile (`0015`) renders without error. | REQ-006 |
| AC-009 | Given a result and a prior-period comparison with known values, when insights are computed, then level, absolute and percent change, contributors (whose shares sum to the total change within 1e-9), trend direction, outliers, and concentration match hand-computed expectations. | REQ-007 |
| AC-010 | Given a narrative containing a number not present in the insight set or result, when grounding-validated, then it is rejected with the offending number named; given a narrative using "because"/"caused by", then a causal-language flag is raised. | REQ-008 |
| AC-011 | Given a result from a dataset flagged synthetic, or with fewer rows than the declared minimum, or a partial final period, when a response is built, then the matching caveat appears in the response. | REQ-008 |
| AC-012 | Given an answered question, when the chat response is built, then it contains headline, insights, chart spec, Vega-Lite JSON that validates against the declared minimal schema, Markdown-table fallback, plan echo, caveats, and citations naming metric owners and as-of. | REQ-009 |
| AC-013 | Given a write-back request against an undeclared target, or with a column outside the contract, or targeting a table declared as a source/fact table, when processed, then it is rejected before the writer is called. | REQ-010, NFR-003 |
| AC-014 | Given a valid write-back request, when run with default settings, then it is a dry run that returns the exact records it would write (with all provenance fields) and the writer is not called; when the same request is committed twice, then the second commit writes zero new records (idempotent on key). | REQ-010 |
| AC-015 | Given a committed write without approval on a target not declared `auto_approve`, then it is rejected; given an approved committed write, when reversed by its run id, then the injected writer receives a reversal for exactly that run's records. | REQ-011 |
| AC-016 | Given persisted insights for two prior days and a question "what changed since yesterday", when answered as-of today, then the comparison uses yesterday's persisted insight, ignores any record created after the as-of, and leaves the store unchanged. | REQ-012, NFR-002 |
| AC-017 | Given any answered request, when its `0070` envelope is replayed, then the replayed plan, result hash, chart spec, and insight set are byte-identical to the original. | REQ-013, NFR-001 |
| AC-018 | Given the repository, when the agent-contract and catalog gates run, then `agents/analytics/data_visualization/` and `agents/analytics/nl_analytics/` each have `prompt.md`, `README.md`, `instructions.md`, `tasks.md`, a `Spec-Driven Role` section, and a catalog row. | REQ-014 |
| AC-019 | Given the runtime package, when its imports and source are scanned, then it imports only the standard library and in-repo modules, and contains no connection string, credential, or network call. | NFR-003 |
| AC-020 | Given a request against a dataset classified `contains_pii`, when audit events are emitted, then they contain hashes and redacted text only, and an LLM adapter request built for it carries `contains_pii: true`. | NFR-004 |
| AC-021 | Given 100,000 synthetic fact rows, when the deterministic path runs end-to-end, then it completes in under 2 s (benchmark test, skipped in CI with a recorded reason if the runner is under-provisioned). | NFR-005 |
| AC-023 | Given a rates dataset tagged `fixed_income_rates` and a yield moving from 4.00% to 4.20%, when answered, then the change is reported as +20 bp (not +5%), and a question about `var` under `market_risk` produces no contributor insight and no cross-desk sum. | REQ-015 |
| AC-024 | Given a dataset tagged `equities` and `fx` and the question "vol by pair", when interpreted, then the response is `clarification_needed` naming both candidate metrics. | REQ-015, REQ-002 |
| AC-025 | Given only `draft` packs applied, when answered, then the unreviewed caveat names each pack and a write-back request is rejected with that reason; with all applied packs `reviewed`, the same write-back proceeds to its normal checks. | REQ-016 |
| AC-026 | Given a dataset whose tags select no pack, when answered, then the response states generic behavior was used; given any pack, the set of permitted insights is a subset of the generic set. | REQ-017 |
| AC-027 | Given packs resolved from the bundle and a question that applies one, when answered, then the response citations and the envelope's answer payload name the source kind, package version, and catalog hash; given domain tags with no pack catalog supplied, then `answer()` raises. | REQ-018 |
| AC-028 | Given QuantMeridian's own `settings/llm_profiles.json` example (copied as a test fixture) and local stub servers speaking the Anthropic Messages and OpenAI chat-completions APIs, when a profile is selected by name, by `default_profile_env`, or by `default_profile`, then the backend sends the configured model and prompt to the endpoint named by `base_url_env` (or the provider default), with the auth scheme and `header_envs` applied, returns the completion text, and records profile, `api_style`, model, and reported usage; a profile whose `uses` omits the role is not used for it; a transport failure falls through to `fallback_profile`; an `api_style: none` profile yields the keyword interpreter and template narrator; a file that fails `llm-profiles/1` validation, an unknown or disabled profile, or a missing environment variable fails with a typed, readable error; no credential appears in any envelope, log, exception, or `repr`; and the AC-019 scan of `src/quantsmith/nl_analytics/` still passes. | REQ-019, NFR-003 |
| AC-029 | Given a stub completion callable returning (a) a valid plan, (b) malformed JSON, and (c) a plan naming an undeclared dimension, when interpreted, then (a) executes and (b) and (c) return `clarification_needed` with the reason and no execution; given a narrator returning a number absent from the insight set, then the response uses the template narrative and carries the fallback caveat. | REQ-020, REQ-008 |
| AC-030 | Given the Console analytics route and a viewer at `internal` clearance, when they ask about a `restricted` metric, then the answer is indistinguishable from a nonexistent metric (as in AC-005); when they ask a permitted question, then the page payload carries the chart, insights, plan echo, caveats, and citations; and the server's default bind address is localhost. | REQ-021, REQ-004 |
| AC-031 | Given a publish request that opts in to a knowledge candidate, when it is committed with every applied pack `reviewed`, then exactly one candidate is created with the required citations and a review status; when it is a dry run, then the would-be candidate is returned and nothing is created; when a pack is unreviewed or the write is refused, then no candidate is created and the reason is stated. | REQ-022, REQ-016 |
| AC-032 | Given committed writes, then each records the approver handle; given a target declaring `approver_roles`, then an approver without the role, or any approval while the roster is empty, returns `write_rejected` with the reason before the writer is called; given `require_distinct_approver`, then an approver equal to the author is rejected. | REQ-023, REQ-011 |
| AC-022 | Given each failure path (clarification, masked, empty result, stale data, write rejected), when a response is returned, then it carries a typed status and a non-empty reason, and no chart spec is attached to a non-answer. | NFR-006 |

## Data & Dependencies

- **Governed metrics:** `0008` `SemanticLayer` and its registry — the only
  vocabulary a plan may use. Synonyms for the baseline interpreter are declared
  alongside metric definitions, owned by the metric owner.
- **Fact rows:** supplied by a caller-injected read-only executor following
  `adapters/data_access/sql.md` (parameterized, read-only, query hash captured).
  The SDK never opens a connection.
- **Access:** `0058` `access_control` clearance resolution and
  `access_level_allows`.
- **Domain knowledge:** `0081` analytics domain packs
  (`knowledge/analytics_packs/`, `analytics_packs.select_packs`,
  `can_sum`, `suppressed_insights`), selected by `sources/*.yml` domain tags.
- **Charts:** `dashboard_spec.CHART_TYPES` and `Panel` (`0014`/`0047`);
  renderers `0015`–`0018` downstream.
- **Narrative:** `instructions/data_storytelling.md` (situation → insight →
  action) and `data_storytelling` agent; optional LLM via
  `adapters/llm_runtime/`.
- **Audit/replay:** `0070` orchestration envelope and replay engine.
- **Provenance:** `0025` data-provenance guardrail and synthetic-data
  disclosure for any example data.
- **Write-back target:** declared in a committed write-back contract
  (`templates/data/writeback_contract.md`). The first supported target is
  SQLite through standard-library `sqlite3` against a local, gitignored file
  (resolved 2026-09-24). Shared databases, their credentials, and their
  drivers stay adopter-owned.
- No private data, credentials, or real company data enter this repository;
  example data is synthetic and disclosed.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The interpreter confidently maps a question to the wrong metric. | A plausible, wrong answer. | Plan echo in every response; clarification over guessing on ambiguity (REQ-002); governed vocabulary only (REQ-001). |
| RISK-002 | An LLM narrative states a number the computation did not produce. | Fabricated figures reach decisions. | Grounding validator rejects unbacked numbers (REQ-008, AC-010); template fallback. |
| RISK-003 | Natural language becomes a path around access control. | Restricted data disclosed. | Clearance check before execution plus existence masking (REQ-004, AC-005). |
| RISK-004 | Write-back becomes an unreviewed side channel into a production database. | Corrupted or unauthorized data; hard rollback. | Declared targets only, append-only, dry-run default, approval, idempotency, reversal by run id (REQ-010/011); source tables unwritable (AC-013). |
| RISK-005 | Chart choice misleads (truncated axes, pies for many categories, dual axes). | Wrong impression from correct numbers. | Declared form rule, sorted bars, zero-based bar axes, no pie/dual-axis types (REQ-006). |
| RISK-006 | Day-over-day comparisons pick up a record written after the as-of. | Look-ahead in "what changed" answers. | Prior-insight lookup bounded by as-of (REQ-012, AC-016). |
| RISK-007 | Insight language implies causation. | Overconfident decisions. | Causal-language flag (AC-010); contribution is presented as decomposition, not cause. |
| RISK-008 | Scope creep toward a general BI chatbot. | Unreviewable breadth. | Non-Goals; plan vocabulary bounded by the registry. |

## Assumptions & Open Questions

- Assumption: the `0008` additive-measure assumption holds for contribution
  decomposition; non-additive metrics get level/trend insights only, with that
  limit stated in the response.
- Assumption: a question maps to one metric per plan in the first slice;
  multi-metric questions beyond a two-measure scatter return a clarification.
- Resolved (owner, 2026-09-24): the first write-back target is **SQLite** via
  the standard-library `sqlite3` module — a local file matched by the
  existing `*.db`/`*.sqlite`/`*.sqlite3` `.gitignore` patterns, never
  committed. It needs no driver, credential, or network, so it serves the
  reference example, the tests, and single-user local use. It is not a shared
  team store. A shared target (Postgres or SQL Server, which already have
  `SQLDataSource` classes in `quant/agentic_quant/sql_data.py`, or a
  warehouse) is deferred until a team needs one; the contract stays
  target-neutral so that adapter plugs in without changing callers.
- Resolved (owner, 2026-10-07): the first surface is the **`0057` Knowledge
  Console**, backed by language-model **APIs**, not Claude Code — the
  environments that will run this have API access to models but no Claude
  Code. The available endpoints are self-hosted / OpenAI-compatible and
  another gateway (REQ-019–REQ-021). The CLI stays for scripts. Slack is out
  of scope: two-way chat there needs a hosted bot; it may later *receive*
  published insights through `adapters/alert_delivery/`.
- Resolved (owner, 2026-10-07): persisted insights become `0048` knowledge
  candidates **only on opt-in per publish**, never automatically, and only
  from committed writes whose packs are all reviewed (REQ-022). Insights are
  point-in-time numbers; promoting every write would flood review with
  values that go stale.
- Resolved (owner, 2026-10-07): approval is **per-request confirmation plus
  a named approver** — the approver's handle is recorded, and a target may
  require approver roles from the roster and a second person (REQ-023).
  Today's anonymous yes/no gave no record of who approved.
- Resolved (owner, 2026-10-07): the gateway is left open on purpose — "as
  flexible as possible". No provider is assumed; the backend is a configured
  profile, with shipped backends for OpenAI-compatible endpoints, the
  Anthropic API, a declared generic HTTP/JSON shape, and an import-path
  callable for SDK-based providers (REQ-019).
- Resolved (owner, 2026-10-07, refining the above): the profile format is
  QuantMeridian's existing `llm-profiles/1`
  (`contracts/agent/llm-profiles.schema.json` there), read unchanged, so
  QuantMeridian's spec009 agent worker and QuantSmith share one
  `settings/llm_profiles.json`. Its `anthropic_messages` and
  `openai_chat_completions` styles cover direct providers, self-hosted
  servers, and OpenAI-compatible gateways. The generic HTTP/JSON shape,
  import-path callable, and token-command credential become a proposed
  additive `llm-profiles` revision in QuantMeridian; `llm-profiles/1` rejects
  unknown fields, so adding them only here would split the format.

## Exceptions

None.
