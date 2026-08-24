# Alpha Vantage NEWS_SENTIMENT Profile

## Use For

- Ticker-tagged news and market-commentary headlines carrying a
  machine-readable sentiment score and label, per article and per mentioned
  ticker.
- The sentiment-scored leg of spec `0059`'s morning market brief — the one
  provider among the three that gives the pipeline a genuinely deterministic
  aggregate to compute (a sentiment rollup by ticker), alongside `newsapi.md`
  (general coverage) and `finnhub_news.md` (ticker-scoped, no sentiment).

## Required Metadata

- `tickers` (the watchlist symbol(s) this request was scoped to)
- `title`, `url`, `source` (the publisher)
- `time_published`
- `overall_sentiment_score`, `overall_sentiment_label`
- `ticker_sentiment[]` — per-ticker `relevance_score` and
  `ticker_sentiment_score`/`ticker_sentiment_label`, kept alongside the
  overall figures rather than collapsed into one number
- `retrieved_at_utc`
- `provider` (`"alpha_vantage"`)

## Delivery Rules

- Call `function=NEWS_SENTIMENT` with an explicit `tickers` parameter per
  watchlist symbol rather than pulling the unscoped topic feed and filtering
  client-side — the ticker-scoped call is what populates `ticker_sentiment[]`.
- Treat `overall_sentiment_score`/`label` and any given ticker's
  `ticker_sentiment_score`/`label` as **the provider's model output, not a
  verified fact** — surface it as a signal, per
  `instructions/knowledge_base.md`'s grounding standard, never as an
  assertion about what the market believes.
- Filter on `relevance_score` before including a ticker's sentiment in any
  rollup; a low-relevance mention (the ticker appears once, in passing)
  should not carry the same weight as a headline centered on it.
- Preserve `time_published` alongside every sentiment figure — a sentiment
  score has a shelf life, and an old score presented as current is
  misleading in the same way a stale FRED vintage would be.

## Risks

- The free-tier key is rate-limited (historically around 25 requests/day);
  a watchlist with many tickers, pulled daily, can exhaust it quickly —
  size the watchlist to the key's actual limit, not the ideal one.
- Sentiment is a single provider's model, not a consensus; averaging it
  across articles can smooth out a genuine disagreement between sources
  into a falsely confident middle number.
- A ticker symbol can collide across exchanges/asset classes; confirm the
  watchlist entry resolves to the intended security before trusting its
  sentiment rollup.
