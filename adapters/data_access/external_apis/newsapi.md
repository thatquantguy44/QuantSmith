# NewsAPI.org Profile

## Use For

- Broad general-news search and headline aggregation across thousands of
  publishers — macro, market-wide, and topic-keyword coverage that isn't
  scoped to a single ticker.
- The general-coverage leg of spec `0059`'s morning market brief, alongside
  `alpha_vantage_news.md` (sentiment-scored, ticker-tagged) and
  `finnhub_news.md` (ticker-scoped).

## Required Metadata

- `query` (the search term or watchlist topic used for this request)
- `title`, `description`, `url`
- `source.name` (the publisher)
- `published_at`
- `retrieved_at_utc`
- `provider` (`"newsapi"`, so a caller merging multiple providers can trace
  an item back to its source)

## Delivery Rules

- Use `/v2/everything` with an explicit `q`, `from`/`to` window, and
  `sortBy=publishedAt` — do not rely on `/v2/top-headlines`, which is scoped
  to a fixed set of categories/countries rather than a caller-chosen topic.
- The free "Developer" tier delays articles roughly 24 hours and is
  restricted by NewsAPI's own terms to non-commercial, local-development
  use — state this plainly wherever a pull is used, never assume a paid
  tier silently.
- Deduplicate by `url` before treating two results as distinct stories —
  the same wire story is frequently syndicated across multiple listed
  publishers.
- No sentiment or ticker field exists on this provider; a caller matching
  an article to a specific security is doing keyword matching, not a
  verified association — do not present it as one.

## Risks

- Free-tier rate limit (100 requests/day) is easy to exhaust with a
  multi-topic watchlist pulled daily; batch topics into as few queries as
  the API's boolean query syntax allows rather than one request per term.
- Relevance is keyword-based only; an article matching a watchlist term by
  coincidence (a company name that is also a common word) can slip through
  without a human or model relevance pass downstream.
