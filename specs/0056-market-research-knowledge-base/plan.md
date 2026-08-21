# Plan: Market Research Knowledge Base

- **Spec:** 0056-market-research-knowledge-base (`spec.md`)
- **Status:** Draft
- **Author:** QuantSmith
- **Last updated:** 2026-08-21

> HOW. This plan requires an approved `spec.md`. Every requirement in the spec
> must appear in the traceability matrix below.

## Approach

Use the existing knowledge-base/MCP layer as the single agent-facing interface,
and put market-research-specific storage, indexing, and governance behind that
interface. The SDK repository carries contracts, schemas, templates, tests, and
reference adapters only; real research content remains in external governed
stores.

The core design is a normalized market-research catalog in front of multiple
backing stores. Agents query one namespace, such as
`knowledge://market_research/<asset_class>/<source_type>/<item_id>`, while the
server resolves caller clearance, storage location, search index, citations,
freshness, and point-in-time filters internally.

This keeps market research distinct from workflow memory. Workflow memory
captures lessons about datasets, fields, runs, and model behavior. Market
research captures sourced views, theses, market color, manager commentary, and
generated syntheses that require entitlement-aware retrieval.

## Architecture & Components

| Component | Responsibility |
| --- | --- |
| Market research source manifest | Extends `knowledge_sources.yml` concepts with source type, entitlement class, retention, and indexing policy. |
| Ingestion adapter | Normalizes files, notes, generated reports, manager letters, and firm research into reviewable items. |
| Metadata catalog | Stores item ids, provenance, classifications, access metadata, dates, status, and supersession links. |
| Governed content store | Holds original content in provider-appropriate storage outside the SDK repo. |
| Search/index tier | Builds access-tiered keyword/vector indexes from approved items or metadata-only records. |
| Governance policy engine | Applies clearance, entitlement, confidentiality, retention, and information-barrier rules before retrieval. |
| MCP retrieval server | Exposes one `knowledge://market_research/...` surface and query tools to agents. |
| Citation renderer | Returns cited passages or item summaries with accessible provenance. |
| Audit ledger | Records ingestion, review, retrieval, denial, citation, and deletion/deprecation events. |

## Interfaces & Data Contracts

### Knowledge URI

```text
knowledge://market_research/<asset_class>/<source_type>/<item_id>
```

Examples:

```text
knowledge://market_research/rates/firm_note/2026-08-21-policy-path
knowledge://market_research/equities/fund_manager_letter/manager-a-2026-q2
knowledge://market_research/macro/market_color/2026-08-21-asia-session
knowledge://market_research/credit/generated_synthesis/2026-08-21-spread-watch
```

### Market Research Item

| Field | Required | Notes |
| --- | --- | --- |
| `item_id` | yes | Stable id used in citations and audit records. |
| `source_uri` | yes | Pointer to original governed content. |
| `title` | yes | Human-readable title. |
| `source_type` | yes | `user_note`, `generated_report`, `firm_research`, `fund_manager`, `sell_side`, `transcript`, `meeting_note`, `other`. |
| `author_or_publisher` | yes | Person, desk, firm, manager, or provider. |
| `published_at` | yes | Source publication date. |
| `effective_at` | no | Date the content describes, if different. |
| `ingested_at` | yes | System ingestion date. |
| `content_hash` | yes | Version/provenance anchor. |
| `asset_class` | yes | Common taxonomy plus `multi_asset`. |
| `entities` | no | Securities, issuers, countries, managers, sectors, curves, commodities, or protocols. |
| `themes` | no | Strategy/regime/topic labels. |
| `confidentiality` | yes | `public`, `internal`, `restricted`, `mnpi_quarantine`. |
| `entitlement_class` | yes | License/access class used before index selection. |
| `status` | yes | `draft`, `pending_review`, `approved`, `quarantined`, `restricted`, `superseded`, `deprecated`, `deleted`. |
| `freshness_days` | no | Current-context staleness threshold. |
| `superseded_by` | no | Links later canonical item. |
| `canonical_of` | no | Links conflict group or duplicate set. |

### Retrieval Request

| Field | Required | Notes |
| --- | --- | --- |
| `query` | yes | Natural-language or structured search intent. |
| `domain` | yes | Defaults to `market_research`. |
| `asset_class` | no | Optional filter. |
| `source_type` | no | Optional filter. |
| `as_of` | no | Excludes later knowledge unless comparison mode is requested. |
| `caller_clearance` | yes | Access level and information-barrier context. |
| `entitlements` | yes | Approved third-party/provider licenses for the caller. |
| `freshness_mode` | no | `current`, `historical`, or `include_stale`. |
| `citation_mode` | yes | `passage` or `item_summary`; bare answer is invalid. |

### Retrieval Response

| Field | Required | Notes |
| --- | --- | --- |
| `results` | yes | Accessible cited passages or item summaries. |
| `unsupported_gaps` | yes | Claims or subquestions not supported by accessible sources. |
| `denial_summary` | yes | Non-revealing denial classes, not restricted titles. |
| `as_of_applied` | yes | Confirms point-in-time scope. |
| `audit_id` | yes | Reconstructs retrieval and citation decisions. |

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Retrieval requires provenance, access filters, citations, and `as_of` filtering before answer composition. |
| P5 Reversibility | yes | Items can move through review, quarantine, supersession, deprecation, deletion, and index rebuild states with audit records. |
| P6 Observability | yes | Ingestion, denial, retrieval, citation, and curation decisions are audit events. |
| P9 Security & data | yes | Restricted content remains outside the repo, caller clearance is explicit, and access-tiered indexes prevent post-retrieval leakage. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Market Research Item schema and ingestion adapter | T-001, T-002 |
| REQ-002 | MCP retrieval server and `knowledge://market_research/...` namespace | T-003 |
| REQ-003 | Governed content store abstraction and metadata catalog | T-001, T-004 |
| REQ-004 | Provenance fields in Market Research Item | T-001, T-002 |
| REQ-005 | Classification taxonomy | T-001, T-005 |
| REQ-006 | Governance policy engine and access-tiered index selection | T-006, T-007 |
| REQ-007 | Point-in-time retrieval fields and filters | T-008 |
| REQ-008 | Citation renderer and response contract | T-009 |
| REQ-009 | Result typing for fact/color/opinion/generated/stale/unsupported | T-005, T-009 |
| REQ-010 | Ingestion status lifecycle | T-002, T-010 |
| REQ-011 | Quarantine checks for secrets, PII, MNPI, and license restrictions | T-006, T-010 |
| REQ-012 | Audit ledger | T-011 |
| REQ-013 | Agent integration contract | T-003, T-012 |
| REQ-014 | Curation conflict/canonical-source workflow | T-013 |
| REQ-015 | Scheduled report knowledge-candidate handoff | T-014 |
| NFR-001 | Access-tiered search and non-revealing denial response | T-006, T-007 |
| NFR-002 | Citation coverage validator | T-009, T-015 |
| NFR-003 | `as_of` validator | T-008, T-015 |
| NFR-004 | Storage adapter contract | T-004 |
| NFR-005 | Catalog/index scalability benchmark fixture | T-016 |
| NFR-006 | Retrieval latency benchmark fixture | T-016 |
| NFR-007 | Immutable audit record schema | T-011 |
| NFR-008 | Compliance metadata propagation | T-006, T-010 |
| NFR-009 | Freshness/index compaction policy | T-005, T-017 |
| NFR-010 | Rebuild/deprecate/delete lifecycle tests | T-010, T-017 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| MCP shape | Same MCP interface, separate market-research namespace | Separate market-research MCP client path | One retrieval contract is easier for agents to use and govern. |
| Storage | External governed stores with SDK contracts | Commit research documents to the repo | Prevents confidential, licensed, or MNPI-adjacent content from entering source control. |
| Access filtering | Select access-tiered indexes before search | Search everything, then filter results | Post-retrieval filtering can leak restricted document existence. |
| Generated content | Treat as derived synthesis with citations | Treat generated summaries as primary sources | Prevents model-generated prose from becoming unsupported firm knowledge. |
| Taxonomy | Common core plus optional asset-class fields | One rigid schema for all markets | Rates, equities, credit, FX, commodities, and digital assets need different detail without losing common retrieval fields. |

## Validation Strategy

- Unit tests validate schema requirements, status lifecycle, provenance, and
  classification behavior.
- Access-control tests prove restricted content is neither returned nor
  existence-leaked to unauthorized callers.
- Point-in-time tests prove later publication, ingestion, and supersession dates
  are excluded under historical `as_of` queries.
- Citation tests prove every returned answer claim maps to an accessible citation
  and unsupported gaps are explicit.
- Quarantine tests prove secrets, PII, MNPI indicators, and license-restricted
  content are excluded from searchable indexes until review.
- Benchmark fixtures validate million-item catalog shape and retrieval latency
  assumptions with synthetic metadata only.

## Rollout, Observability & Rollback

Roll out in four slices:

1. Contract-only: schema, namespace, source manifest extension, and tests with
   synthetic market-research metadata.
2. Read-only MCP resources: expose approved Markdown/text/PDF-derived summaries
   through `knowledge://market_research/...`.
3. Governed RAG: build access-tiered indexes, citation rendering, and denial
   audit records.
4. Scheduled operations integration: use `0055` to run ingestion scans, daily
   review status, stale-content reports, and knowledge-candidate handoffs.

Rollback is provider-local: remove a source from the manifest, mark items
quarantined/deprecated, rebuild affected indexes, and preserve audit records.

## Open Questions

- Which storage providers should the first adapter support?
- Which entitlement/confidentiality taxonomy is authoritative?
- Which source types can be passage-indexed versus metadata-only?
- Who owns canonical-source decisions for conflicting investment views?
- What retention policy applies to generated synthesis and external research?
