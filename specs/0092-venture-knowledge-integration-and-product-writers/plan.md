# Plan: Venture Knowledge Integration and Product Writers

- **Spec:** 0092-venture-knowledge-integration-and-product-writers (`spec.md`)
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-03

> HOW. Requires the Draft spec; `tasks.md` tracks status.

## Approach

Connect, do not rebuild. The existing memory runtime already has the record vocabulary
(`quirk`, `pitfall`, `pattern`, `decision`), a candidate-and-promotion write path, a manifest
that accepts an external path, and a point-in-time scope; the MCP servers already enforce
`public < internal < restricted`; the `knowledge` gate already reads a local `knowledge_sources.yml`.
This spec adds the private store, the venture-shaped candidates, a retrieval contract, and product
validation, and changes none of those systems.

## Architecture & Components

```
knowledge_local/<domain>/            (gitignored) store.yml, memory/, cohorts/, vendor_notes/, indexes/
templates/knowledge_local/           README, store.yml, memory_manifest_entry.yml, knowledge_sources_entry.yml
src/quantsmith/pipelines/venture_knowledge.py
    parse_flat_yaml, validate_store, tracked_files_under
    load_source_quality, source_quirk_candidates, channel_lesson_candidate,
    screening_decision_candidate, stage_to_local_store
    Document, validate_documents, retrieve, retrieval_contract_violations
src/quantsmith/pipelines/venture_products.py
    index_passages, validate_product, releasable, render_markdown
agents/venture_intelligence/{intelligence_brief_writer,investment_memo_writer}
knowledge/venture_intelligence/conventions.json   (+ product_rules, retrieval_contract)
hooks/stages/{docs-link-check,memory-check}.sh    (skip / scan knowledge_local)
tests/test_venture_knowledge.py
```

## Interfaces & Data Contracts

- `retrieve(query, documents, caller_clearance, as_of, k, min_score)` -> `{"status": "ok" | "not_found", "passages": [...], "reason", "as_of", "caller_clearance", "tokenizer"}`; a passage has `citation_id` (`doc:start-end`), `doc_id`, `source_id`, `start`, `end`, `text`, `score`, `content_hash`, `passage_hash`, `access_level`, `known_at`, `source_grade`, `language`. Order: require clearance, drop ineligible, rank eligible only, cite or `not_found`.
- Product: `kind`, `title`, `as_of`, `access_level`, `status`, `reviewer`, optional `bluf` and `decision_owner`; `evidence[]` (`id`, `text`, `citations`, `source_grade`, `claim_id`, `origin_id`, `channel`, `derived`, `reviewer`), `assumptions[]` (`basis`), `judgements[]` (`likelihood`, `probability`, `evidence_confidence`, `rests_on`), `open_gaps[]`.
- `validate_product(...) -> ["<item>: <code>: detail"]`; codes include `uncited_claim`, `unresolvable_citation`, `cites_future_information`, `cites_above_classification`, `invalid_source_grade`, `assumption_without_basis`, `likelihood_mismatch`, `vague_wording`, `judgement_without_evidence`, `high_confidence_without_corroboration`, `rests_only_on_unreviewed_derived_evidence`, `conclusion_language`, `recommendation_language`, `missing_section`, `missing_field`, `premature_final_status`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Clearance and point-in-time before ranking; one non-empty-string rule for reviewers |
| P5 Reversibility | yes | Additive; the store is local and deletable |
| P6 Observability | partial | Contract checker and validator codes; no runtime service |
| P9 Security & data | yes | Ignored store, refusal outside it, secret and email refusal, memory-gate scan |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | ignore rule, templates, gate edits, tracked-files check | T-001 |
| REQ-002 | `validate_store` | T-002 |
| REQ-003 | overlay rule in `validate_overlay` | T-001 |
| REQ-004 | candidate builders | T-003 |
| REQ-005 | `stage_to_local_store` | T-003 |
| REQ-006 | template entries | T-004 |
| REQ-007 | `retrieve` | T-005 |
| REQ-008 | `retrieve` not_found | T-005 |
| REQ-009 | segmenter use in `retrieve` | T-005 |
| REQ-010 | `retrieval_contract_violations` | T-006 |
| REQ-011 | `validate_documents` | T-006 |
| REQ-012 | `validate_product` | T-007 |
| REQ-013 | `releasable`, non-empty-string rule | T-007, T-008 |
| REQ-014 | `render_markdown` | T-007 |
| REQ-015 | agents, conventions, indexes | T-009 |
| NFR-001 | stdlib only, deterministic | T-010 |
| NFR-002 | docstrings, gaps | T-009 |
| NFR-003 | ignore, refusal, gate scan | T-001, T-003 |
| NFR-004 | gates, full suite | T-010 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Where private material lives | `knowledge_local/<domain>/` | One flat ignored folder; or outside the checkout only | Mirrors the committed packs; one ignore rule; the manifest's external mode remains available |
| Memory vocabulary | Existing types and scopes | New record types | The memory runtime is frozen and sufficient |
| Ranking statistics | Eligible passages only | Whole corpus | Whole-corpus statistics leak through scores |
| `not_found` | One response for every cause | Specific reasons | Specific reasons enable existence probing |
| Retriever | Lexical BM25 reference plus contract checker | Embeddings now | Embeddings are `0054`; the contract can be tested today |
| Reviewer test | `isinstance(str)` and non-empty | `str(x).strip()` | `str(None)` is the text 'None' |

## Validation Strategy

`tests/test_venture_knowledge.py` (store, candidates, staging, retrieval, leakage, contract
checker, product rules, agents), plus the added pack and tradecraft tests for the `None` fix;
pack validator; gates and the full suite.

## Rollout, Observability & Rollback

Additive. Rollback: delete the two modules, two agents, templates, tests, and revert the gate edits,
ignore rule, conventions additions, and doc edits.

## Open Questions

Whether real screening decisions may sit in a checkout; recommendation-term list; BLUF length.
