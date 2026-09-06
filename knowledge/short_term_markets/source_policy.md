# Short-Term Markets Source Policy

This policy applies to records in `knowledge/short_term_markets/`.

## Source Hierarchy

Use the highest authority that supports the specific claim:

| Tier | Authority type | Examples |
| --- | --- | --- |
| 1 | Official statutes, regulations, rules, releases, and agency datasets | SEC, Federal Reserve Board, U.S. Treasury |
| 2 | Official benchmark administrators and government market datasets | NY Fed SOFR/repo datasets, Treasury auction/rates data |
| 3 | Clearing, settlement, and reporting infrastructure specifications | DTCC/FICC public materials |
| 4 | Recognized industry-standard documentation | SIFMA or other industry bodies when they define operational conventions |
| 5 | Licensed vendor methodology or data dictionary | Vendor metadata only when access and redistribution rights permit it |
| 6 | Reviewed internal procedure | Derived operational rule without client, counterparty, or proprietary terms |
| 7 | Analyst interpretation | Always labeled; never promoted above its evidence |

The existing `sources/` catalog remains the source registry. Domain records cite
sources as `source.<source_id>`. This pack must not create a second source
catalog with competing connection metadata.

## Evidence Fields

Reviewed records require field- or claim-level evidence. The evidence may live
in a source entry, a public document locator, or a later governed knowledge
record, but the review envelope must identify:

- registered `source_id`;
- authority type and tier;
- document, dataset, release, or API locator;
- publication date or dataset vintage when available;
- retrieval date for web/API material;
- jurisdiction and effective interval;
- access class and license or redistribution notes;
- supported record IDs and fields; and
- conflict disposition if another source disagrees.

Records without that evidence remain `draft`.

## Temporal Rules

Every record has two clocks:

- `knowledge_as_of`: when this record version became knowable to the library.
- `effective_from` / `effective_to`: when the underlying convention, rule,
  observation, or assumption applies.

An as-of query first filters `knowledge_as_of <= as_of`, then filters the
effective interval. A later-known observation or rule version is excluded even
when its effective dates overlap the query date. `effective_from` is inclusive;
`effective_to` is exclusive.

## Knowledge Classes

| Class | Temporal behavior |
| --- | --- |
| `stable_mechanic` | May have null effective dates, but still has `knowledge_as_of` and review status. |
| `contractual_convention` | Requires declared parties/context; null effective dates mean "contract-specific", not universal. |
| `regulatory_policy` | Requires jurisdiction, authority, publication/effective timing, and review freshness. |
| `market_observation` | Requires as-of/knowledge date, observation date, and a source with point-in-time behavior. |
| `empirical_finding` | Requires sample period, methodology, and stale-by review rules. |
| `model_assumption` | May cite `assumption.<id>` or no source, but must be parameterized and cannot be called sourced truth. |

## Conflicts And Freshness

Conflicting sources are resolved in one of three ways:

- choose the higher authority for the exact claim and record the lower source as
  superseded or context-only;
- keep both as visible conflicts if they apply to different products, venues,
  counterparties, or dates; or
- keep the record in `draft` until a qualified reviewer resolves the conflict.

Freshness is not the same as correctness. A stable mechanic may need infrequent
review, while a market observation can be stale immediately after a new
publication. Later specs `0068` and `0069` own source ingestion and regulatory
freshness automation.

## Safety And Licensing

This repository may contain public metadata, derived definitions, stable IDs,
locators, and small deterministic examples. It must not contain credentials,
MNPI, personal data, proprietary feed values, client terms, internal
counterparty schedules, or licensed agreement text.

When a source is public but redistribution is constrained, record the locator
and access class; do not copy the protected content.
