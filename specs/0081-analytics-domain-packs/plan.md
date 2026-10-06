# Plan: Analytics Domain Packs for Financial Services

- **Spec:** 0081-analytics-domain-packs (`spec.md`)
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-06

> HOW. This plan requires an approved `spec.md`. Every requirement in the spec
> appears in the traceability matrix below.

## Approach

Packs are data, not code: one JSON file per pack under
`knowledge/analytics_packs/`, so a domain owner can review and edit one without
touching Python. A single stdlib module,
`src/quantsmith/pipelines/analytics_packs.py`, loads, validates, and selects
them, and exposes the two semantic helpers `0080` needs — `can_sum` and
`suppressed_insights`.

Additivity is the load-bearing idea. Most analytic mistakes in finance are
sums or averages that should not happen (VaR across desks, balances across
days, PDs across obligors). Declaring each metric's class once, and deriving
both "may I sum this?" and "may I show contributors?" from it, prevents those
mistakes by construction instead of relying on a narrative reviewer.

Golden cases make each pack self-checking: the validator recomputes each
basis-point move and ratio, and checks each additivity claim against the
metric's declared class, so a pack cannot contradict itself.

## Architecture & Components

```
sources/*.yml  domain: [...]  ──┐
                                 ▼
knowledge/analytics_packs/*.json ──▶ analytics_packs.load_packs()
                                        │ validate_catalog()  → findings (error | info)
                                        │ select_packs(tags)  → Selection(packs, unmatched, conflicts, all_reviewed)
                                        │ can_sum(), suppressed_insights()
                                        ▼
                               0080 nl_analytics (interpret, insights, caveats, write-back gate)
```

| Component | Responsibility |
| --- | --- |
| `knowledge/analytics_packs/<pack_id>.json` | One pack (40 at launch across seven families). |
| `knowledge/analytics_packs/README.md` | Contract, rules, and the catalog table (validator checks every pack is listed). |
| `analytics_packs.validate_pack` / `validate_catalog` | Structure, vocabularies, rate-like additivity rule, insight-rule and caveat targets, golden cases, review completeness, agent and `builds_on` existence, family coverage, README sync. |
| `analytics_packs.select_packs` | Tag intersection, deterministic order, term conflicts, write-back eligibility. |
| `analytics_packs.coverage_report` / CLI | Counts by family and status; uncovered source tags. |
| `analytics_packs.resolve_packs` / `PackSource` | Whole-catalog resolution: explicit root, else local `knowledge/analytics_packs/` under the working directory, else the bundled copy; returns the packs and their source (kind, location, version, content hash). |
| `setup.py` `build_py` | Copies `knowledge/analytics_packs/*.json` byte for byte into `quantsmith/_bundled/analytics_packs/` in the build; fails when it finds none. `MANIFEST.in` carries the catalog into the sdist so a wheel built from the sdist bundles it too. |
| `tests/test_analytics_packs.py` | Acceptance tests naming each `AC-*`. |

## Interfaces & Data Contracts

See the field table in `knowledge/analytics_packs/README.md` (the contract's
single home). Key rules:

- `additivity` → (sum across dimensions, sum across time): additive (yes, yes),
  semi-additive (yes, no), non-additive (no, no).
- Rate-like units (`pct`, `bps`, `ratio`, `multiple`, `index`, `score`,
  `years`, `days`) are non-additive unless `additivity_rationale` is present.
- `suppressed_insights(pack, metric)` = `{contributor}` if non-additive, plus
  every `suppress_kinds` of each rule whose `applies_to` glob matches.
- `Selection.all_reviewed` is the write-back gate `0080` REQ-016 reads.
- Resolution order (REQ-013): an explicit root is used alone and must hold
  packs; otherwise `./knowledge/analytics_packs/` if it holds any JSON;
  otherwise the bundle — `quantsmith/_bundled/analytics_packs/` in an
  installed wheel, or the repository's own `knowledge/analytics_packs/` when
  running from a source tree or an editable install (where `build_py`'s copy
  is not on the import path). The content hash is SHA-256 over each file's
  name and bytes in file-name order, so a local copy of an unmodified bundle
  hashes the same.
- Bundled packs load without strict validation: their `reviewer_agents` and
  `builds_on` paths point into the repository, which an installed package does
  not have. CI validates the catalog (AC-001) before any build.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Additivity classes forbid invalid sums and contributor insights; golden cases recomputed on every validation. |
| P5 Reversibility | yes | Packs are data files; removing or reverting one returns `0080` to generic behavior. Review status can be revoked by edit. |
| P6 Observability | yes | Coverage report (status, uncovered tags) is part of the CLI; findings are explicit. |
| P9 Security & data | yes | No company data or credentials; packs can only restrict, never widen access (REQ-011). |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | Pack JSON contract + README field table | T-001 |
| REQ-002 | 40 packs across seven families | T-002 |
| REQ-003 | `UNITS`, `ADDITIVITY_RULES`, rate-like rule, `can_sum`, `suppressed_insights` | T-001, T-003 |
| REQ-004 | `select_packs`, conflicts | T-004 |
| REQ-005 | `review` block, `is_reviewed`, `Selection.all_reviewed` | T-003, T-004 |
| REQ-006 | reviewer-agent existence check | T-003 |
| REQ-007 | `builds_on` existence check; credit/STM references | T-002, T-003 |
| REQ-008 | `_check_golden` | T-003 |
| REQ-009 | `validate_catalog`, CLI | T-003, T-005 |
| REQ-010 | `uncovered_source_domains`, `coverage_report` | T-005 |
| REQ-011 | contract has suppress-only fields; `suppressed_insights` only adds | T-001, T-003 |
| REQ-012 | `review_sheet`, `mark_reviewed`, `FAMILY_REVIEWERS`, CLI flags | T-008 |
| NFR-001 | stdlib only; sorted loading | T-003, T-006 |
| NFR-002 | content scan test | T-006 |
| REQ-013 | `resolve_packs`, `PackSource`, bundled data dir | T-009, T-010 |
| NFR-003 | `schema_version` check | T-003 |
| NFR-004 | `setup.py` `build_py` copy + empty-catalog failure; `MANIFEST.in` | T-010 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Pack format | JSON, one file per pack | YAML; one big file | Stdlib parses JSON; one file per pack keeps review diffs small and ownable. |
| Granularity | 40 packs by business area | ~7 family-level packs | Family packs would mix incompatible conventions (deposit betas and VaR). |
| Selection key | Existing `sources/*.yml` domain tags | New per-dataset pack field | Reuses `0027`; no second registry to keep in sync. |
| Draft packs in chat | Allowed with caveat | Blocked until reviewed | Blocking makes 40 packs useless until all are reviewed; the caveat keeps chat honest. |
| Deep domains | Reference `knowledge/credit_risk` and `short_term_markets` | Copy their rules | One source of truth. |
| Distribution | Bundled defaults copied at build time; local catalog shadows the whole bundle | Bundle only; repo only; per-pack merge; committed mirror under `src/` | Bundle-only makes `--mark-reviewed` impossible for installed users and keeps write-back closed; repo-only gives installed users nothing; per-pack merge makes review status ambiguous; a committed mirror is a second source of truth to keep in sync. |

## Validation Strategy

`tests/test_analytics_packs.py` runs the validator on the committed catalog
(AC-001, AC-002, AC-008–AC-012) and on mutated in-memory copies to prove each
rejection actually fires (AC-003, AC-007, AC-010, AC-011). Selection and
semantic helpers are tested directly (AC-004–AC-006, AC-013). An import and
content scan covers NFR-001/NFR-002 (AC-014).

## Rollout, Observability & Rollback

Ship all packs `draft`. `0080` shows a caveat whenever it applies a draft pack
and blocks write-back. Review proceeds pack by pack; each review is one
reviewed diff to one JSON file. Rollback: revert the file or set status back to
`draft`.

## Open Questions

- ~~Named reviewer per family~~ — resolved 2026-09-24: the owner reviews all seven families.
- ~~Adopter override mechanism~~ — resolved 2026-10-06: whole-catalog shadowing (REQ-013).
