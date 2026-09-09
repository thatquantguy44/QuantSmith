# Spec: Short-Term Markets Domain Foundation

- **ID:** 0063-short-term-markets-domain-foundation
- **Status:** Approved
- **Author:** Codex
- **Approver:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-09-09

## Problem & Context

QuantSmith has broad quant, optimization, and agent coverage, but its
short-term-markets expertise is not yet a coherent domain system. The current
securities-financing group has four agents; only securities lending (`0023`) and
financing-cost analysis (`0028`) have reference runtimes. Repo and collateral
remain contract-only, cash-product pricing is absent, and the source catalog
does not yet register the official benchmark, issuance, clearing, reporting,
and market-structure sources these workflows need.

The deeper issue is not simply missing code. Existing domain knowledge is spread
across agent prose and narrow models without one canonical contract for:

- which product, transaction, role, and lifecycle state a term refers to;
- whose economics a rate or cashflow describes;
- how a quote, day count, calendar, settlement rule, haircut, and margin amount
  are represented;
- when a fact, rule, market observation, or model assumption was knowable and
  effective; and
- what evidence makes an item reviewed expert knowledge rather than plausible
  prose.

That fragmentation creates predictable errors: repo specialness can be described
with the stock-loan sign, static basis-point cutoffs can masquerade as universal
market classifications, incompatible accrual bases can be combined silently,
and a financing rate observed after a trade begins can be applied retroactively.
Adding more agents before solving this would multiply the same ambiguity.

This spec establishes the shared **U.S.-first short-term-markets domain
foundation** that later pricing, lifecycle, data, and optimization specs must
consume. It is deliberately a knowledge and validation contract, not a mega-spec
that attempts to implement every model.

## Goals

- Create a canonical, versioned domain pack for repo/reverse repo, securities
  lending, collateral and margin, U.S. Treasury and approved institutional cash
  products, and their market-structure and regulatory context.
- Make economic viewpoint, cashflow sign, units, quotation method, day count,
  settlement, jurisdiction, and effective time explicit wherever ambiguity could
  change an answer or a model result.
- Separate stable mechanics, time-varying rules, market observations, and
  empirical/model claims so point-in-time use is correct by construction.
- Define an authority and review model that distinguishes official sources,
  industry standards, vendor documentation, internal procedures, and analyst
  interpretation.
- Inventory current agents, instructions, runtimes, sources, and tests against a
  capability matrix; record rather than hide gaps and assign each to a bounded
  follow-on spec.
- Provide deterministic golden cases that future models must reproduce before
  they can claim compatibility with the domain foundation.
- Give existing agents one shared expert contract to retrieve and cite, reducing
  duplicated domain prose and future catalog sprawl.

## Non-Goals

- No repo, cash-product, securities-lending, or collateral pricing/optimization
  runtime is implemented by this spec. Those are separate specs `0064`–`0067`.
- No live API, feed, web scraper, database connector, or production ingestion
  pipeline is implemented. Source ingestion belongs to `0068`.
- No attempt to encode all securities, derivatives, credit products, treasury
  functions, jurisdictions, or legal agreements. The initial scope is U.S.
  institutional short-term markets; extensions must declare their jurisdiction
  and conventions explicitly.
- No legal, tax, accounting, capital, or regulatory advice. The pack identifies
  authoritative materials, concepts, applicability fields, and review dates;
  qualified owners decide how a rule applies to a particular firm or trade.
- No proprietary market data, licensed agreement text, client information,
  credentials, MNPI, or internal counterparty terms are committed.
- No new agent is added merely because a topic appears in the taxonomy. Existing
  agents consume the shared foundation unless the coverage matrix demonstrates a
  distinct workflow and a later approved spec establishes it.
- No existing runtime is silently “fixed” as part of documentation work. Every
  behavioral change receives acceptance criteria in its owning child spec.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The foundation shall define a capability map covering, at minimum: repo/reverse repo; securities lending; collateral, haircut, margin, and substitution; U.S. Treasury bills and short-dated Treasury cashflows; an explicitly approved institutional cash-product universe; clearing, settlement, reporting, and regulatory context; and connections to financing-aware portfolio, backtest, risk, liquidity, and capacity decisions. Every capability shall have a status and an owning existing or future artifact. | must |
| REQ-002 | The foundation shall define a canonical taxonomy with stable IDs, preferred names, aliases, definitions, product/process/role classifications, parent and related concepts, and collision rules. The terms “repo” and “reverse repo,” “GC” and “special,” “borrow fee” and “rebate,” “haircut” and “margin,” and “price,” “rate,” and “yield” shall not be treated as interchangeable. | must |
| REQ-003 | Every economic rule, formula, and example shall declare its viewpoint using canonical roles, including at minimum cash provider/taker, securities provider/receiver, repo seller/buyer, securities lender/borrower, beneficial owner, agent lender, and short seller where applicable. Cash and security directions and positive/negative cost or income signs shall be explicit. | must |
| REQ-004 | The foundation shall define a machine-readable convention registry for rates, yields, prices, cashflows, collateral, and settlement. Each convention shall carry units, quote style, day count, compounding or discount basis, calendar, business-day adjustment, settlement lag/timing, rounding, economic viewpoint, formula reference, jurisdiction, effective interval, and source references where applicable. | must |
| REQ-005 | The foundation shall define lifecycle contracts for repo, securities lending, cash products, and collateral. Each contract shall enumerate valid states, events/transitions, preconditions, contractual and contingent cashflows, marks/margin, substitutions, corporate actions where relevant, fails/default/termination paths, and which role initiates or receives each event. | must |
| REQ-006 | The foundation shall define an evidence hierarchy and source-reference contract. Every reviewed knowledge record shall identify a registered source, source authority type, document or dataset locator, publication/retrieval date, jurisdiction, effective interval, access/license class, and the claim or field the source supports. Conflicting sources shall be resolved explicitly or retained as a visible conflict. | must |
| REQ-007 | Every knowledge record shall be classified as one of: stable mechanic, contractual convention, regulatory/policy rule, time-varying market observation, empirical finding, or model assumption. The class shall determine required `as_of`, `effective_from`, `effective_to`, validation, and freshness behavior; no later observation or rule version may leak into an earlier as-of query. | must |
| REQ-008 | The foundation shall contain a coverage matrix and discrepancy register mapping current agents, instructions, runtimes, source entries, and tests to the canonical capabilities. Coverage levels shall distinguish absent, prose-only, contract-only, reference-runtime, and validated-runtime states; limitations and the responsible child spec shall be explicit. | must |
| REQ-009 | The foundation shall provide deterministic golden cases for each core domain. Cases shall include typed inputs, units, viewpoint, convention IDs, source or assumption references, expected outputs, tolerances, and paired-role or accounting identities where relevant. At minimum, the set shall exercise repo GC-versus-special sign, securities-lending fee/rebate direction, rate/yield conversion, day-count accrual, haircut/margin, lifecycle transitions, and point-in-time admission. | must |
| REQ-010 | The handoff shall reserve but not prematurely design six bounded child specs: `0064` repo economics/lifecycle runtime, `0065` cash products/pricing, `0066` securities-lending correction/expansion, `0067` collateral/margin optimization, `0068` source ingestion/data contracts, and `0069` regulatory/legal/market-structure knowledge. Each reservation shall name its dependencies and activation boundary. | must |
| REQ-011 | The domain pack shall be discoverable from `specs/README.md`, `docs/handoff.md`, the relevant agent-group documentation, and a shared short-term-markets instruction standard. Existing agents shall link to the canonical pack instead of independently redefining shared terms and conventions. | should |
| REQ-012 | The discrepancy register shall, at minimum, adjudicate the currently observed risks: repo-special versus stock-loan-special sign/viewpoint ambiguity; hard-coded borrow classifications; mixed 252-day and ACT/360 accrual; declared-but-unused counterparty concentration in securities-lending allocation; retroactive use of a rate learned during a holding period; and fixed-notional/universal-day-count simplifications in financing-cost analysis. A discrepancy may be corrected in domain prose under `0063` or assigned to a child runtime spec, but it may not disappear without a disposition. | must |
| REQ-013 | Every knowledge record and golden case shall carry a review status (`draft`, `reviewed`, `superseded`, or `retired`). Promotion to `reviewed` shall require a named domain reviewer, review date, supporting evidence, and no unresolved severity-high discrepancy affecting that record. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Deterministic, offline validation | All committed schemas, relationships, references, effective intervals, and golden cases validate without network access; validation uses the Python standard library plus existing project dependencies only. |
| NFR-002 | Temporal correctness | Every time-varying item carries both knowledge/as-of and effective-time semantics; fixtures prove that later observations and superseding rules are rejected for earlier as-of use. |
| NFR-003 | Evidence completeness | 100% of records marked `reviewed` have resolvable source references and field- or claim-level support; unsupported items remain `draft`. |
| NFR-004 | Expert reviewability | Promotion evidence records reviewer identity as a non-email handle, review date, and review scope; automation may validate structure but cannot self-certify domain correctness. |
| NFR-005 | Bounded scope | The initial pack declares `jurisdiction=US`; every excluded product/jurisdiction is marked out of scope or future rather than implied by a generic term. |
| NFR-006 | Security and licensing | No secret, MNPI, personal data, proprietary feed value, licensed agreement text, or restricted counterparty term is committed; source metadata records access and license constraints. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the capability map, when each required domain in REQ-001 is queried, then at least one capability row exists with scope, coverage level, current artifact(s), limitation, and owner/future spec. | REQ-001, REQ-008 |
| AC-002 | Given the taxonomy, when aliases and stable IDs are validated, then IDs and preferred names are unique, aliases resolve deterministically, and the required non-interchangeable term pairs in REQ-002 remain distinct. | REQ-002 |
| AC-003 | Given a repo example with a GC rate above a specific-collateral rate, when specialness is evaluated, then the case defines positive specialness as `GC rate - specific rate`, identifies the cash provider’s lower rate income, and does not reuse a stock-loan “higher fee means more special” rule without an explicit viewpoint conversion. | REQ-003, REQ-009 |
| AC-004 | Given any convention record, when validated, then its units, quote style, timing/day-count fields, viewpoint, jurisdiction, effective interval, formula reference, and source or assumption references are present as applicable; incompatible or omitted fields fail validation. | REQ-004, NFR-001 |
| AC-005 | Given the four lifecycle contracts, when their transition graphs are validated, then all states are reachable from an initial state, terminal states are explicit, transition roles/cashflows are identified, and an undeclared transition is rejected. | REQ-005 |
| AC-006 | Given a record marked `reviewed`, when evidence validation runs, then every source reference resolves and carries authority, locator, jurisdiction, date, effective interval, access, license, and supported-claim metadata; otherwise the record cannot be reviewed. | REQ-006, REQ-013, NFR-003, NFR-006 |
| AC-007 | Given two versions of a time-varying rule or market observation, when an as-of date precedes the later version’s knowledge date, then the later version is excluded even if its effective interval overlaps. | REQ-007, NFR-002 |
| AC-008 | Given the current repository, when the discrepancy register is inspected, then all six issues named in REQ-012 have evidence paths, severity, disposition, and an owning spec; none is represented as corrected unless the affected artifact and validation evidence changed. | REQ-008, REQ-012 |
| AC-009 | Given the golden-case set, when it is run twice offline, then the repo, securities-lending, cash/yield, day-count, haircut/margin, lifecycle, and point-in-time cases produce identical results within declared tolerances. | REQ-009, NFR-001, NFR-002 |
| AC-010 | Given a numeric threshold used to classify GC/special or easy/hard-to-borrow status, when the pack is validated, then the threshold is either an explicitly parameterized model assumption or a sourced rule with jurisdiction/effective dates; an unexplained global constant fails validation. | REQ-004, REQ-007, REQ-012 |
| AC-011 | Given `docs/handoff.md`, when the planned-spec table is inspected, then `0064`–`0069` appear with the scopes, dependencies, and activation rule required by REQ-010, while `0063` is identified as the active Draft and `0070` as the next unreserved number. | REQ-010 |
| AC-012 | Given the relevant securities-financing and fixed-income agent instructions, when a shared term or convention is needed, then the instructions point to the canonical foundation; any retained local summary is consistent with it and declares viewpoint and scope. | REQ-011, REQ-012 |
| AC-013 | Given the `0063` implementation diff, when reviewed, then no pricing, trading, allocation, or optimization result in an existing runtime has changed under this spec. | REQ-010, NFR-005 |
| AC-014 | Given a knowledge record or golden case proposed as `reviewed`, when reviewer metadata is absent or a severity-high discrepancy remains open against it, then promotion is rejected. | REQ-013, NFR-004 |
| AC-015 | Given a clean checkout, when the domain validation tests and existing repository gates run, then they pass without credentials, network access, or private data. | REQ-011, NFR-001, NFR-006 |

## Data & Dependencies

### Existing repository dependencies

- `agents/securities_financing/` and `instructions/securities_financing.md` —
  current domain contracts to crosswalk and reconcile.
- `agents/asset_classes/fixed_income_rates/` — current rates/fixed-income
  mechanics contract.
- Specs `0022`, `0023`, `0027`, `0028`, `0035`, `0039`, `0045`, `0048`,
  `0052`, and `0053` — existing mechanics, runtimes, source registration,
  point-in-time, memory, and knowledge-resource contracts.
- `sources/` and `templates/data/source_catalog_entry.yml` — canonical source
  registry rather than a second source inventory.
- `instructions/point_in_time.md`, `instructions/data_provenance.md`,
  `instructions/knowledge_base.md`, and `instructions/risk_management.md` —
  temporal, evidence, retrieval, and risk constraints.

### External source classes to register during implementation

The foundation does not copy source content. It records locators and
field/claim-level support, prioritizing:

1. statutes, regulations, regulator releases, and official rule text;
2. official benchmark administrators and government data/issuance publishers;
3. clearing, settlement, and reporting infrastructure specifications;
4. recognized contractual and industry-standard documentation;
5. licensed vendor methodology and data dictionaries, subject to access terms;
6. reviewed internal operating procedures; and
7. analyst interpretation, always labeled and never promoted above its evidence.

Expected U.S. source owners include the U.S. Treasury, Federal Reserve Bank of
New York, Federal Reserve Board, SEC, FINRA, and DTCC/FICC. Industry sources may
include SIFMA, ICMA, and ISLA where they are authoritative for the convention or
agreement concept being described. Inclusion in this list is not evidence by
itself; each actual record must cite the specific document or dataset version it
uses.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A polished taxonomy is mistaken for validated market expertise. | Agents answer confidently from structure without sufficient substance. | Distinguish `draft` from `reviewed`; require claim-level evidence and named domain review; expose coverage level and gaps. |
| RISK-002 | Economic signs remain viewpoint-dependent even after terms are normalized. | Correct formulas produce wrong P&L interpretations. | REQ-003 makes role, asset direction, and cost/income sign mandatory; paired-role golden cases prove conservation identities. |
| RISK-003 | Rules, benchmark methods, clearing mandates, or market conventions change. | Stale knowledge is served as current or leaks into historical analysis. | Effective intervals, knowledge/as-of time, source versions, freshness policy, supersession, and `0069` review ownership. |
| RISK-004 | The foundation becomes a mega-spec or encyclopedia. | Review stalls; no usable runtime follows. | U.S.-first boundary, fixed artifact contracts, explicit non-goals, and six separately activated child specs. |
| RISK-005 | Public documentation accidentally reproduces licensed agreements or data. | Contractual, copyright, or data-license breach. | Store definitions, identifiers, formulas, and locators only; record license/access class; never copy proprietary text or observations. |
| RISK-006 | Existing runtimes appear compatible because names match while their assumptions do not. | Silent model error survives the documentation layer. | Coverage levels, discrepancy register, golden cases, and explicit child-spec ownership; no compatibility claim without validation. |
| RISK-007 | “U.S. market” is treated as one homogeneous convention across products, venues, or counterparties. | Over-generalized rules fail on real transactions. | Product, venue, agreement/context, role, jurisdiction, and effective-time fields; unknown or bilateral terms remain explicit inputs. |

## Assumptions & Open Questions

- Assumption: the first expert pack is U.S.-first because the current library,
  source catalog, regulatory references, and likely initial consumers are most
  developed there. Other jurisdictions extend the schemas; they do not silently
  reuse U.S. defaults.
- Assumption: the initial cash-product universe will include U.S. Treasury bills
  and short-dated Treasury cashflows, with commercial paper, certificates of
  deposit, deposits, agency discount notes, and money-market-fund shares admitted
  only when `coverage.json` defines the required pricing, credit, liquidity, and
  source fields for each. Repo remains its own transaction family even when used
  as a cash investment.
- Assumption: canonical machine-readable artifacts will use JSON so offline
  validation needs no new parser dependency; Markdown provides expert narrative
  and citations.
- Open question: which named securities-finance or money-markets practitioner
  will approve records as `reviewed` rather than merely approve the software
  structure?
- Open question: which industry-standard or master-agreement materials are
  available under terms that permit derived definitions and stable locators?
- Open question: should `0067` ship a small transparent reference optimizer, rely
  only on the `0026` model-plugin boundary, or support both? `0063` supplies the
  inputs and golden cases but does not prejudge that decision.
- Open question: which cash products beyond Treasury bills are needed by the
  first real consumer? The capability matrix must answer before `0065` is
  approved.

## Exceptions

None.
