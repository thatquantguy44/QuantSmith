# Spec: Morning Market Brief

- **ID:** 0059-morning-market-brief
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-22

## Problem & Context

The user wants a scheduled pipeline that pulls free-API market commentary,
generates a personal morning brief, delivers it to them, and stages the
output into the knowledge base for review before it becomes durable
research. Two questions had to be answered before writing code: **where do
API credentials live so this is configurable for anyone who clones the
repo**, and **which store does generated commentary belong in**.

The first is already solved. `sources/*.yml` (spec `0027`) is a committed,
public catalog where `connection.credential_ref` is a pointer name, never a
secret — `sources/fred.yml:31`: `credential_ref: "FRED_API_KEY"   # free
registration; still a pointer, not the key itself`.
`agents/secrets_management/credential_access/` resolves that pointer from
the environment at runtime. Every clone sets its own environment variables;
nothing about a key ever enters git. This spec's only change here is
**adding three more entries** to that existing catalog.

The second question changes the design. Generated market commentary does
not fit `0048`'s memory-record vocabulary
(`schema`/`quirk`/`pattern`/`pitfall`/`decision`/`metric`/`performance` — all
about *dataset* behavior, not market views). It fits `0056`
(market-research-knowledge-base, Draft, spec-only) instead, which already
names this exact flow: its own requirement to "generate memory or knowledge
candidates from scheduled reports... only after reviewable provenance is
available," its risk that "generated summaries become treated as primary
research... preserve as a derived source type with citations," and its own
acceptance criterion that "scheduled research reports... candidates...
enter review instead of being auto-promoted." `0056` also states plainly
that real content must never be committed to this repository — its own
`research/` directory holds only fictional reference data.

This spec is therefore the first real runtime slice of that part of `0056`,
not a rebuild of `0056` (entitlement enforcement, the email
connector, MCP exposure, and audit logging stay `0056`'s own unbuilt scope),
composed with several already-built pieces: `0055`'s scheduling registry and
`agentic_workflow` target type, `adapters/alert_delivery/email.py`, the
`credential_access` agent, and `research.py`'s already-real `ResearchItem`
schema and `load_research_store` loader.

Three providers were chosen deliberately, not one: **NewsAPI.org** (broad
general-news search, free "Developer" tier — 100 req/day, ToS-restricted to
non-commercial/local-development use, articles ~24h delayed), **Alpha
Vantage `NEWS_SENTIMENT`** (ticker-tagged headlines with a machine-readable
sentiment score — the one provider giving this pipeline something
genuinely deterministic to compute), and **Finnhub** company/market news
(ticker-scoped headlines, no sentiment). Each free-tier caveat is disclosed
in its own `sources/*.yml` entry, not hidden.

## Goals

- Add `sources/{newsapi,alpha_vantage_news,finnhub_news}.yml` and matching
  `adapters/data_access/external_apis/*.md` profiles, so each provider's
  credential is configurable per-clone via an environment variable, never
  committed.
- Add `src/quantsmith/pipelines/market_brief.py`: normalize each provider's
  raw response into one shared `CommentaryItem` shape, fetch and merge
  across providers with recency filtering and cross-provider dedupe,
  compute a deterministic sentiment rollup from Alpha Vantage coverage
  only, and render `templates/docs/morning_market_brief.md`'s shape from
  computed data plus a caller-supplied analysis text.
- Propose and stage a `research.ResearchItem`-shaped, `pending_review`
  candidate from a rendered brief, written to a **local-only, gitignored**
  root — never the committed `research/` reference store.
- Add `templates/data/morning_brief_config.yml`: a local-only
  personalization template (watchlist, enabled providers, delivery route,
  staging root, schedule) following the exact pattern
  `role_context.yml`/`knowledge_sources.yml`/`model_plugins.yml` already
  establish.
- Add `agents/economists/morning_brief_writer/`: an agent contract (no
  runtime code, matching every other `agents/economists/*` agent) that
  writes the "Views & Analysis" section, grounded only in the headlines and
  sentiment rollup it's actually handed.
- Add a worked `ScheduleJob` example wiring the above into `0055`'s
  existing registry and `dispatch_job`'s `agentic_workflow` target type.

## Non-Goals

- **No live network call inside this repository's tested code.** Every
  provider's fetch is a caller-injected function; this SDK holds no API
  traffic and no credential, the same P9 boundary `fred_point_in_time.py`
  and `credential_access` already draw.
- **No MCP or knowledge-graph exposure.** Items 17 / specs `0052`–`0054`
  remain unbuilt; this spec produces candidates in a shape those servers
  will eventually need to expose, but does not build them.
- **No promotion into a live, queryable research index.** `0056` has no REQ
  describing promotion mechanics (id assignment, supersession, review-state
  transition) the way `0048` did before `0049` built `promote()`. This spec
  stages a local file for human review; a future "`0056` write path" spec
  owns promotion.
- **No entitlement enforcement, secret/PII/MNPI quarantine, audit logging,
  or email connector for the research store.** All remain `0056`'s own
  stated gaps (its access-control, quarantine, audit-logging, and
  email-scanning requirements); not claimed here.
- **No fourth commentary provider or plugin-discovery mechanism.** Three
  concrete providers justify the shared `CommentaryItem` contract and
  per-provider `normalize_*` pattern used here; a fifth is a drop-in
  extension later, not pre-built or abstracted further now.
- **No scheduling code changes.** `0055`'s registry, `dispatch_job`, and
  its `handlers` extension point already support an `agentic_workflow`
  target; this spec adds a worked example, not new scheduling mechanics.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | Register `newsapi`, `alpha_vantage_news`, and `finnhub_news` in `sources/*.yml`, each with a `credential_ref` naming an environment variable, never a secret value, and each listed in `sources/README.md`. | must |
| REQ-002 | Normalize each provider's raw response shape into a shared `CommentaryItem` dataclass via one `normalize_*` function per provider. | must |
| REQ-003 | `fetch_commentary` shall exclude items published before a caller-supplied lookback cutoff and deduplicate by URL *across* providers, merging matched topics rather than duplicating the item; an unrecognised provider name shall raise. | must |
| REQ-004 | `top_headlines` shall group items by matched topic and truncate each group to a caller-supplied maximum, most-recent-first. | must |
| REQ-005 | `sentiment_rollup` shall compute mean sentiment per topic from items carrying a sentiment score only (Alpha Vantage), optionally filtered by a minimum relevance score; a topic with no scored coverage shall be absent from the result, never present at zero. | must |
| REQ-006 | `render_morning_brief` shall compose the computed headlines and sentiment rollup with a caller-supplied `analysis_markdown` string into `templates/docs/morning_market_brief.md`'s shape; it shall never generate analysis text itself. | must |
| REQ-007 | `candidates_from_brief` shall propose exactly one `research.ResearchItem`-shaped candidate per run with `source_type="generated"` and `review_status="pending_review"`, citing only the real headline URLs it was built from; given no headlines, it shall return an empty list. | must |
| REQ-008 | `stage_research_candidates` shall write proposed candidates to `<root>/inbox/morning_brief/<source_run>.yaml` under a caller-specified root; it shall never write into the committed `research/` directory, and shall raise given no candidates. | must |
| REQ-009 | Add `templates/data/morning_brief_config.yml`, resolved env-var-first then repo-root-local, gitignored at the real-file path, following the exact pattern `role_context.yml` establishes. | must |
| REQ-010 | Add `agents/economists/morning_brief_writer/` as a complete agent contract (`README.md`, `instructions.md`, `prompt.md`, `tasks.md`) writing only the Views & Analysis section, every claim traced to a supplied headline or the sentiment rollup. | must |
| REQ-011 | `specs/README.md`, root `README.md`, `agents/README.md`, `agents/economists/README.md`, and `specs/0056-market-research-knowledge-base/spec.md` shall reference spec `0059`. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Dependency isolation | Standard library only (`dataclasses`, `datetime`, `pathlib`); no new dependency. |
| NFR-002 | No network in this repo | Every provider fetch is a caller-injected callable; no HTTP call is made by code in `src/quantsmith/pipelines/market_brief.py` or its tests. |
| NFR-003 | Determinism | The same raw inputs and the same arguments always produce the same `CommentaryItem` ordering, rollup, and rendered text. |
| NFR-004 | No committed real content | Staged candidates are written only under a caller-specified, gitignored local root; nothing in this spec writes to `research/`. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a raw NewsAPI, Alpha Vantage, and Finnhub response each, when the matching `normalize_*` runs, then each returns typed `CommentaryItem`s with the right provider tag, and Alpha Vantage's ticker-specific sentiment (not the overall figure) is used when a ticker match exists. | REQ-002 |
| AC-002 | Given an item published before `now - lookback_hours`, when `fetch_commentary` runs, then it is excluded. | REQ-003 |
| AC-003 | Given the same URL returned by two providers, when `fetch_commentary` runs, then it appears once with `matched_topics` merged from both. | REQ-003 |
| AC-004 | Given items across recency, when `top_headlines` runs with a max count, then each topic's list is truncated, most-recent-first. | REQ-004 |
| AC-005 | Given Alpha Vantage items with sentiment and NewsAPI/Finnhub items without, when `sentiment_rollup` runs, then only Alpha-Vantage-covered topics appear, with the correct mean. | REQ-005 |
| AC-006 | Given an item whose `relevance_score` is below a caller-supplied floor, when `sentiment_rollup` runs with that floor, then it is excluded from the rollup. | REQ-005 |
| AC-007 | Given headlines, a rollup, and a supplied analysis string, when `render_morning_brief` runs, then the rendered text contains the supplied analysis verbatim and never text this function generated itself. | REQ-006 |
| AC-008 | Given an empty headline set, when `candidates_from_brief` runs, then it returns an empty list. | REQ-007 |
| AC-009 | Given real headlines, when `candidates_from_brief` runs, then it returns exactly one candidate with `review_status="pending_review"` and every citation traceable to a supplied URL. | REQ-007 |
| AC-010 | Given a candidate and a root path, when `stage_research_candidates` runs, then a YAML file is written at `<root>/inbox/morning_brief/<source_run>.yaml` and nowhere else. | REQ-008 |
| AC-011 | Given an unrecognised provider name, when `fetch_commentary` runs, then it raises `MarketBriefError` naming the provider. | REQ-003 |
| AC-012 | Given no candidates, when `stage_research_candidates` runs, then it raises `MarketBriefError`. | REQ-008 |
| AC-013 | Given the same raw inputs, when `fetch_commentary` runs twice, then the resulting order is identical both times. | NFR-003 |
| AC-014 | Given the three new `sources/*.yml` entries, when the `source-catalog` gate runs, then every required field is declared and each is listed in `sources/README.md`. | REQ-001 |
| AC-015 | Given `templates/data/morning_brief_config.yml` and `.gitignore`, when inspected, then the template is committed and the real `morning_brief_config.yml`/`.yaml` path is ignored. | REQ-009 |
| AC-016 | Given `agents/economists/morning_brief_writer/`, when the `agent-catalog` gate runs, then it is recognized as a complete public agent. | REQ-010 |
| AC-017 | Given the five catalogs/cross-references named in REQ-011, when inspected, then each lists spec `0059`. | REQ-011 |

## Data & Dependencies

- **Reads (via caller-injected `fetch_fn`, never directly):** NewsAPI
  `/v2/everything`, Alpha Vantage `NEWS_SENTIMENT`, Finnhub
  `/company-news`/`/news` — registered in `sources/{newsapi,
  alpha_vantage_news,finnhub_news}.yml`.
- **Reads:** `morning_brief_config.yml` (local-only, not read by this
  module directly — the scheduling handler that composes these functions
  reads it and passes the resulting arguments).
- **Writes:** `<research_staging.root>/inbox/morning_brief/<source_run>.yaml`
  — local-only, never `research/`.
- **Consumed by:** the worked `ScheduleJob` example
  (`specs/0059-morning-market-brief/schedule_registry.md`), which composes
  this module's functions with `agents/economists/morning_brief_writer/`
  and `adapters/alert_delivery/email.py`.
- Standard library only; no new dependency.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A caller's `fetch_fn` returns a shape this module's `normalize_*` functions don't expect (a provider API change), silently producing zero or malformed items. | Medium — a quiet, empty-looking brief rather than a visible failure. | Each `normalize_*` reads defensively (`.get(...)` with defaults) and skips an item it cannot parse a date for, rather than raising mid-batch; the adapter profile docs quote the expected shape so a drift is visible in review, the same pattern `fred_point_in_time.py` uses for its upstream table. |
| RISK-002 | Real, personal market-research content is accidentally committed (e.g. `research_staging.root` misconfigured to point inside a tracked directory). | High — exactly the leak `0056`'s Non-Goals exist to prevent. | `.gitignore` adds `/research_local/` (the packaged default root) and `stage_research_candidates` never writes to a path it invents itself — it writes exactly where the caller points it, so the caller's own `.gitignore` hygiene is the enforcement point, stated plainly in this module's docstring. |
| RISK-003 | Sentiment from one provider's model is read as a verified market fact rather than a signal. | Medium — overconfident downstream decisions. | `sentiment_rollup`'s absence-not-zero rule, the adapter profile's explicit caveat, and `morning_brief_writer`'s own instructions all state the same thing: a score is the provider's model output, not a fact. |
| RISK-004 | The generated analysis is later treated as primary research rather than a draft. | Medium — the exact failure `0056`'s RISK-004 names. | `candidates_from_brief` always sets `review_status="pending_review"`, never `approved`; nothing in this spec promotes it further. |

## Assumptions & Open Questions

- Assumption: NewsAPI's, Alpha Vantage's, and Finnhub's free-tier response
  shapes (quoted in the three adapter profile docs) are stable enough to
  normalize against; a provider's breaking API change is RISK-001's
  concern, not grounds to redesign the shared `CommentaryItem` contract.
- Assumption: one candidate per run (not one per topic) is the right
  granularity — the agent writes one coherent analysis, not independent
  per-topic pieces, so proposing one candidate matches what was actually
  produced.
- Open question, carried from `0056`: when a future "`0056` write path"
  spec builds real promotion mechanics, does a staged `morning_brief`
  candidate promote directly, or does it require the same kind of review
  gate `0049` built for `0048` (a pull request against a private
  research repository, analogous to `memory/inbox/`)?
- Open question: should `morning_brief_config.yml` support a fourth
  provider's config shape before that provider's `normalize_*` function
  exists, or should the config and the code stay in lockstep (current
  choice — the config only names providers `market_brief.py` actually
  implements)?

## Exceptions

None. This spec adds a new pipeline module, a new agent contract, and
catalog entries to already-established patterns; it introduces no deviation
from `instructions/engineering_principles.md`.
