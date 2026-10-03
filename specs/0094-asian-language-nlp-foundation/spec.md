# Spec: Asian-Language NLP Foundation

- **ID:** 0094-asian-language-nlp-foundation
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:**
- **Last updated:** 2026-10-02

> WHAT and WHY only. Child of `0083-venture-intelligence-foundation`; builds on `0071` (governed text intelligence) and the `0084`/`0085`/`0086` regional agents. Number `0093` is taken by another agent.

## Problem & Context

The venture agents promise source-anchored extraction from start-up documents in
Mandarin (Simplified and Traditional), Japanese, Korean, Thai, Vietnamese,
Bahasa Indonesia/Malay, Filipino, Russian, Kazakh and Uzbek, and South Asian
business English. Today that promise is a contract only. The `0071` runtime
records a document's language but tokenizes on whitespace
(`unicode-whitespace-v1`), which does not segment Chinese, Japanese, or Thai;
nothing detects language or script; nothing turns `3.5亿元`, `2024年3月`,
`2567`, or `2024년` into structured values with spans; and there is no
evaluation set for any Asian language (`gap.low_resource_languages`). Without a
deterministic, testable baseline, any LLM-based extraction in these languages
cannot be checked, and quality would silently be reported at English-like levels.

## Goals

- A dependency-free **language and script identification** baseline that is honest about short and mixed text.
- A **segmentation** baseline for unspaced scripts, with a defined slot for a dictionary segmenter or model supplied through the `0071` capability profile.
- **Rule-based extraction** of amounts, currencies, dates, and fiscal periods in each in-scope language into structured values that keep the verbatim span and character offsets.
- **Synthetic evaluation sets** per language with per-language reporting, never pooled.
- A clear **boundary** between deterministic baseline output and LLM-derived output, with a comparison harness.

## Non-Goals

- No model training, fine-tuning, or embedding generation.
- No translation, transliteration, or OCR.
- No live LLM, API, or data-source call; no real documents or entities (all fixtures synthetic, `0025`).
- No named-entity recognition for company or person names beyond legal-form markers (entity matching stays in `entity_resolution`).
- No legal interpretation of extracted clauses.
- No claim that rule-based extraction is complete: it is a checkable baseline, not a replacement for review.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall identify the dominant script and a ranked list of candidate languages for a text using Unicode blocks, kana/hangul/Thai presence, Vietnamese-specific letters, and function-word lists, returning `undetermined` (with reasons) for text below a stated length or with mixed scripts, and shall never return a language it cannot support with the stated evidence. | must |
| REQ-002 | The SDK shall distinguish Simplified from Traditional Chinese on a stated character-set heuristic, report the evidence count, and return `zh` undetermined-variant when the evidence is insufficient. | must |
| REQ-003 | The SDK shall provide a segmentation baseline that uses whitespace tokens for spaced scripts and character n-grams for Han, kana, and Thai text, records a tokenizer identifier and version, and exposes a segmenter slot that accepts a function declared through a `0071` capability profile without changing callers. | must |
| REQ-004 | The SDK shall extract monetary amounts, currencies, dates, era years, and fiscal-period statements from text in each in-scope language into structured values, each carrying the verbatim span, character start and end offsets, the language, the normalization rule ID, and `method: rule`. | must |
| REQ-005 | Extraction shall reuse the normalization conventions in `knowledge/venture_intelligence/conventions.json` (units, eras, locales, currency symbols) without redefining them, and shall flag rather than guess any ambiguous symbol, unit, era, or separator. | must |
| REQ-006 | The SDK shall verify that for every extraction `text[start:end]` equals the recorded span, and shall reject any extraction that fails this check. | must |
| REQ-007 | The SDK shall ship synthetic evaluation sets with at least a stated minimum number of labelled cases per in-scope language and per extraction type, each marked synthetic. | must |
| REQ-008 | The SDK shall compute precision, recall, and exact-match per language and per extraction type, shall report them separately, and shall refuse to publish a pooled score that hides a language below a stated threshold. | must |
| REQ-009 | The SDK shall define an LLM-comparison harness that takes baseline extractions and externally supplied model extractions for the same text, reports per-language agreement and disagreements, labels model output `derived: true`, and never overwrites a baseline value with a model value. | must |
| REQ-010 | The SDK shall require that any model-derived extraction carries its model and prompt provenance through the `0070` envelope and names a bilingual human reviewer before it informs a decision, and shall record this boundary in the `multilingual_document_nlp` agent contract. | must |
| REQ-011 | The SDK shall update the gap register: close or re-own `gap.low_resource_languages`, and add gaps for language-identification accuracy on short text and for segmentation quality without a dictionary. | should |
| REQ-012 | The SDK shall document, per language, the known failure modes of the baseline (for example unspaced text, mixed scripts, numerals written in words, vertical or full-width forms), and shall normalize full-width digits and punctuation before extraction while keeping original offsets. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism | Identical input produces identical output; standard library only. |
| NFR-002 | Span integrity | 100% of extractions satisfy `text[start:end] == span` on the evaluation sets. |
| NFR-003 | Honesty | Every reported metric is per language with its sample size; no claim of general accuracy. |
| NFR-004 | Data provenance | All fixtures synthetic and disclosed per `0025`; no real document or entity. |
| NFR-005 | Gates | `spec`, `agent-catalog`, `handoff-sync`, `doc-counts` pass and no existing test regresses. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given short, mixed-script, and clear single-language samples in each in-scope language, when identified, then clear samples return the correct script and language, and short or mixed samples return `undetermined` with reasons. | REQ-001 |
| AC-002 | Given Simplified-only, Traditional-only, and shared-character Chinese samples, when classified, then the first two are labelled and the third is undetermined-variant with evidence counts. | REQ-002 |
| AC-003 | Given Han, kana, Thai, and spaced-script text, when segmented, then unspaced scripts yield character n-grams and spaced scripts yield whitespace tokens, the tokenizer ID and version are recorded, and a supplied segmenter function replaces the baseline without changing the caller. | REQ-003 |
| AC-004 | Given synthetic sentences containing amounts, currencies, dates, era years, and fiscal statements in each in-scope language, when extracted, then each is returned with span, offsets, language, rule ID, and `method: rule`. | REQ-004 |
| AC-005 | Given an ambiguous symbol (such as 兆), an unknown unit, or an unresolved separator, when extracted, then the item is flagged ambiguous and carries no normalized value. | REQ-005 |
| AC-006 | Given a corrupted offset, when verified, then the check rejects the extraction. | REQ-006, NFR-002 |
| AC-007 | Given the evaluation sets, when counted, then each in-scope language meets the stated minimum per extraction type and every case is marked synthetic. | REQ-007, NFR-004 |
| AC-008 | Given the metrics report, when generated, then it lists each language and extraction type separately with sample size, and refuses to publish a pooled score when a language is below threshold. | REQ-008, NFR-003 |
| AC-009 | Given baseline and model extractions that disagree, when compared, then the harness reports the disagreement per language, labels model output derived, and leaves the baseline value unchanged. | REQ-009 |
| AC-010 | Given the `multilingual_document_nlp` agent contract and the harness, when read, then the provenance and bilingual-reviewer requirements are stated. | REQ-010 |
| AC-011 | Given the gap register, when read, then the low-resource-language gap is re-owned to this spec and the two new gaps exist. | REQ-011 |
| AC-012 | Given full-width digits and punctuation, when extracted, then values are normalized and offsets still point at the original text. | REQ-012 |
| AC-013 | Given repeated runs on the same inputs, when compared, then outputs are byte-identical. | NFR-001 |
| AC-014 | Given the repository, when gates and the full suite run, then no gate has findings and no previously passing test fails. | NFR-005 |

## Data & Dependencies

Depends on `0071` (documents, tokenizer and capability profiles, evidence labels),
`0070` (envelope, provenance), `0083` conventions (`conventions.json`), `0084`/`0085`/`0086`
(languages in scope), `0025` (synthetic data). Inputs are caller-supplied text.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Language ID misfires on short text. | Wrong rules applied. | `undetermined` below a length; reasons recorded. |
| RISK-002 | Character n-grams are mistaken for words. | Poor lexical features. | Tokenizer ID recorded; segmenter slot; gap recorded. |
| RISK-003 | Rules extract the wrong number from words or tables. | Mis-scaled figure. | Span integrity, ambiguity flag, per-language evaluation. |
| RISK-004 | Synthetic cases are too easy; scores overstate quality. | False confidence. | Per-language reporting, known-failure-mode list, and an explicit statement that scores apply only to the synthetic sets. |
| RISK-005 | Model output silently replaces rule output. | Unauditable change. | Harness never overwrites; `derived: true`; reviewer required. |
| RISK-006 | Simplified/Traditional heuristic labels a Japanese text as Chinese. | Wrong language. | Kana presence takes precedence; evidence counts reported. |

## Assumptions & Open Questions

- Assumption: a dependency-free baseline is worth shipping first because it is checkable and pins the interface a dictionary segmenter or model must meet.
- Open question: which dictionary segmenters or multilingual models the adopter may license, to be declared later through a `0071` capability profile.
- Open question: minimum evaluation-set size per language (a starting value is set in the plan).

## Exceptions

None.
