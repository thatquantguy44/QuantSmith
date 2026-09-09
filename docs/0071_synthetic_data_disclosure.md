# Synthetic Data Disclosure — Spec 0071 Reference Evidence

- **Artifact:** `examples/text_intelligence/`
- **Author:** QuantSmith spec `0071` maintainers
- **Last updated:** 2026-09-09
- **Reviewer / sign-off:** Fixture evidence is structurally approved by the
  recorded `spec0071` review objects; production and investment use are not
  approved.

## Priority Check

- [x] Actual sourced data was considered first.
- [x] Real text was intentionally not used because the acceptance target is an
      offline, redistributable contract fixture with no license, entitlement,
      privacy, or revision ambiguity.

## Disclosure Table

| Location (section / chart / field) | What's synthetic | Why real data wasn't used | Generation method | Real-data follow-up |
| --- | --- | --- | --- | --- |
| `deterministic_lexical_signal/documents/` and derived artifacts | Fictional issuer text, timestamps, entity/instrument mapping, task outputs, and signal | Public or vendor bodies would add license and availability assumptions unrelated to contract validation | Fixed strings and timestamps in `generate_reference_examples`; deterministic normalization and lexical rules; no random sampling | Register and approve each real source, availability policy, license, and promotion policy before ingestion |
| `fixture_backed_retrieval_generation/documents/`, `fixtures/`, vectors, tasks, and signal | Fictional text, model response, four-dimensional vectors, retrieval ranks, training placeholder, and signal | No provider, model weights, vector backend, or licensed corpus is approved for this foundation slice | Fixed fixture response; SHA-256-derived four-value vectors; deterministic ranks; no live call or training | Implement live retrieval under spec `0054`; approve provider/model/source policies in a separate consumer spec |

## Traceability

Every artifact is hash-linked by `text_intelligence_manifest.json`. The matching
spec-`0070` run envelope records prompt, context, assumptions, evaluation, audit
events, expected outputs, and replay classification. Source metadata resolves to
`sources/text_intelligence_fixture.yml`.

## Open Items

- Replace fixtures only in a bounded consumer spec with registered sources,
  source-specific point-in-time rules, approved licenses and entitlements, and
  production evaluation thresholds.
