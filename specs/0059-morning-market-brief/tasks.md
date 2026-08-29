# Tasks: Morning Market Brief

- **Spec:** 0059-morning-market-brief (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-22

## Definition of Done (applies to every task)

- Standard library only; no new dependency.
- No network call anywhere in `src/quantsmith/pipelines/market_brief.py` or
  its tests — every provider fetch is caller-injected.
- No credential value anywhere in this repository — `sources/*.yml`'s
  `credential_ref` always names an environment variable.
- No real generated research content committed — staging targets a
  caller-specified, gitignored local root only, never `research/`.
- Deterministic: the same inputs always produce the same result.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Write `CommentaryItem`, `normalize_newsapi_response`, `normalize_alpha_vantage_response`, `normalize_finnhub_response`, `fetch_commentary`, `top_headlines`, `sentiment_rollup`, `render_morning_brief`, `candidates_from_brief`, `stage_research_candidates`. | REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, NFR-001, NFR-002, NFR-003, NFR-004 | done | `src/quantsmith/pipelines/market_brief.py`. Ticker-specific sentiment preferred over an article's overall figure; absence-not-zero for unscored topics; cross-provider dedupe merges `matched_topics`. |
| T-002 | Register the three providers in the source catalog. | REQ-001 | done | `sources/{newsapi,alpha_vantage_news,finnhub_news}.yml`, `sources/README.md`, `adapters/data_access/external_apis/{newsapi,alpha_vantage_news,finnhub_news}.md`, `adapters/data_access/external_apis/README.md`. |
| T-003 | Write `tests/test_market_brief.py`, the report template, and the personalization config. | REQ-006, REQ-009 | done | One test per AC-001–AC-013 (`_newsapi_raw`/`_alpha_vantage_raw`/`_finnhub_raw` fixtures, no network); `templates/docs/morning_market_brief.md`; `templates/data/morning_brief_config.yml`; `.gitignore` entries for `morning_brief_config.yml`/`.yaml` and `/research_local/` (also fixed a pre-existing gap: `identity.yml`/`.env` were referenced as gitignored elsewhere but missing from `.gitignore` until now). |
| T-004 | Write the `morning_brief_writer` agent contract and the worked scheduling example. | REQ-010 | done | `agents/economists/morning_brief_writer/{README,instructions,prompt,tasks}.md`; `specs/0059-morning-market-brief/schedule_registry.md` (a worked `0055` registry entry — no scheduling code changed). |
| T-005 | Wire catalogs and cross-references. | REQ-011 | done | `specs/README.md`, root `README.md`, `agents/README.md`, `agents/economists/README.md`, `specs/0056-market-research-knowledge-base/spec.md`. |
| T-006 | Run validation gates. | NFR-001, NFR-002, NFR-003, NFR-004 | done | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`, `agent-catalog`, `source-catalog`; `pytest tests/ -q`; `git diff --check`. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Test(s) | Status |
| --- | --- | --- |
| AC-001 | `test_normalize_all_three_providers_AC_001` | done |
| AC-002 | `test_fetch_commentary_excludes_items_before_lookback_cutoff_AC_002` | done |
| AC-003 | `test_fetch_commentary_dedupes_and_merges_topics_across_providers_AC_003` | done |
| AC-004 | `test_top_headlines_truncates_most_recent_first_per_topic_AC_004` | done |
| AC-005 | `test_sentiment_rollup_only_covers_alpha_vantage_topics_AC_005` | done |
| AC-006 | `test_sentiment_rollup_filters_below_min_relevance_AC_006` | done |
| AC-007 | `test_render_morning_brief_never_fabricates_analysis_AC_007` | done |
| AC-008 | `test_candidates_from_brief_empty_headlines_proposes_nothing_AC_008` | done |
| AC-009 | `test_candidates_from_brief_builds_one_pending_review_candidate_AC_009` | done |
| AC-010 | `test_stage_research_candidates_writes_local_inbox_file_AC_010` | done |
| AC-011 | `test_fetch_commentary_unknown_provider_raises_AC_011` | done |
| AC-012 | `test_stage_research_candidates_empty_raises_AC_012` | done |
| AC-013 | `test_deterministic_AC_013` | done |
| AC-014 | `hooks/stages/source-catalog-check.sh` against the three new entries | done |
| AC-015 | Direct inspection of `templates/data/morning_brief_config.yml` and `.gitignore` | done |
| AC-016 | `hooks/stages/agent-catalog-check.sh` against `morning_brief_writer/` | done |
| AC-017 | Direct inspection of the five cross-referenced catalogs/docs | done |

## Follow-ups

- A future "`0056` write path" spec: real promotion mechanics (id
  assignment, supersession, review-state transition) for a staged
  candidate — this spec deliberately stops at staging (carried as an open
  question in `spec.md`).
- MCP exposure of staged/promoted market research (items 17, specs
  `0052`–`0054`) — unbuilt; out of scope here.
- A fourth commentary provider, once a concrete need exists — the
  `normalize_*`/`PROVIDERS` pattern makes this a drop-in addition.
