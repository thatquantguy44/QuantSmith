# Venture & Non-Traditional Intelligence Pack

Spec: `specs/0083-venture-intelligence-foundation/`. Standard:
`instructions/venture_intelligence.md`. Status: **draft structural contract** —
nothing here is reviewed by a named person yet, and many records carry
`citation: "unverified"` on purpose (NFR-004).

| File | Holds |
| --- | --- |
| `taxonomy.json` | Entity and relationship types; people only as public professional roles |
| `conventions.json` | Fact-record contract, data-time and bias contracts, valuation and fund-metric formulas, source/confidence grading, multilingual normalization rules, prohibited source classes |
| `channels.json` | Ten non-traditional signal channels with lead time, bias, deception risk, licensing, point-in-time statement |
| `models.json` | Seven model families (catalog only; no trained models) |
| `workflows.json` | Five workflows with decision-path classes and review gates |
| `coverage.json` | Agent roster (built and planned), the child-spec roadmap `0084`–`0092` |
| `gaps.json` | Known unknowns with severity and owning spec |
| `glossary.json` | Terms; the dictionary section in `agentic_dictionary.md` is generated from it |
| `golden_cases.json` | Synthetic deterministic cases: dilution, fund metrics, IRR, confidence, grades, 万/亿, Buddhist and ROC years, locale numbers, survivorship, missing `known_at` |

## Validate

```sh
PYTHONPATH=src python3 -m quantsmith.pipelines.venture_pack
PYTHONPATH=src python3 -m pytest tests/test_venture_pack.py -q
```

The validator checks referential integrity, governance invariants (non-analytic
workflows are decision-support-only with named review), citation discipline, and
recomputes every golden case. It does **not** certify that a convention or a
channel claim is correct; that needs named human review.

## Adopter-local overlay

Copy `config/venture_overlay.example.yml` to `/venture_overlay.yml` (gitignored).
`validate_overlay` refuses an overlay that enables a prohibited source class or
holds a secret-like value. Real database evaluation notes live in the gitignored
`docs/venture_database_recommendations.md`.
