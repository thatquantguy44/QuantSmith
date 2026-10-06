# Spec: Analytics Domain Packs for Financial Services

- **ID:** 0081-analytics-domain-packs
- **Status:** Draft
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** — (pending owner review)
- **Last updated:** 2026-10-06

> WHAT and WHY only. Implementation lives in `plan.md`.

## Problem & Context

Spec `0080` turns a natural-language question into a governed chart and
interpretation. Without domain knowledge it treats every dataset the same way,
and in financial services the same arithmetic gives wrong answers in different
places: yield moves belong in basis points, not percent change; PDs, VaR, and
PFE must never be summed; balances are summed across desks but never across
days; exchange-rate direction depends on quoting convention; revised macro data
needs its as-of vintage; assets under management move with markets, not only
with flows.

The repository already holds most of the ingredients but nothing joins them:
every `sources/*.yml` entry declares `domain:` tags (`0027`); two deep, reviewed
knowledge packs exist (`knowledge/credit_risk/`, `knowledge/short_term_markets/`);
and domain agents exist for asset classes, credit, securities financing, risk,
portfolio management, and economics.

The owner asked for a comprehensive set of pluggable packs spanning the full
range of areas in a bank or financial-services firm, selected by the type of
data, so `0080` reads each dataset with the right domain knowledge.

## Goals

- One declared pack contract that `0080` consumes, so domain knowledge plugs in
  by data type without code changes.
- A catalog that spans the firm front to back: business lines, markets, risk,
  finance and treasury, control and compliance, operations, and cross-cutting
  analytics.
- Metric semantics that prevent the commonest analytic errors by construction:
  a declared unit and additivity class per metric.
- Honest review status: packs ship as drafts, usable in chat with a caveat, and
  eligible for database write-back only once a named person reviews them.

## Non-Goals

- **Reviewing the packs.** This spec drafts them from general, public industry
  conventions; review by named domain owners is separate, tracked work.
- **Replacing the deep knowledge packs.** `knowledge/credit_risk/` and
  `knowledge/short_term_markets/` stay authoritative; analytics packs reference
  them in `builds_on`.
- **Firm-specific definitions or data.** Adopters extend or override packs in
  their own repository; no company data enters this one.
- **Legal, accounting, tax, or regulatory advice.**
- **New agents.** Every pack routes review to an agent that already exists.
- **Text and document sources.** Tags such as `market_commentary` and
  `supervisory_guidance` belong to `0071`/`0077`, not tabular analytics.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The SDK shall define an analytics domain pack contract (`schema_version` `0081.1`): identity, family, selecting source domains, `builds_on` references, reviewer agents, dimensions, metrics, conventions, insight rules, caveats, chart conventions, golden cases, and review status. | must |
| REQ-002 | The SDK shall ship a catalog of packs covering all seven families — business lines, markets, risk, finance and treasury, control and compliance, operations, cross-cutting — and at minimum the areas listed in the Coverage table below. | must |
| REQ-003 | Every metric shall declare a unit from a fixed vocabulary and an additivity class (`additive`, `semi_additive`, `non_additive`) that determines whether it may be summed across dimensions and across time; a rate-like unit shall be `non_additive` unless the metric states an `additivity_rationale`. A non-additive metric shall never receive a contributor insight. | must |
| REQ-004 | Packs shall be selected for a dataset by intersecting the dataset's `sources/*.yml` `domain:` tags with each pack's `source_domains`, deterministically; a term that maps to different metrics in two selected packs shall be reported as a conflict for `0080` to clarify. | must |
| REQ-005 | Each pack shall carry a review status (`draft`, `in_review`, `reviewed`); `reviewed` shall require a named reviewer and an ISO review date. Only a selection whose packs are all `reviewed` is eligible to drive database write-back. | must |
| REQ-006 | Each pack shall name at least one existing reviewer agent; a reference to a nonexistent agent is a validation error. | must |
| REQ-007 | A pack that touches a domain with an existing deep knowledge pack or spec shall reference it in `builds_on`, and every `builds_on` path shall exist. | must |
| REQ-008 | Each pack shall carry machine-checkable golden cases (`bps_change`, `additivity`, `ratio`) that the validator verifies against the pack's own declarations and arithmetic. | must |
| REQ-009 | A standard-library validator shall check every pack and the catalog (unique ids, file-name match, family coverage, catalog README listing) and return findings, with a CLI that exits non-zero on any error. | must |
| REQ-010 | The validator shall report which `sources/*.yml` domain tags select no pack, as information. | should |
| REQ-012 | The SDK shall support review by family: a deterministic Markdown review sheet per family listing every pack, metric (with unit, additivity, and what it permits), convention, insight rule, caveat, chart convention, and golden case; and a command that records a named review on one pack at a time, refusing an empty reviewer, a non-ISO date, an unknown pack, or a pack that fails validation. | must |
| REQ-011 | Packs shall only restrict interpretation: insight rules suppress, caveats add, conventions constrain. No pack field can enable an insight, widen access, or override `0008` governance. | must |
| REQ-013 | The installed `quantsmith` package shall carry the catalog as read-only bundled defaults, so packs resolve without a repository checkout. A local catalog (`<root>/knowledge/analytics_packs/`, default root the working directory) shall take precedence over the bundled one as a whole catalog — never merged pack by pack. An explicitly named root with no packs, or no packs anywhere, shall be an error, not an empty catalog. Every resolution shall return its source: kind (`local` or `bundled`), location, package version, and a content hash of the catalog. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Determinism and dependencies | Standard library only; loading and selection are ordered by file name; identical inputs give identical findings and selections. |
| NFR-002 | Data handling | No company data, credentials, or personal data in any pack; conventions cite general public practice. |
| NFR-003 | Evolvability | The pack shape is versioned; a schema change bumps `schema_version` and the validator rejects mismatches. |
| NFR-004 | Distribution fidelity | The bundled catalog is a byte-identical copy of the repository catalog at build time; a build that finds no packs fails rather than shipping an empty bundle. The bundle is validated in CI, before it is built, not when it is loaded. |

## Coverage

| Family | Packs |
| --- | --- |
| Business lines | retail deposits; cards & consumer lending; mortgages & home lending; commercial & corporate banking; treasury & cash management; trade finance; investment banking; wealth & private banking; asset management; payments; custody & securities services; insurance |
| Markets | equities; rates & government bonds; credit markets; FX; commodities; derivatives & structured products; digital assets; short-term markets & funding; securities lending & prime brokerage; sales, trading & execution |
| Risk | credit risk; counterparty credit risk & XVA; market risk; liquidity risk; treasury/ALM & IRRBB; operational risk; model risk; climate & ESG risk |
| Finance & treasury | finance & performance management; regulatory capital & reporting |
| Control & compliance | AML & financial crime; fraud; consumer compliance & conduct |
| Operations | operations & settlement; collections & recovery |
| Cross-cutting | customer & marketing analytics; economics & macro; portfolio management & performance attribution |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the committed catalog, when validated, then there are no error findings and every pack has every required field at `schema_version` `0081.1`. | REQ-001, REQ-009, NFR-003 |
| AC-002 | Given the catalog, when checked against the Coverage table, then every listed area has a pack and all seven families are represented; removing every pack of one family produces a family-coverage error. | REQ-002 |
| AC-003 | Given a pack with a `pct` metric declared `additive` and no rationale, when validated, then an error names the metric; with a rationale, it passes. | REQ-003 |
| AC-004 | Given each additivity class, when `can_sum` is asked about dimensions and time, then additive is (yes, yes), semi-additive (yes, no), non-additive (no, no); and a non-additive metric's suppressed insights include `contributor`. | REQ-003, REQ-011 |
| AC-005 | Given domain tags `["macro", "fixed_income_rates"]`, when packs are selected, then `economics_macro` and `rates_fixed_income` are selected in file-name order; given an unknown tag only, then no pack is selected and the tag is reported unmatched. | REQ-004, NFR-001 |
| AC-006 | Given two selected packs that use one term for different metrics, when selected together, then the term is returned as a conflict. | REQ-004 |
| AC-007 | Given a pack set to `reviewed` without a reviewer or date, when validated, then it errors; given all-draft packs, when selected, then the selection is not eligible for write-back; given all-reviewed packs, then it is. | REQ-005 |
| AC-008 | Given a pack naming a nonexistent reviewer agent or `builds_on` path, when validated, then each produces an error; every committed pack names at least one existing agent. | REQ-006, REQ-007 |
| AC-009 | Given the credit and short-term-markets packs, when inspected, then their `builds_on` references `knowledge/credit_risk` and `knowledge/short_term_markets` respectively. | REQ-007 |
| AC-010 | Given golden cases with a wrong bps result, a wrong ratio, or an additivity claim contradicting the metric's class, when validated, then each errors; every committed pack has at least one golden case and all pass. | REQ-008 |
| AC-011 | Given the committed catalog, when the CLI runs, then it exits zero; given a catalog README missing a pack id, then an error names that pack. | REQ-009 |
| AC-012 | Given `sources/*.yml`, when coverage is reported, then only text/document tags remain uncovered and they are reported as `info`, never `error`. | REQ-010 |
| AC-013 | Given an insight rule, when applied, then it can only add suppressed kinds; the pack contract has no field that enables an insight kind or changes access level. | REQ-011 |
| AC-015 | Given any family, when its review sheet is generated twice, then the output is identical, names the assigned reviewer, and lists every pack id, metric, and item id of that family; an unknown family is rejected. | REQ-012 |
| AC-016 | Given a pack, when marked reviewed with a name and ISO date, then the file records status, reviewer, and date and the selection becomes write-back eligible; an empty name, a bad date, an unknown pack, or a pack with a validation error is refused and the file is unchanged. | REQ-012, REQ-005 |
| AC-017 | Given a wheel built from the repository, when it is inspected, then it contains every catalog JSON byte-identical to `knowledge/analytics_packs/`; and when it is imported from a directory with no local catalog, then packs resolve from the bundle with kind `bundled`, the package version, and the same content hash as the repository catalog. | REQ-013, NFR-004 |
| AC-018 | Given a local catalog with fewer packs than the bundle, when packs resolve from that root, then only the local packs are returned and the source kind is `local`; given no local catalog, then the bundled catalog is returned. | REQ-013 |
| AC-019 | Given an explicit root with no packs, when packs resolve, then it raises naming the searched directory and never falls back to the bundle; given a build source with no packs, then the build fails. | REQ-013, NFR-004 |
| AC-014 | Given the validator module, when its imports are scanned, then it imports only the standard library; given every pack, when scanned, then it contains no email address, credential-like token, or URL with credentials. | NFR-001, NFR-002 |

## Data & Dependencies

- `sources/*.yml` `domain:` tags (`0027`) — the selection key.
- `knowledge/credit_risk/` (`0072`) and `knowledge/short_term_markets/` (`0063`)
  — referenced, never redefined.
- Existing agents under `agents/` — reviewer routing only.
- Consumer: `0080` natural-language analytics (its domain-pack requirements).
- No private data; conventions are public, general practice.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A drafted convention is wrong for a firm or jurisdiction. | Misleading answers. | Draft status shown as a caveat in chat; write-back requires named review (REQ-005). |
| RISK-002 | Breadth outruns review capacity; 40 packs stay draft indefinitely. | Write-back never enabled. | Coverage report shows status per pack; review can proceed one pack at a time. |
| RISK-003 | Overlapping packs disagree about a term. | Wrong metric chosen. | Conflicts reported; `0080` clarifies rather than picks (REQ-004). |
| RISK-004 | Analytics packs drift from the deep packs they build on. | Two sources of truth. | `builds_on` references plus conventions deferring to the deep pack (REQ-007). |
| RISK-005 | Packs are mistaken for regulatory or accounting guidance. | Misuse. | Non-Goals and README state they are informational. |
| RISK-006 | Bundled defaults change with each package release, so the same question can be answered differently after an upgrade. | Silent drift in answers. | Every resolution records source, version, and content hash (REQ-013) and `0080` reports it; teams that need stability pin the version or keep a local catalog. |
| RISK-007 | Someone edits or marks reviewed a bundled pack inside `site-packages`. | Review lost on upgrade; sign-off not traceable. | Bundled packs are read-only defaults; `--mark-reviewed` writes only to a local catalog under `--root`. |

## Assumptions & Open Questions

- Assumption: U.S.-first conventions where they differ by jurisdiction, as in
  `0063`/`0072`.
- Resolved (owner, 2026-09-24): Joshua Lutkemuller, CFA reviews all seven
  families, pack by pack, using the review sheet and `--mark-reviewed`
  (REQ-012). Recorded in `analytics_packs.FAMILY_REVIEWERS`.
- Resolved (owner, 2026-10-06): adopters override by shadowing the whole
  catalog — a local `knowledge/analytics_packs/` replaces the bundled packs
  entirely (REQ-013). Per-pack merging was rejected: mixing a team's reviewed
  packs with newer bundled drafts would make an answer's review status
  ambiguous. A declared overlay field stays a possible later extension.

## Exceptions

None.
