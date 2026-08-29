# Plan: Morning Market Brief

- **Spec:** 0059-morning-market-brief (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-22

## Approach

One new module, `src/quantsmith/pipelines/market_brief.py`, standard
library only. Three concrete providers behind one shared `CommentaryItem`
contract — the same shape `adapters/alert_delivery/` uses (one contract,
one file/function per provider) — rather than a speculative
plugin-discovery framework. Everything else is composition: `sources/*.yml`
for credentials, `research.py`'s existing `ResearchItem` field names for
forward compatibility with `0056`, `0055`'s existing scheduling registry,
and `adapters/alert_delivery/email.py` for delivery, none of which are
modified.

## Architecture & Components

```text
market_brief.py
  CommentaryItem  -- title, description, url, source_name, provider,
                     published_at (datetime, tz-aware), matched_topics (tuple),
                     sentiment_score/label (Alpha Vantage only), relevance_score

  normalize_newsapi_response(raw, topic)        REQ-002
  normalize_alpha_vantage_response(raw, topic)  REQ-002
      per-ticker sentiment preferred over the article's overall figure
      when a ticker_sentiment[] entry matches the requested topic
  normalize_finnhub_response(raw, topic)        REQ-002

  fetch_commentary(fetch_fns, topics, *, lookback_hours, now)  REQ-003
      fetch_fns: Mapping[provider_name, FetchFn] -- caller-injected, no
      network call in this module. Dispatches to the matching normalize_*,
      filters to now - lookback_hours, dedupes by url ACROSS providers
      (merges matched_topics on collision), sorted (published_at, url) desc.

  top_headlines(items, *, max_per_topic)   REQ-004
      groups by matched_topics, truncates most-recent-first per group.

  sentiment_rollup(items, *, min_relevance=0.0)   REQ-005
      mean sentiment_score per topic, Alpha Vantage items only; an item
      below min_relevance or with no score contributes nothing -- absence,
      never a coerced 0.0.

  render_morning_brief(as_of, headlines_by_topic, sentiment,
                        analysis_markdown, *, watchlist, providers_used)  REQ-006
      pure formatter into templates/docs/morning_market_brief.md's shape;
      analysis_markdown is opaque caller-supplied text, never generated here.

  candidates_from_brief(as_of, headlines_by_topic, analysis_markdown,
                         *, source_run, access_level, entitlement_class)  REQ-007
      ResearchItem-shaped dict(s): source_type="generated",
      review_status="pending_review", citation built only from real
      supplied URLs. One candidate per run (see spec.md Assumptions);
      returns [] given no headlines. Proposes only -- does not stage
      (mirrors ingestion_data_contract.candidates_from_validation).

  stage_research_candidates(candidates, *, root, source_run)   REQ-008
      writes <root>/inbox/morning_brief/<source_run>.yaml -- mirrors
      workflow_memory's memory/inbox/<workflow>/<source_run>.yaml shape,
      rooted under a caller-specified, LOCAL-ONLY directory (never
      research/ or memory/). Raises given empty candidates.
```

No `promote_*` function — see spec.md's Non-Goals. Staging to a
human-readable local YAML file *is* the v1 review step.

## Interfaces & Data Contracts

`candidates_from_brief`'s output dict uses `research.ResearchItem`'s exact
field names (`id`, `title`, `source_type`, `author_or_publisher`,
`asset_class`, `strategy_theme`, `access_level`, `entitlement_class`,
`publication_date`, `ingestion_date`, `review_status`, `freshness_days`,
`summary`, `citation`) so a future promotion step can construct a
`ResearchItem` (or write into `research.py`'s YAML shape) without a field
mapping layer in between.

`fetch_fns: Mapping[str, Callable[[str], object]]`, keyed by a name in
`PROVIDERS = ("newsapi", "alpha_vantage", "finnhub")` — matches the
`source_id` convention `sources/*.yml` already uses, minus the `_news`
suffix those files carry for catalog-naming clarity.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P9 Security and data handling | yes | No credential or network call lives in this repository's code; `fetch_fn` is always caller-injected, `credential_ref` is always a pointer. Real generated content is never committed — staged only under a caller-specified local root. |
| P10 Honest reporting | yes | Sentiment absence stays absence (REQ-005); `render_morning_brief` never fabricates the analysis section it composes; a topic with no coverage is named, not dropped (agent instructions). |
| P4 Correct by construction | yes | Cross-provider dedupe and the lookback filter are structural (a set-keyed merge and a comparison), not an assertion layered on top. |
| P5 Reversibility | yes | Additive module; no existing file modified except catalog/doc cross-references and `.gitignore`. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `sources/{newsapi,alpha_vantage_news,finnhub_news}.yml`, `sources/README.md` | T-002 |
| REQ-002 | `normalize_newsapi_response`, `normalize_alpha_vantage_response`, `normalize_finnhub_response` | T-001 |
| REQ-003 | `fetch_commentary` | T-001 |
| REQ-004 | `top_headlines` | T-001 |
| REQ-005 | `sentiment_rollup` | T-001 |
| REQ-006 | `render_morning_brief`, `templates/docs/morning_market_brief.md` | T-001, T-003 |
| REQ-007 | `candidates_from_brief` | T-001 |
| REQ-008 | `stage_research_candidates` | T-001 |
| REQ-009 | `templates/data/morning_brief_config.yml`, `.gitignore` | T-003 |
| REQ-010 | `agents/economists/morning_brief_writer/` | T-004 |
| REQ-011 | `specs/README.md`, root `README.md`, `agents/README.md`, `agents/economists/README.md`, `specs/0056-.../spec.md` | T-005 |
| NFR-001, NFR-002, NFR-003, NFR-004 | Pure functions, stdlib only, caller-injected fetch, local-only staging root | T-001, T-002 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Provider architecture | Three concrete providers, one shared contract + one `normalize_*` each | A generic provider-plugin registry | Three real instantiations justify a shared shape now (same reasoning `adapters/alert_delivery/` already applies with seven providers); a discovery mechanism for providers that don't exist yet is speculative. |
| Sentiment source | Alpha Vantage only; other providers contribute no score | Infer a sentiment score from headline text (keyword/NLP heuristic) | A hand-rolled sentiment heuristic in a dependency-free module would be a worse, unstated model competing with a real provider's; better to have real coverage for one provider and honestly absent coverage elsewhere than a fabricated signal everywhere. |
| Candidate granularity | One candidate per run | One candidate per topic | The agent writes one coherent analysis, not independently-authored per-topic pieces; splitting it would fabricate structure the agent never actually produced. |
| Staging destination | A caller-specified local root (default `research_local/`), never `research/` | Stage directly into `research/market_research/index.yaml` | `research/` is explicitly fictional-only per spec `0056`'s Non-Goals; writing real content there would violate the one boundary that spec draws hardest. |
| Promotion mechanics | Not built | Build a `promote_research()` mirroring `0049`'s `promote()` | `0056` has no REQ describing promotion (id assignment, supersession, review-state transition) the way `0048` did before `0049` existed — building it now would be inventing a contract `0056` itself hasn't specified. |

## Validation Strategy

`tests/test_market_brief.py`, one test per acceptance criterion
(AC-001–AC-013), using canned raw response fixtures shaped like each
provider's real payload (`_newsapi_raw`, `_alpha_vantage_raw`,
`_finnhub_raw`) — no network call anywhere in the suite. AC-014–AC-017 are
direct inspection (gate output, `.gitignore` contents, catalog rows), the
same pattern spec `0045`'s AC-011 uses for its three catalogs. Then the
full documentation gate set (`spec`, `docs-link`, `spec-index`,
`readme-sync`, `doc-counts`, `agent-catalog`, `source-catalog`), the full
`pytest tests/ -q`, and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit and push; no migration, no existing module
modified beyond catalog/doc cross-references. Rollback is reverting the
commit. Nothing in this repository invokes `market_brief.py` on a schedule
by itself — the worked `ScheduleJob` example
(`specs/0059-morning-market-brief/schedule_registry.md`) documents how an
adopter wires a real `handlers` callable and their own `fetch_fn`
implementations; until an adopter does that, this spec ships tested,
composable functions, not a running pipeline.

## Open Questions

- Carried from `spec.md`: promotion mechanics for a future "`0056` write
  path" spec.
- Carried from `spec.md`: whether `morning_brief_config.yml` should ever
  name a provider ahead of its `normalize_*` implementation.
