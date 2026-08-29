"""Tests for spec 0059 -- morning market brief.

One test per acceptance criterion. Every fixture is a canned raw response
shape (no network) -- ``fetch_fns`` in the module under test is always
caller-injected, so tests never make a real HTTP call.
"""

from __future__ import annotations

import datetime

import pytest

from quantsmith.pipelines.market_brief import (
    MarketBriefError,
    candidates_from_brief,
    fetch_commentary,
    normalize_alpha_vantage_response,
    normalize_finnhub_response,
    normalize_newsapi_response,
    render_morning_brief,
    sentiment_rollup,
    stage_research_candidates,
    top_headlines,
)

NOW = datetime.datetime(2026, 8, 22, 12, 0, tzinfo=datetime.timezone.utc)


def _newsapi_raw(*, title="Fed holds rates steady", url="https://example.com/fed-1",
                  published="2026-08-22T09:00:00Z", source="Example Wire"):
    return {"articles": [{
        "title": title, "description": "desc", "url": url,
        "source": {"id": "example", "name": source}, "publishedAt": published,
    }]}


def _alpha_vantage_raw(*, ticker="AAPL", url="https://example.com/aapl-1",
                        published="20260822T090000", score=0.28, relevance="0.9"):
    return {"feed": [{
        "title": "AAPL guidance beats", "url": url, "summary": "desc",
        "source": "Example Desk", "time_published": published,
        "overall_sentiment_score": 0.1, "overall_sentiment_label": "Neutral",
        "ticker_sentiment": [{
            "ticker": ticker, "relevance_score": relevance,
            "ticker_sentiment_score": score, "ticker_sentiment_label": "Somewhat-Bullish",
        }],
    }]}


def _finnhub_raw(*, headline="AAPL supplier note", url="https://example.com/aapl-2",
                  ts=1755853200):  # 2025-08-22T09:00:00Z-ish, any fixed epoch works
    return [{
        "headline": headline, "summary": "desc", "url": url,
        "source": "Example Newswire", "datetime": ts,
    }]


# --------------------------------------------------------------------------
# T-001 -- normalization (AC-001)
# --------------------------------------------------------------------------

def test_normalize_all_three_providers_AC_001():
    newsapi_items = normalize_newsapi_response(_newsapi_raw(), "Federal Reserve")
    av_items = normalize_alpha_vantage_response(_alpha_vantage_raw(), "AAPL")
    finnhub_items = normalize_finnhub_response(_finnhub_raw(), "AAPL")

    assert [i.provider for i in newsapi_items] == ["newsapi"]
    assert newsapi_items[0].title == "Fed holds rates steady"
    assert newsapi_items[0].matched_topics == ("Federal Reserve",)

    assert av_items[0].provider == "alpha_vantage"
    assert av_items[0].sentiment_score == 0.28  # ticker-specific, not the overall 0.1
    assert av_items[0].sentiment_label == "Somewhat-Bullish"
    assert av_items[0].relevance_score == 0.9

    assert finnhub_items[0].provider == "finnhub"
    assert finnhub_items[0].sentiment_score is None


# --------------------------------------------------------------------------
# T-002 -- fetch_commentary (AC-002, AC-003, AC-011)
# --------------------------------------------------------------------------

def test_fetch_commentary_excludes_items_before_lookback_cutoff_AC_002():
    fetch_fns = {"newsapi": lambda topic: _newsapi_raw(published="2026-08-20T09:00:00Z")}
    got = fetch_commentary(fetch_fns, ["Federal Reserve"], lookback_hours=18, now=NOW)
    assert got == []


def test_fetch_commentary_dedupes_and_merges_topics_across_providers_AC_003():
    shared_url = "https://example.com/same-story"
    fetch_fns = {
        "newsapi": lambda topic: _newsapi_raw(url=shared_url, title="Story"),
        "finnhub": lambda topic: _finnhub_raw(url=shared_url, headline="Story", ts=1755853200),
    }
    got = fetch_commentary(fetch_fns, ["Federal Reserve", "AAPL"], lookback_hours=999999, now=NOW)
    matching = [i for i in got if i.url == shared_url]
    assert len(matching) == 1
    assert set(matching[0].matched_topics) == {"Federal Reserve", "AAPL"}


def test_fetch_commentary_unknown_provider_raises_AC_011():
    with pytest.raises(MarketBriefError, match="bogus"):
        fetch_commentary({"bogus": lambda topic: {}}, ["AAPL"], lookback_hours=18, now=NOW)


# --------------------------------------------------------------------------
# T-003 -- top_headlines (AC-004)
# --------------------------------------------------------------------------

def test_top_headlines_truncates_most_recent_first_per_topic_AC_004():
    fetch_fns = {"newsapi": lambda topic: {"articles": [
        {"title": "older", "url": "https://example.com/1", "source": {"name": "s"},
         "publishedAt": "2026-08-22T06:00:00Z", "description": ""},
        {"title": "newer", "url": "https://example.com/2", "source": {"name": "s"},
         "publishedAt": "2026-08-22T09:00:00Z", "description": ""},
    ]}}
    items = fetch_commentary(fetch_fns, ["Federal Reserve"], lookback_hours=24, now=NOW)
    grouped = top_headlines(items, max_per_topic=1)
    assert [i.title for i in grouped["Federal Reserve"]] == ["newer"]


# --------------------------------------------------------------------------
# T-004 -- sentiment_rollup (AC-005, AC-006)
# --------------------------------------------------------------------------

def test_sentiment_rollup_only_covers_alpha_vantage_topics_AC_005():
    fetch_fns = {
        "alpha_vantage": lambda topic: _alpha_vantage_raw(ticker="AAPL", score=0.3),
        "newsapi": lambda topic: _newsapi_raw(url="https://example.com/other"),
    }
    items = fetch_commentary(fetch_fns, ["AAPL"], lookback_hours=24, now=NOW)
    rollup = sentiment_rollup(items)
    assert set(rollup) == {"AAPL"}
    assert rollup["AAPL"]["mean_sentiment"] == 0.3
    assert rollup["AAPL"]["article_count"] == 1


def test_sentiment_rollup_filters_below_min_relevance_AC_006():
    fetch_fns = {"alpha_vantage": lambda topic: _alpha_vantage_raw(relevance="0.1")}
    items = fetch_commentary(fetch_fns, ["AAPL"], lookback_hours=24, now=NOW)
    assert sentiment_rollup(items, min_relevance=0.5) == {}
    assert "AAPL" in sentiment_rollup(items, min_relevance=0.05)


# --------------------------------------------------------------------------
# T-005 -- render_morning_brief (AC-007)
# --------------------------------------------------------------------------

def test_render_morning_brief_never_fabricates_analysis_AC_007():
    fetch_fns = {"newsapi": lambda topic: _newsapi_raw()}
    items = fetch_commentary(fetch_fns, ["Federal Reserve"], lookback_hours=24, now=NOW)
    headlines = top_headlines(items, max_per_topic=5)
    rollup = sentiment_rollup(items)
    report = render_morning_brief(
        datetime.date(2026, 8, 22), headlines, rollup,
        "Written entirely by the agent, verbatim.",
        watchlist=["Federal Reserve"], providers_used=["newsapi"],
    )
    assert "Written entirely by the agent, verbatim." in report
    assert "Fed holds rates steady" in report
    assert "https://example.com/fed-1" in report
    assert "No Alpha Vantage coverage" in report


# --------------------------------------------------------------------------
# T-006 -- candidates_from_brief (AC-008, AC-009)
# --------------------------------------------------------------------------

def test_candidates_from_brief_empty_headlines_proposes_nothing_AC_008():
    assert candidates_from_brief(datetime.date(2026, 8, 22), {}, "analysis", source_run="run1") == []


def test_candidates_from_brief_builds_one_pending_review_candidate_AC_009():
    fetch_fns = {"newsapi": lambda topic: _newsapi_raw()}
    items = fetch_commentary(fetch_fns, ["Federal Reserve"], lookback_hours=24, now=NOW)
    headlines = top_headlines(items, max_per_topic=5)
    candidates = candidates_from_brief(
        datetime.date(2026, 8, 22), headlines, "The agent's view.", source_run="run1"
    )
    assert len(candidates) == 1
    c = candidates[0]
    assert c["review_status"] == "pending_review"
    assert c["source_type"] == "generated"
    assert "https://example.com/fed-1" in c["citation"]
    assert c["summary"] == "The agent's view."


# --------------------------------------------------------------------------
# T-007 -- stage_research_candidates (AC-010, AC-012)
# --------------------------------------------------------------------------

def test_stage_research_candidates_writes_local_inbox_file_AC_010(tmp_path):
    candidates = candidates_from_brief(
        datetime.date(2026, 8, 22),
        {"Federal Reserve": [normalize_newsapi_response(_newsapi_raw(), "Federal Reserve")[0]]},
        "analysis", source_run="run1",
    )
    path = stage_research_candidates(candidates, root=tmp_path, source_run="run1")
    assert path == tmp_path / "inbox" / "morning_brief" / "run1.yaml"
    text = path.read_text()
    assert "review_status: pending_review" in text
    assert "source_type: generated" in text
    # Staged under the caller-supplied root's own inbox/ -- never a path this
    # function invents itself (it writes wherever root points, nothing else).
    assert path.parent == tmp_path / "inbox" / "morning_brief"


def test_stage_research_candidates_empty_raises_AC_012(tmp_path):
    with pytest.raises(MarketBriefError):
        stage_research_candidates([], root=tmp_path, source_run="run1")


# --------------------------------------------------------------------------
# T-008 -- determinism (AC-013)
# --------------------------------------------------------------------------

def test_deterministic_AC_013():
    fetch_fns = {
        "newsapi": lambda topic: _newsapi_raw(),
        "finnhub": lambda topic: _finnhub_raw(),
    }
    first = fetch_commentary(fetch_fns, ["Federal Reserve", "AAPL"], lookback_hours=24, now=NOW)
    second = fetch_commentary(fetch_fns, ["Federal Reserve", "AAPL"], lookback_hours=24, now=NOW)
    assert [i.url for i in first] == [i.url for i in second]
