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
| `workflows.json` | Five workflows with decision-path classes and review gates; a workflow's class must cover its strictest agent |
| `coverage.json` | Agent roster (built and planned, each with a decision-path class) and the child-spec roadmap `0084`–`0092` plus `0094` |
| `gaps.json` | Known unknowns with severity and owning spec |
| `glossary.json` | Terms; the dictionary section in `agentic_dictionary.md` is generated from it |
| `golden_cases.json` | Synthetic deterministic cases: dilution, fund metrics, IRR, confidence, grades, 万/亿/萬/億/억/조/lakh/crore, Buddhist, ROC, and Japanese era years, locale numbers (id, vi, ru), survivorship, missing `known_at` |

Companion code: `src/quantsmith/pipelines/venture_pack.py` (validator and
normalization helpers), `venture_ingestion.py` (point-in-time and entity resolution),
`venture_fund_analytics.py` (multiples, XIRR, J-curve, PME, mark flags, simulation), `venture_tradecraft.py` (grades, corroboration, hypotheses, ownership). Companion
agents: `agents/venture_intelligence/`. Sources: `sources/` (eleven venture entries).

## Validate

```sh
PYTHONPATH=src python3 -m quantsmith.pipelines.venture_pack
PYTHONPATH=src python3 -m pytest tests/test_venture_pack.py -q
```

The validator checks referential integrity, governance invariants (non-analytic
workflows are decision-support-only with named review), citation discipline, and
recomputes every golden case. It does **not** certify that a convention or a
channel claim is correct; that needs named human review.

## Review sign-off

Every reviewable record carries `review_status` (`draft` | `reviewed` |
`superseded` | `retired`) and `review`. To sign a record off, set
`review_status: "reviewed"` and fill `review` with `reviewer`, `review_date`
(ISO), and `scope`. A reviewed record may not still cite `unverified` unless
`review.accepts_unverified` is true. The validator prints the current counts.

## Adopter-local overlay

Copy `config/venture_overlay.example.yml` to `/venture_overlay.yml` (gitignored).
`validate_overlay` refuses an overlay that enables a prohibited source class or
holds a secret-like value. Real database evaluation notes live in the gitignored
`docs/venture_database_recommendations.md`.
