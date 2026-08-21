# Email Market Color Source: <source-name>

> Provider-neutral contract for scanning only explicitly tagged market color from
> an approved mailbox. Backed by spec `0056-market-research-knowledge-base`.

## Source

- **provider:** gmail | outlook | imap_export | firm_search_export | other
- **mailbox_ref:** <mailbox alias or connector-owned mailbox id>
- **source_type:** email_market_color
- **owner:** <team or person accountable for this source>
- **access_level:** public | internal | restricted
- **entitlement_class:** <license/access policy id>
- **retention_policy:** <retention policy id>

## Scan Scope

- **label_filters:** [market-color, research-approved]
- **folder_filters:** []
- **saved_search_ref:** <optional provider saved-search id>
- **sender_allowlist:** [example.com, desk-list@example.com]
- **sender_denylist:** []
- **lookback_days_initial:** <integer>
- **cursor:** <provider cursor or timestamp watermark>

## Ingestion Policy

- **read_only:** true
- **review_required:** true
- **attachment_policy:** metadata_only | review_required | index_allowed | ignore
- **store_recipients:** omit | hash | approved_distribution_only | store
- **index_body:** false
- **index_snippets_after_review:** true

## Metadata Mapping

| Email field | Market research field |
| --- | --- |
| provider thread id | `thread_id` |
| provider message id | `message_id` |
| sent timestamp | `published_at` / `sent_at` |
| received timestamp | `received_at` / availability timestamp |
| from/sender | `author_or_publisher` |
| label/folder/saved search | `tag_provenance` |
| subject | `title` |
| approved extracted passage | citation passage |

## Review Checklist

- [ ] Message was intentionally tagged as market color or research.
- [ ] Sender/domain is allowed for this source.
- [ ] No secrets, PII, MNPI, restricted-list content, or prohibited third-party
      material is indexed.
- [ ] Attachment handling follows the declared policy.
- [ ] Citation points to the original message/thread, not only a generated summary.
