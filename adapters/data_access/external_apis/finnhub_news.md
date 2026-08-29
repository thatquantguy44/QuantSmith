# Finnhub Company/Market News Profile

## Use For

- Ticker-scoped company news, and general market-news headlines, from
  Finnhub's free news endpoints.
- The per-position coverage leg of spec `0059`'s morning market brief,
  alongside `newsapi.md` (general coverage) and `alpha_vantage_news.md`
  (sentiment-scored).

## Required Metadata

- `symbol` (the watchlist ticker this request was scoped to, for
  `company-news`; omitted for the general `news` endpoint)
- `headline`, `summary`, `url`
- `source`
- `datetime` (Unix timestamp; convert to UTC before storing)
- `category`
- `retrieved_at_utc`
- `provider` (`"finnhub"`)

## Delivery Rules

- Use `/company-news?symbol=...&from=...&to=...` for a specific watchlist
  ticker, and `/news?category=general` only for broad market coverage —
  the two endpoints are not interchangeable and mixing their results
  without recording which one a headline came from loses that distinction.
- `company-news` takes one call per ticker; a multi-ticker watchlist means
  one request per symbol per run, not one batched call — size request
  volume accordingly against the free tier's 60-calls/minute limit.
- No sentiment field exists on these endpoints; do not infer or fabricate
  one downstream — `category` and `headline`/`summary` text are all that's
  available.
- Deduplicate by `url` when a headline appears under both a ticker-scoped
  and a general-market pull.

## Risks

- Free-tier `company-news` lookback is capped to roughly one year; a
  request for an older window silently returns nothing rather than an
  error — check the returned range against what was requested.
- `category` values are provider-defined and coarse (e.g. `general`,
  `forex`, `crypto`, `merger`); do not treat them as a reliable substitute
  for the watchlist's own topic taxonomy.
