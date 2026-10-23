# SQL Composer Tasks

## Reviewed Reuse

Input: a no-governed-match question and exact parameters.

Output: the unchanged reviewed query, evidence citation, and verification token.

## Bounded Adaptation or Generation

Input: a question with lower-confidence reviewed evidence or no eligible hit.

Output: a catalog-constrained candidate with path provenance and independent
verification; generated SQL remains outside retrieval.

## Verification Refusal

Input: a candidate that fails a deterministic check.

Output: escalation with the stable finding code; no execution and no policy
weakening.
