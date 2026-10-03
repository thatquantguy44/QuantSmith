# Spec: Venture Knowledge Integration and Product Writers

- **ID:** 0092-venture-knowledge-integration-and-product-writers
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-03

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`. Reuses `0048`/`0049`/`0058` (workflow memory), `0052`/`0053`/`0056` (MCP resource servers), `0071` (text intelligence), and `0094` (Asian-language segmentation) without changing them. Live semantic search remains the reserved `0054`.

## Problem & Context

The venture work produces analyses but is not connected to the repository's knowledge
systems: nothing says where real, private material lives, how a lesson about a data source
becomes durable memory, how an agent retrieves cited passages without seeing what its
clearance forbids, or how findings become a brief or memo a reader can trust. The risks are
specific. A committed folder gets a real screening note. A retriever ranks on statistics that
include restricted documents, so even a score leaks. A brief states a claim nobody can trace.
A memo drifts into recommending an investment. A "reviewer" field quietly reads `None` as a name.

## Goals

- A dedicated, gitignored private store per knowledge domain, `knowledge_local/<domain>/`, paired with the committed pack of the same name, with its own access level.
- Durable lessons through the existing memory write path (stage, then a named human promotes), never auto-promoted, never written outside the private store.
- A retrieval contract (clearance first, point-in-time, eligible-only ranking, cited spans or `not_found`) that the future `0054` server can be checked against.
- Brief and memo writers whose drafts are validated: cited, graded, separated, calibrated, classified, and releasable only by a named human.

## Non-Goals

- No live semantic search, embeddings, or vector index (`0054`); the retriever here is a lexical reference.
- No change to `workflow_memory`, `access_control`, the MCP servers, or `text_intelligence`.
- No real documents, notes, or decisions in the repository; every fixture is synthetic.
- No judgement of whether a cited passage truly supports its claim; the validator checks form, a human checks truth.
- No release, approval, or recommendation by any agent.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall gitignore `/knowledge_local/` (root-anchored), ship placeholder templates under `templates/knowledge_local/`, exclude the folder from the `docs-link` gate, include it in the `memory` gate's secret and PII scan when present, and fail a test if any file under it is tracked. | must |
| REQ-002 | Each `knowledge_local/<domain>/` shall declare `store.yml` with a domain equal to its folder name, an access level (public, internal, or restricted), and a pseudonymous owner handle; the validator shall reject a missing manifest, a mismatched domain, an unknown level, an email or name as owner, and the unedited placeholder owner. | must |
| REQ-003 | The venture overlay's `store_root` shall be accepted only under `knowledge_local/`. | must |
| REQ-004 | The SDK shall build `0049` candidates for source quirks (from a source entry's `quality.known_issues`), channel lessons, and screening decisions, scoped, typed, and evidenced for the existing memory vocabulary; screening decisions shall always be `restricted`; a statement with a credential, an email address, or over 500 characters shall be refused. | must |
| REQ-005 | The SDK shall stage candidates only into `knowledge_local/<domain>/memory`, shall refuse any other target, shall promote nothing, and shall stage idempotently. | must |
| REQ-006 | The SDK shall document memory-manifest and knowledge-sources entries that point the existing memory runtime, the `sources` MCP authority, and the `knowledge` gate at the local store. | must |
| REQ-007 | The SDK shall retrieve cited passages for a query with a required caller clearance: documents above the clearance, not yet known at `as_of`, superseded, or credential-bearing are dropped before any scoring; ranking statistics come from the eligible passages only; each passage carries a citation identifier `document:start-end`, offsets that slice back to the text, content and passage hashes, `known_at`, source grade, and access level. | must |
| REQ-008 | Retrieval shall return `not_found` with no passages when nothing eligible matches, and that response shall be identical whether the matching document is absent, future-dated, superseded, or restricted; no response shall mention or count dropped documents. | must |
| REQ-009 | Retrieval shall segment queries and passages with the `0094` segmenter so Chinese, Japanese, and Thai text is searchable, and shall be deterministic. | must |
| REQ-010 | The SDK shall provide a contract checker that reports any retriever output that exceeds the caller's clearance, was not known at `as_of`, has inconsistent citation identifiers or offsets, mentions dropped documents, or has an impossible status; the future `0054` server shall be required to pass it. | must |
| REQ-011 | The SDK shall validate documents at load, over all documents and never inside a caller's query, for duplicate identifiers, unknown access levels, credential-shaped text, and non-ISO dates. | must |
| REQ-012 | The SDK shall validate intelligence briefs and investment memos against rules held in `conventions.json`: required non-empty sections; every evidence item cited with citations that resolve, were known at the product date, and do not exceed the product's classification; a valid source grade; assumptions with a basis; judgements whose likelihood word matches their probability, with an evidence-confidence level, supporting evidence, and no unqualified hedging; high confidence only for a corroborated claim; no judgement resting only on unreviewed derived evidence; no conclusion language; and, for a memo, a named decision owner and no recommendation, approval, or rejection language. | must |
| REQ-013 | A product shall be releasable only when it validates and a named human reviewer is recorded; the writers shall never set the reviewer, and `None`, empty, or non-string values shall never count as a name anywhere in the venture sign-off checks. | must |
| REQ-014 | The SDK shall render products deterministically, with a visible DRAFT banner while unreviewed, a sources section listing each cited passage's grade, date, and access level, and no reordering of sections. | must |
| REQ-015 | The SDK shall add the agents `intelligence_brief_writer` and `investment_memo_writer` with four contract files each and stated boundaries, mark them built, add them to the workflows, catalog, standard, group README, dictionary, and agent registry, and record the retrieval and product rules as reviewable draft records in the conventions. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Standard library only; identical inputs give identical outputs. |
| NFR-002 | Honesty | The validator states that it checks form, not truth; the retriever states that it is a lexical reference for `0054`. |
| NFR-003 | Privacy | No real note, decision, document, or personal address appears in the repository; the private store is never tracked. |
| NFR-004 | Gates | All gates with enforcement on pass and no existing test regresses. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the repository, when inspected, then `/knowledge_local/` is ignored, the four templates exist, the `docs-link` and `memory` gates reference the folder, and git tracks nothing under it; and an overlay `store_root` outside `knowledge_local/` is rejected. | REQ-001, REQ-003 |
| AC-002 | Given store manifests with a missing file, a wrong domain, an unknown level, a name or email owner, or the placeholder owner, when validated, then each is rejected, and a sound manifest passes. | REQ-002 |
| AC-003 | Given a source catalog entry, when candidates are built, then each known issue becomes a low-confidence quirk with a source-catalog evidence run; screening decisions are restricted; and credentials, emails, empty, and over-long statements are refused. | REQ-004 |
| AC-004 | Given a candidate, when staged, then it lands only under `knowledge_local/<domain>/memory`, is readable through the existing inbox loader, is not promoted, restages byte-identically, and any other target raises. | REQ-005 |
| AC-005 | Given the template entries, when parsed, then the memory manifest entry is external and restricted and the sources entry enables domain subfolders at restricted. | REQ-006 |
| AC-006 | Given a corpus, when a query runs, then passages slice back to the text, citation identifiers match their offsets and documents, hashes and metadata are present, and repeated runs are identical. | REQ-007, NFR-001 |
| AC-007 | Given a Chinese query and an internal filing, when searched at internal and public clearance, then the segmenter finds it at internal and nothing is found at public. | REQ-009 |
| AC-008 | Given no clearance, an empty query, or no match, when retrieval runs, then a missing clearance raises, and nothing-found returns `not_found` with no passages. | REQ-007, REQ-008 |
| AC-009 | Given a restricted, future-dated, or superseded match only, when a lower-clearance caller searches, then the response equals the response over an empty corpus, and adding many restricted documents does not change a lower caller's passages or scores. | REQ-008 |
| AC-010 | Given future-dated, superseded, and credential-bearing documents, when searched, then they are excluded, and corpus validation reports duplicates, credential text, unknown levels, and bad dates. | REQ-007, REQ-011 |
| AC-011 | Given good and corrupted retriever output, when checked, then good passes and over-clearance, future-known, bad identifiers or offsets, dropped-document mentions, and impossible statuses are each reported. | REQ-010 |
| AC-012 | Given a sound brief and memo, when validated and rendered, then there are no errors, rendering is deterministic with a DRAFT banner and a sources section, and release requires a named reviewer. | REQ-012, REQ-013, REQ-014 |
| AC-013 | Given drafts with an uncited, unresolvable, future-known, over-classified, or ungraded claim, an assumption without basis, a mismatched, vague, unsupported, or uncorroborated high-confidence judgement, derived-only support, conclusion language, memo recommendation language, a missing decision owner, a final status without a reviewer, or `None` as a reviewer, when validated, then each is rejected with its code. | REQ-012, REQ-013 |
| AC-014 | Given the coverage matrix, agents, workflows, indexes, registry, and conventions, when read, then the two agents are built with four files and boundaries, the rules are draft records, the pack validates, and a `None` reviewer, scope, date, or citation in the pack is rejected. | REQ-013, REQ-015 |
| AC-015 | Given the repository, when gates and the full suite run, then no gate has findings and no previously passing test fails. | NFR-004 |

## Data & Dependencies

Depends on `0083` (conventions, source grades, tradecraft), `0088` (`known_at`), `0090`
(corroboration, wording checks), `0094` (segmentation), and the existing memory, access-control,
and MCP modules. Inputs are caller-supplied.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Real private material is committed. | Disclosure. | Root-anchored ignore, a no-tracked-files test, and refusal to stage outside the store. |
| RISK-002 | Ranking statistics leak restricted content. | Existence or content inference. | Eligible-only statistics; a test that 25 added restricted documents change nothing. |
| RISK-003 | `not_found` reveals that a restricted match exists. | Existence probing. | Identical response for absent, future, superseded, and restricted. |
| RISK-004 | A product is trusted because it validated. | False assurance. | The validator documents that it checks form; a named human reviewer releases. |
| RISK-005 | `None` or an empty string is accepted as a reviewer. | Unreviewed release. | One non-empty-string rule applied everywhere; tests for each sign-off path. |
| RISK-006 | A memo drifts into advice. | Pre-empts the committee. | Recommendation lint, a named decision owner, and the agent boundary. |
| RISK-007 | The lexical retriever is mistaken for the live server. | Overstated capability. | Gap recorded; contract checker defined for `0054`. |

## Assumptions & Open Questions

- Assumption: a lexical reference plus a contract checker is the right first step, because the contract is what `0054` must satisfy and the check can run now.
- Open question: whether counsel permits real screening decisions in a developer checkout, or requires the memory manifest's external mode.
- Open question: the exact recommendation-term list and BLUF length the committee wants; both are data in `conventions.json`.

## Exceptions

None.
