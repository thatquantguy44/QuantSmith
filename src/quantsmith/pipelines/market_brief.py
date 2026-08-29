"""Reference pipeline for spec 0059 -- the morning market brief.

Pulls free-API market commentary from three providers (NewsAPI general
search, Alpha Vantage ``NEWS_SENTIMENT``, Finnhub company/market news),
normalizes it into one shared shape, computes what can honestly be computed
deterministically (recency filtering, dedupe, a sentiment rollup where a
provider actually supplies one), and renders a report. The prose "Views &
Analysis" is never generated here -- that is
``agents/economists/morning_brief_writer/``'s job; this module composes
computed fields plus a caller-supplied narrative, the same discipline
``backtesting.render_backtest_report`` uses.

Closes the input-side half of spec ``0056``'s REQ-015 / AC-010 ("scheduled
research reports... candidates... enter review instead of being
auto-promoted"): ``candidates_from_brief`` proposes a
``research.ResearchItem``-shaped candidate and ``stage_research_candidates``
writes it to a **local-only** inbox file for human review. It never writes
to the committed ``research/`` reference store -- per spec 0056's own
Non-Goals, real generated research content must never be committed to this
repository.

Three boundaries are deliberate:

* **No network calls live here.** Every provider's ``fetch_fn`` is supplied
  by the caller (a real HTTP client plus a ``credential_access``-resolved
  key); this module only parses what it is handed. Same P9 boundary
  ``fred_point_in_time.py`` and ``credential_access`` already draw.
* **Sentiment is a signal, not a claim.** Only Alpha Vantage supplies a
  score; absence stays absence rather than being coerced to a neutral
  number, the same "absence is the truth" discipline
  ``fred_point_in_time.py`` uses for ``is_missing`` rows.
* **Staging is not promotion.** This module proposes and stages a candidate;
  nothing here writes it into a live, queryable index. Spec ``0056`` has no
  REQ describing promotion mechanics yet -- that is a future write-path
  spec, not this one.
"""

from __future__ import annotations

import dataclasses
import datetime
import os
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

PROVIDERS = ("newsapi", "alpha_vantage", "finnhub")

_SENTIMENT_BUCKETS = (
    (-0.35, "Bearish"),
    (-0.15, "Somewhat-Bearish"),
    (0.15, "Neutral"),
    (0.35, "Somewhat-Bullish"),
)


class MarketBriefError(ValueError):
    """Raised when provider input or staging arguments are unusable."""


@dataclasses.dataclass(frozen=True)
class CommentaryItem:
    """One normalized headline, from any of the three providers."""

    title: str
    description: str
    url: str
    source_name: str
    provider: str
    published_at: datetime.datetime
    matched_topics: Tuple[str, ...]
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    relevance_score: Optional[float] = None


# ---------------------------------------------------------------------------
# Per-provider normalization -- one function per raw response shape
# ---------------------------------------------------------------------------


def normalize_newsapi_response(raw: Mapping, topic: str) -> List[CommentaryItem]:
    """``GET /v2/everything`` -- ``{"articles": [{"title", "url", ...}]}``."""
    items: List[CommentaryItem] = []
    for article in raw.get("articles") or []:
        published_raw = article.get("publishedAt")
        published_at = _parse_iso8601(published_raw)
        if published_at is None:
            continue
        source = article.get("source") or {}
        items.append(
            CommentaryItem(
                title=str(article.get("title", "")),
                description=str(article.get("description") or ""),
                url=str(article.get("url", "")),
                source_name=str(source.get("name", "")),
                provider="newsapi",
                published_at=published_at,
                matched_topics=(topic,),
            )
        )
    return items


def normalize_alpha_vantage_response(raw: Mapping, topic: str) -> List[CommentaryItem]:
    """``NEWS_SENTIMENT`` -- ``{"feed": [{"time_published": "20260822T100000", ...}]}``."""
    items: List[CommentaryItem] = []
    for entry in raw.get("feed") or []:
        published_at = _parse_alpha_vantage_timestamp(entry.get("time_published"))
        if published_at is None:
            continue
        score = entry.get("overall_sentiment_score")
        label = entry.get("overall_sentiment_label")
        relevance: Optional[float] = None
        for ticker_sentiment in entry.get("ticker_sentiment") or []:
            if str(ticker_sentiment.get("ticker", "")).upper() == topic.upper():
                score = ticker_sentiment.get("ticker_sentiment_score", score)
                label = ticker_sentiment.get("ticker_sentiment_label", label)
                relevance = _to_float(ticker_sentiment.get("relevance_score"))
                break
        items.append(
            CommentaryItem(
                title=str(entry.get("title", "")),
                description=str(entry.get("summary") or ""),
                url=str(entry.get("url", "")),
                source_name=str(entry.get("source", "")),
                provider="alpha_vantage",
                published_at=published_at,
                matched_topics=(topic,),
                sentiment_score=_to_float(score),
                sentiment_label=str(label) if label is not None else None,
                relevance_score=relevance,
            )
        )
    return items


def normalize_finnhub_response(raw, topic: str) -> List[CommentaryItem]:
    """``/company-news`` or ``/news`` -- a bare JSON array of article dicts."""
    items: List[CommentaryItem] = []
    for article in raw or []:
        published_at = _parse_unix_timestamp(article.get("datetime"))
        if published_at is None:
            continue
        items.append(
            CommentaryItem(
                title=str(article.get("headline", "")),
                description=str(article.get("summary") or ""),
                url=str(article.get("url", "")),
                source_name=str(article.get("source", "")),
                provider="finnhub",
                published_at=published_at,
                matched_topics=(topic,),
            )
        )
    return items


_NORMALIZERS: Dict[str, Callable[[object, str], List[CommentaryItem]]] = {
    "newsapi": normalize_newsapi_response,
    "alpha_vantage": normalize_alpha_vantage_response,
    "finnhub": normalize_finnhub_response,
}

FetchFn = Callable[[str], object]


# ---------------------------------------------------------------------------
# Fetch, merge, and deterministic aggregation
# ---------------------------------------------------------------------------


def fetch_commentary(
    fetch_fns: Mapping[str, FetchFn],
    topics: Sequence[str],
    *,
    lookback_hours: int,
    now: datetime.datetime,
) -> List[CommentaryItem]:
    """Pull, normalize, filter, and merge commentary across every enabled provider.

    ``fetch_fns`` maps a provider name (``PROVIDERS``) to a callable the
    caller supplies -- ``fetch_fn(topic) -> raw response``. No network call
    is made by this function; the caller's callable owns that. Deduplicates
    by URL *across* providers, merging ``matched_topics`` rather than
    duplicating the article, so the same story covered by two providers
    becomes one ``CommentaryItem``.
    """
    unknown = set(fetch_fns) - set(PROVIDERS)
    if unknown:
        raise MarketBriefError(f"unknown provider(s) {sorted(unknown)}; must be a subset of {PROVIDERS}")

    cutoff = now - datetime.timedelta(hours=lookback_hours)
    by_url: Dict[str, CommentaryItem] = {}

    for provider, fetch_fn in fetch_fns.items():
        normalize = _NORMALIZERS[provider]
        for topic in topics:
            raw = fetch_fn(topic)
            for item in normalize(raw, topic):
                if item.published_at < cutoff or not item.url:
                    continue
                existing = by_url.get(item.url)
                if existing is None:
                    by_url[item.url] = item
                else:
                    merged_topics = tuple(sorted(set(existing.matched_topics) | set(item.matched_topics)))
                    by_url[item.url] = dataclasses.replace(existing, matched_topics=merged_topics)

    return sorted(by_url.values(), key=lambda i: (i.published_at, i.url), reverse=True)


def top_headlines(
    items: Sequence[CommentaryItem], *, max_per_topic: int
) -> Dict[str, List[CommentaryItem]]:
    """Group by matched topic, most-recent-first, truncated. No ranking beyond recency."""
    by_topic: Dict[str, List[CommentaryItem]] = {}
    for item in items:
        for topic in item.matched_topics:
            by_topic.setdefault(topic, []).append(item)
    return {
        topic: sorted(group, key=lambda i: (i.published_at, i.url), reverse=True)[:max_per_topic]
        for topic, group in sorted(by_topic.items())
    }


def sentiment_rollup(
    items: Sequence[CommentaryItem], *, min_relevance: float = 0.0
) -> Dict[str, Dict[str, object]]:
    """Mean ``sentiment_score`` per topic, Alpha Vantage items only.

    An item with no score (NewsAPI, Finnhub, or a relevance below
    ``min_relevance``) contributes nothing -- never coerced to a neutral
    0.0, the same "absence is the truth" rule ``fred_point_in_time.py``
    applies to ``is_missing`` rows.
    """
    by_topic: Dict[str, List[CommentaryItem]] = {}
    for item in items:
        if item.sentiment_score is None:
            continue
        if item.relevance_score is not None and item.relevance_score < min_relevance:
            continue
        for topic in item.matched_topics:
            by_topic.setdefault(topic, []).append(item)

    rollup: Dict[str, Dict[str, object]] = {}
    for topic, group in sorted(by_topic.items()):
        mean_score = sum(i.sentiment_score for i in group) / len(group)
        rollup[topic] = {
            "mean_sentiment": mean_score,
            "label": _sentiment_label(mean_score),
            "article_count": len(group),
        }
    return rollup


# ---------------------------------------------------------------------------
# Rendering -- REQ-005 (per spec.md)
# ---------------------------------------------------------------------------


def render_morning_brief(
    as_of: datetime.date,
    headlines_by_topic: Mapping[str, Sequence[CommentaryItem]],
    sentiment: Mapping[str, Mapping[str, object]],
    analysis_markdown: str,
    *,
    watchlist: Sequence[str],
    providers_used: Sequence[str],
) -> str:
    """Render ``templates/docs/morning_market_brief.md``'s shape.

    ``analysis_markdown`` is supplied by the caller (the agent) and never
    generated here -- the same composition discipline
    ``backtesting.render_backtest_report`` uses for computed-plus-supplied
    fields.
    """
    o: List[str] = []
    o.append(f"# Morning Market Brief: {as_of.isoformat()}")
    o.append("")
    o.append(f"- **As-of date:** {as_of.isoformat()}")
    o.append(f"- **Watchlist:** {', '.join(watchlist)}")
    o.append(f"- **Providers:** {', '.join(sorted(providers_used))}")
    o.append("")
    o.append(
        "> Generated by `render_morning_brief` (spec `0059-morning-market-brief`) "
        "from real pulled headlines plus agent-written analysis. Headlines and "
        "sentiment rollup are computed; Views & Analysis is written by "
        "`agents/economists/morning_brief_writer/`."
    )
    o.append("")

    o.append("## Headlines")
    o.append("")
    if not headlines_by_topic:
        o.append("No headlines matched the watchlist within the lookback window.")
        o.append("")
    for topic, items in headlines_by_topic.items():
        o.append(f"### {topic}")
        o.append("")
        for item in items:
            o.append(
                f"- [{item.title}]({item.url}) — *{item.source_name}*, "
                f"{item.published_at.isoformat()}, via `{item.provider}`"
            )
        o.append("")

    o.append("## Sentiment Rollup")
    o.append("")
    if sentiment:
        o.append("| Ticker | Mean sentiment | Label | Articles |")
        o.append("| --- | --- | --- | --- |")
        for topic, row in sentiment.items():
            o.append(
                f"| {topic} | {row['mean_sentiment']:.3f} | {row['label']} | "
                f"{row['article_count']} |"
            )
    else:
        o.append("No Alpha Vantage coverage for this watchlist in this run.")
    o.append("")

    o.append("## Views & Analysis")
    o.append("")
    o.append(analysis_markdown or "*(not yet written)*")
    o.append("")

    o.append("## Sources & Citations")
    o.append("")
    seen: Dict[str, CommentaryItem] = {}
    for items in headlines_by_topic.values():
        for item in items:
            seen[item.url] = item
    for item in sorted(seen.values(), key=lambda i: (i.published_at, i.url), reverse=True):
        o.append(f"- {item.title} — {item.source_name}, {item.published_at.date().isoformat()}: {item.url}")
    o.append("")

    return "\n".join(o)


# ---------------------------------------------------------------------------
# Staging for review -- 0056 REQ-015 / AC-010
# ---------------------------------------------------------------------------


def candidates_from_brief(
    as_of: datetime.date,
    headlines_by_topic: Mapping[str, Sequence[CommentaryItem]],
    analysis_markdown: str,
    *,
    source_run: str,
    access_level: str = "internal",
    entitlement_class: str = "firm-internal",
) -> List[Dict[str, object]]:
    """Turn a rendered brief into a ``research.ResearchItem``-shaped candidate.

    One candidate per run, not one per topic: the agent wrote one coherent
    analysis, not independent per-topic pieces, so splitting it would
    fabricate structure that was never actually produced. Returns a
    candidate only when there is at least one real headline behind it --
    an empty run proposes nothing. Proposes only; does not stage (mirrors
    ``ingestion_data_contract.candidates_from_validation``'s division of
    responsibility).
    """
    all_items: Dict[str, CommentaryItem] = {}
    for items in headlines_by_topic.values():
        for item in items:
            all_items[item.url] = item
    if not all_items:
        return []

    citations = [
        f"{item.title} — {item.source_name}, {item.published_at.date().isoformat()}: {item.url}"
        for item in sorted(all_items.values(), key=lambda i: (i.published_at, i.url), reverse=True)
    ]
    topics = sorted(headlines_by_topic.keys())

    candidate = {
        "id": f"BRIEF-{as_of.isoformat()}-{source_run}",
        "title": f"Morning brief — {as_of.isoformat()}",
        "source_type": "generated",
        "author_or_publisher": "morning_brief_writer (agent)",
        "asset_class": "multi_asset",
        "strategy_theme": ", ".join(topics),
        "access_level": access_level,
        "entitlement_class": entitlement_class,
        "publication_date": as_of,
        "ingestion_date": as_of,
        "review_status": "pending_review",
        "freshness_days": 1,
        "summary": analysis_markdown,
        "citation": "; ".join(citations),
    }
    return [candidate]


def stage_research_candidates(
    candidates: Sequence[Mapping[str, object]],
    *,
    root: "str | os.PathLike[str]",
    source_run: str,
) -> Path:
    """Write candidates to a local-only inbox file for human review.

    Writes ``<root>/inbox/morning_brief/<source_run>.yaml`` -- mirrors
    ``workflow_memory``'s own ``memory/inbox/<workflow>/<source_run>.yaml``
    staging shape, but rooted under a directory the caller must keep
    gitignored (the packaged default is ``research_local/``; see
    ``templates/data/morning_brief_config.yml``). Never writes into
    ``research/`` -- spec 0056's Non-Goals are explicit that real generated
    research content must never be committed to this repository.
    """
    if not candidates:
        raise MarketBriefError("no candidates to stage")

    path = Path(root) / "inbox" / "morning_brief" / f"{source_run}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["items:"]
    for candidate in candidates:
        lines.extend(_render_candidate_entry(candidate))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Small internal helpers
# ---------------------------------------------------------------------------


def _parse_iso8601(value: object) -> Optional[datetime.datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def _parse_alpha_vantage_timestamp(value: object) -> Optional[datetime.datetime]:
    # "20260822T100000" -- Alpha Vantage's own compact UTC format.
    if not value:
        return None
    try:
        dt = datetime.datetime.strptime(str(value), "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    return dt.replace(tzinfo=datetime.timezone.utc)


def _parse_unix_timestamp(value: object) -> Optional[datetime.datetime]:
    if value is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(value), tz=datetime.timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sentiment_label(score: float) -> str:
    for threshold, label in _SENTIMENT_BUCKETS:
        if score < threshold:
            return label
    return "Bullish"


def _yaml_scalar(value: object) -> str:
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if any(ch in text for ch in (":", '"', "#", "\n")) or text.strip() != text:
        text = text.replace('"', "'")
        return f'"{text}"'
    return text


def _render_candidate_entry(candidate: Mapping[str, object], *, indent: str = "  ") -> List[str]:
    lines: List[str] = []
    first = True
    for key, value in candidate.items():
        prefix = f"{indent}- " if first else f"{indent}  "
        first = False
        lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    return lines
