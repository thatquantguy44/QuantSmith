# Plan: Short-Term Markets Domain Foundation

- **Spec:** 0063-short-term-markets-domain-foundation (`spec.md`)
- **Status:** Draft
- **Author:** Codex
- **Last updated:** 2026-09-05

> This is the proposed HOW for review with the Draft spec. Implementation does
> not begin until the spec is approved.

## Approach

Build one canonical, public, versioned domain pack and make existing agents point
to it. The pack separates human-readable expert explanation from
machine-readable contracts: Markdown explains market mechanics, boundaries, and
evidence; JSON carries stable IDs, relationships, conventions, lifecycle graphs,
coverage states, and deterministic examples. A small standard-library validator
loads the JSON and checks referential, temporal, and arithmetic invariants.

The design is deliberately layered:

1. **Semantics first** — taxonomy, roles, economic viewpoints, units, and signs.
2. **Mechanics second** — quotation/convention records and lifecycle graphs.
3. **Evidence and time around both** — source authority, review status,
   knowledge/as-of time, effective intervals, conflicts, and supersession.
4. **Models last** — golden cases and the coverage/discrepancy register define
   what later runtimes must reproduce without implementing those runtimes here.

The result becomes the input contract for reserved specs `0064`–`0069`. Those
specs may extend the pack, but they may not privately redefine its stable IDs,
viewpoints, or conventions.

## Architecture & Components

```text
authoritative public documents and datasets
reviewed industry/internal interpretations
                    |
                    v
            sources/ registry (0027)
                    |
                    v
knowledge/short_term_markets/
  README.md                 scope, navigation, review policy
  source_policy.md          authority/conflict/freshness rules
  taxonomy.json             products, processes, roles, aliases, relations
  conventions.json          quotes, units, signs, day counts, calendars
  lifecycles.json           states, events, roles, cashflows, failure paths
  coverage.json             current capability/artifact/owner/status map
  golden_cases.json         deterministic examples and identities
  gap_register.md           evidence and disposition for current weaknesses
                    |
                    +--> instructions/short_term_markets.md
                    |      shared operating standard for agents
                    |
                    +--> existing agent instructions
                    |      thin routing/use guidance, not duplicated truth
                    |
                    +--> validate_short_term_markets.py + tests
                    |      offline structural/temporal/numerical checks
                    |
                    `--> 0064-0069 bounded consumers
```

### Component responsibilities

| Component | Responsibility |
| --- | --- |
| `knowledge/short_term_markets/README.md` | State the U.S.-first scope, navigation, review states, how agents should cite records, and what the pack does not claim. |
| `taxonomy.json` | Provide stable IDs and deterministic alias resolution for products, processes, roles, transaction sides, lifecycle concepts, and risk dimensions. |
| `conventions.json` | Define units and transformations for rate/yield/price/accrual/collateral conventions with explicit viewpoint and time scope. |
| `lifecycles.json` | Encode permitted transaction states and transitions; connect events to roles, cash/security movements, accrual, margin, corporate actions, and exceptional termination. |
| `coverage.json` | Map the desired expert capability surface to current agents, instructions, code, sources, tests, limitations, and future owning specs. |
| `golden_cases.json` | Hold small deterministic cases that exercise signs, conversions, dates, lifecycle rules, and paired-role identities. |
| `source_policy.md` plus `sources/*.yml` | Reuse `0027` for source ownership and connection metadata while documenting evidence hierarchy, conflict resolution, licensing, effective time, and field-level support. |
| `gap_register.md` | Record observed mismatches with evidence paths, severity, affected consumers, disposition, and owning spec; never equate identification with correction. |
| `instructions/short_term_markets.md` | Tell all relevant agents how to use the pack: resolve viewpoint first, never infer missing conventions, retrieve as-of-safe evidence, and state uncertainty. |
| `validate_short_term_markets.py` | Standard-library loader/validator for unique IDs, references, required fields, intervals, lifecycle graphs, coverage ownership, review evidence, and golden-case operations. It exposes no pricing API. |

## Interfaces & Data Contracts

### Common record envelope

Every machine-readable record uses the following common fields unless the record
is a pure relationship embedded in a parent:

| Field | Type | Rule |
| --- | --- | --- |
| `id` | string | Stable namespaced ID; unique and never reused. |
| `record_type` | enum | `concept`, `convention`, `lifecycle`, `capability`, or `golden_case`. |
| `name` | string | Human-readable preferred name. |
| `jurisdiction` | string | `US` in the first pack; never omitted or inferred. |
| `knowledge_as_of` | ISO date | When this version was available to the library. |
| `effective_from` | ISO date or null | First date the underlying rule/convention applies; null only for stable mechanics or explicit assumptions. |
| `effective_to` | ISO date or null | Inclusive/exclusive policy is fixed in the pack README; null means still active, not timeless. |
| `knowledge_class` | enum | `stable_mechanic`, `contractual_convention`, `regulatory_policy`, `market_observation`, `empirical_finding`, `model_assumption`. |
| `source_refs` | array[string] | Registered source/evidence IDs supporting the record; empty only for a labeled model assumption or draft gap. |
| `review_status` | enum | `draft`, `reviewed`, `superseded`, or `retired`. |
| `review` | object or null | For `reviewed`: non-email reviewer handle, ISO review date, scope, and evidence refs. |
| `supersedes` | array[string] | Older record IDs replaced by this record; cycles forbidden. |

`knowledge_as_of` and the effective interval are separate. A regulation may have
a future effective date but be knowable after publication; a historical query
must first pass the knowledge/as-of check, then the effective-time check for the
question being asked.

### Taxonomy concept

```json
{
  "id": "role.repo_cash_provider",
  "record_type": "concept",
  "name": "Repo cash provider",
  "kind": "role",
  "aliases": ["reverse-repo investor"],
  "definition": "...",
  "parent_ids": ["role.cash_provider"],
  "related_ids": ["role.repo_securities_receiver"],
  "jurisdiction": "US",
  "knowledge_class": "stable_mechanic",
  "knowledge_as_of": "YYYY-MM-DD",
  "effective_from": null,
  "effective_to": null,
  "source_refs": ["source.example"],
  "review_status": "draft",
  "review": null,
  "supersedes": []
}
```

Alias resolution is case-folded and punctuation-normalized. An alias resolving
to multiple IDs is invalid unless an explicit ambiguity record requires the
caller to supply transaction side or context; the validator never guesses.

### Convention record

In addition to the common envelope:

| Field | Rule |
| --- | --- |
| `quantity` | Canonical measured quantity, such as `financing_rate`, `discount_yield`, `borrow_fee`, `rebate_rate`, `haircut`, `margin_amount`, or `dirty_price`. |
| `quote_style` | Explicit style: decimal rate, percent, basis points, price per par, discount yield, add-on yield, money-market yield, bond-equivalent yield, amount, or ratio. |
| `unit` | No naked number: currency, currency-per-par, decimal, percent, basis points, days, or quantity-specific unit. |
| `day_count` | Named basis or `not_applicable`; product defaults are records, never code assumptions. |
| `compounding` | Simple, discount, periodic with frequency, continuous, or `not_applicable`. |
| `calendar` / `business_day_adjustment` | Named calendar and roll behavior or explicit `not_applicable`. |
| `settlement` | Lag, cut-off/timing semantics, and start/end inclusion rule where relevant. |
| `rounding` | Precision and method applied only at the declared output boundary. |
| `viewpoint_ids` | Canonical roles from `taxonomy.json`; cost/income and cash/security directions stated per role. |
| `formula` | Symbolic formula identifier plus input/output field names; executable golden-case operation is separately allow-listed. |

### Lifecycle contract

Each lifecycle declares:

- one or more initial states and explicit terminal states;
- states with invariants;
- transitions with `event_id`, `from`, `to`, initiating/affected roles,
  preconditions, and emitted cashflow/security/margin event references;
- periodic events that leave state unchanged, such as accrual or mark-to-market;
- substitution, partial return/unwind, fail, default, close-out, and cancellation
  paths where applicable; and
- invalid-transition examples in `golden_cases.json`.

The validator checks duplicate states/events, missing endpoints, unreachable
states, missing role/direction fields, and undeclared references. It does not
decide legal enforceability.

### Coverage capability

```json
{
  "id": "capability.repo.specialness",
  "product_ids": ["product.repo"],
  "topic": "GC versus specific-collateral economics",
  "coverage_level": "prose_only",
  "artifact_paths": ["agents/securities_financing/repo_financing/instructions.md"],
  "source_readiness": "missing",
  "validation_status": "not_validated",
  "limitations": ["Economic viewpoint not canonicalized"],
  "owner_spec": "0064"
}
```

Allowed coverage levels are `absent`, `prose_only`, `contract_only`,
`reference_runtime`, and `validated_runtime`. `reviewed` domain prose does not
upgrade a runtime’s level; only tests against compatible golden cases do.

### Golden case

Each case declares `case_id`, `domain`, `purpose`, `as_of`, `viewpoint_ids`,
`convention_ids`, typed inputs with units, an allow-listed operation, expected
outputs with units/tolerances, invariant assertions, and source or assumption
references. Operations are deliberately small—rate difference, simple accrual,
price/yield conversion, haircut amount, sign mapping, transition admission, and
point-in-time admission—not a hidden pricing engine.

For repo specialness the canonical comparison is:

```text
specialness_bps = (gc_repo_rate - specific_collateral_repo_rate) * 10,000
```

A positive value means the specific collateral trades below GC on the repo-rate
axis. The case separately states the cash provider’s rate income and the
securities provider’s transaction context; it does not collapse those economics
into a stock-loan fee label.

### Evidence references

The existing `sources/` catalog remains the source registry. The domain pack may
add a small evidence locator when one catalog entry supports multiple documents
or datasets, but it may not create a second competing source catalog. Evidence
locators carry document/dataset title, publisher, version/publication date,
retrieval date, stable URL or dataset identifier, supported record/field IDs,
authority tier, access class, and license notes.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P1 Spec is source of truth | yes | This Draft freezes WHAT/WHY before any domain-pack implementation; behavioral runtimes remain child specs. |
| P2 Traceability | yes | Every requirement maps to tasks and acceptance evidence below. Stable IDs connect knowledge, sources, gaps, and future models. |
| P3 Explicit DoD | yes | Structural, temporal, arithmetic, evidence, and review criteria are separately testable. |
| P4 Correct by construction | yes | Mandatory units/viewpoints, no implicit defaults, separate knowledge/effective time, transition graphs, and golden cases make common finance errors invalid inputs. |
| P5 Reversibility | yes | The pack is additive and versioned; records are superseded rather than silently overwritten. Existing runtime behavior does not change. |
| P6 Observability | yes | Coverage/gap states and validation output show what is present, reviewed, stale, conflicting, and compatible. No live service is introduced. |
| P7 Small changes | yes | One foundation plus six separately activated implementation specs replaces a single cross-domain mega-change. |
| P8 No silent trade-offs | yes | U.S.-first scope, JSON choice, agent-reuse decision, model boundary, and deferred products are explicit. |
| P9 Security/data | yes | Public metadata and derived mechanics only; access/license fields required; no proprietary values, agreement text, secrets, PII, or MNPI. |
| P10 Honest reporting | yes | `draft` is not `reviewed`; prose is not a validated runtime; observed discrepancies remain open until evidence proves a correction. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `README.md`, `coverage.json` capability universe | T-001, T-002, T-007 |
| REQ-002 | `taxonomy.json`, deterministic alias validation | T-003, T-008 |
| REQ-003 | Canonical role concepts, viewpoint/sign fields, paired-role cases | T-003, T-004, T-008 |
| REQ-004 | `conventions.json` and validation contract | T-004, T-008 |
| REQ-005 | `lifecycles.json` transition graphs | T-005, T-008 |
| REQ-006 | `source_policy.md`, `sources/*.yml`, evidence locators | T-006, T-008, T-010 |
| REQ-007 | Common temporal envelope and point-in-time cases | T-006, T-008 |
| REQ-008 | `coverage.json`, `gap_register.md` | T-007 |
| REQ-009 | `golden_cases.json`, validator, tests | T-008 |
| REQ-010 | `docs/handoff.md` reservations and activation rule | T-001, T-012 |
| REQ-011 | Shared instruction standard and documentation links | T-001, T-002, T-009 |
| REQ-012 | Required discrepancy dispositions and targeted instruction corrections | T-007, T-009 |
| REQ-013 | Review envelope, promotion validation, expert review | T-002, T-006, T-008, T-010 |
| NFR-001 | Standard-library validator and offline tests | T-008, T-011 |
| NFR-002 | Dual-time semantics and temporal fixtures | T-006, T-008 |
| NFR-003 | Reviewed-record evidence checks | T-006, T-008, T-010 |
| NFR-004 | Named human review metadata and review procedure | T-002, T-010 |
| NFR-005 | U.S.-first scope and explicit exclusions | T-002, T-007 |
| NFR-006 | License/access metadata, secret/data gates | T-006, T-011 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Work decomposition | One foundation spec plus six bounded child specs | One spec for all knowledge, sources, pricers, lifecycles, and optimizers | The combined acceptance surface would be too large to review or validate and would couple independent deliveries. |
| Knowledge ownership | Canonical domain pack consumed by existing agents | Add a specialist agent for every product/topic | Shared truth avoids duplicated prose and keeps agents narrow; a new agent requires a distinct workflow, not just a glossary row. |
| Representation | Human-readable Markdown plus strict JSON | Markdown only or a database | Markdown alone cannot validate IDs, signs, states, and references; a database adds migration/operations burden before there is enough content. JSON is standard-library-readable and diffable. |
| Geography | U.S.-first with mandatory jurisdiction | Generic global defaults | Repo, settlement, reporting, agreements, and cash conventions vary. A false universal default is worse than an explicit boundary. |
| Economic terminology | Explicit roles, asset directions, and signs | Perspective-neutral “repo rate,” “rebate,” or “cost” fields | The same transaction is named and signed differently by counterparties; requiring viewpoint prevents silent inversions. |
| Time model | Separate knowledge/as-of and effective intervals | One date or latest-current overwrite | Publication/observation time and legal/economic effectiveness are distinct; one date cannot prevent historical leakage. |
| Thresholds | Sourced rule or parameterized assumption | Global fixed GC/special or HTB cutoffs | Market classifications are contextual and time-varying; unexplained constants create false authority. |
| Validation | Small allow-listed golden-case operations | Build complete pricing engines in the foundation | The foundation needs contract tests, not premature implementations that belong to child specs. |
| Collateral optimizer boundary | Defer decision to `0067` with concrete inputs/cases | Permanently plugin-only or immediately SDK-owned | The current evidence supports neither permanent extreme; the foundation makes a later decision testable. |

## Validation Strategy

Add `tests/test_short_term_markets_knowledge.py` and a small reusable validator.
All tests run offline against committed fixtures.

### Structural validation

- unique stable IDs and deterministic aliases;
- valid enum values and required fields by record/knowledge class;
- all concept, convention, source, supersession, artifact, and owner-spec
  references resolve;
- effective intervals are ordered; supersession graphs are acyclic;
- `reviewed` records have reviewer and evidence metadata;
- lifecycle states are reachable and transitions reference valid roles/events;
- coverage rows have an owner and cannot claim a runtime level without a real
  artifact/test path.

### Golden-case validation

- repo GC/specific rate difference and viewpoint description;
- securities-lending fee/rebate cashflow directions;
- discount/add-on/price-yield conversions for admitted cash products;
- ACT/360 and other explicitly registered accrual bases without implicit 252-day
  substitution;
- haircut/margin amount and paired cash/security directions;
- valid and invalid lifecycle transitions;
- later-known observation/rule exclusion from an earlier as-of date; and
- deterministic repeatability and declared rounding/tolerance.

### Review validation

Automation verifies that review evidence exists, not that the reviewer is a
qualified practitioner. Before the pack is approved, a named securities-finance
or money-markets practitioner reviews the economic viewpoint, convention, and
lifecycle subsets; a data/quant reviewer checks temporal and numerical fixtures.
Disagreements remain explicit conflicts or `draft` records.

### Repository validation

Run at minimum:

```sh
hooks/stages/run-stage.sh spec docs-link spec-index doc-counts handoff-sync \
  source-catalog data-provenance secret-scan
pytest -q
git diff --check
```

## Rollout, Observability & Rollback

`0063` rolls out as a public knowledge-contract change with no existing pricing
or allocation behavior altered. Implement in reviewable commits by layer:
taxonomy/viewpoints, conventions/lifecycles, evidence/time, coverage/gaps,
golden cases/validation, then agent links. Child specs remain inactive until the
relevant foundation records are implemented and reviewed.

Validation output reports counts by record type and review status, unresolved
references, stale/effective-time conflicts, open discrepancies by severity,
capability coverage level, and golden-case failures. These are build-time
observability signals; no operational service or alert is introduced.

Rollback is a revert of the additive pack and links. After consumers exist,
stable IDs are never deleted or redefined: retire/supersede them and preserve
aliases so downstream failures are visible rather than silent.

## Open Questions

- Who is the named practitioner reviewer for the first `reviewed` release?
- Which non-Treasury cash product is the first real consumer of `0065`, and what
  official or licensed source data is available for it?
- Should the machine-readable files remain one file per concern or split by
  product after a measured size threshold? Start consolidated; split only when a
  review diff becomes difficult to understand.
- Should a future MCP/resource server expose the pack directly, or should the
  existing `0052` resource server discover it through `knowledge_sources.yml`?
  Prefer reuse of `0052`; decide during implementation once paths are concrete.
