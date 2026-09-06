# Short-Term Markets Domain Foundation

This pack is the canonical QuantSmith contract for U.S.-first short-term
markets work under spec `0063-short-term-markets-domain-foundation`.

It gives agents and later runtimes stable IDs, viewpoints, conventions,
lifecycle states, source rules, coverage levels, and deterministic golden cases.
It is a foundation, not a pricing library.

## Scope

Included:

- repo and reverse repo;
- securities lending and short-borrow economics;
- collateral, haircuts, margin, and substitution;
- Treasury bills and short-dated Treasury cashflows;
- an admitted-but-not-yet-priced institutional cash-product universe;
- clearing, settlement, reporting, and regulatory source context; and
- links from financing economics to portfolio, backtest, risk, liquidity, and
  capacity review.

Excluded until later specs:

- repo economics and lifecycle runtime (`0064`);
- cash-product pricing and accrual engines (`0065`);
- securities-lending runtime corrections and expansion (`0066`);
- collateral allocation or margin optimization (`0067`);
- live source ingestion and data contracts (`0068`);
- legal, regulatory, or market-structure knowledge pack (`0069`);
- non-U.S. jurisdictions unless an extension declares its jurisdiction and
  conventions explicitly.

Specs `0064` through `0069` are reserved in `docs/handoff.md`; do not draft or
activate them from this pack alone.

## Files

| File | Purpose |
| --- | --- |
| `taxonomy.json` | Stable concept IDs, aliases, role/viewpoint definitions, and non-interchangeable term pairs. |
| `conventions.json` | Rate, price, cashflow, collateral, settlement, sign, and threshold conventions. |
| `lifecycles.json` | Repo, securities-lending, cash-product, and collateral state machines. |
| `coverage.json` | Capability map across current agents, instructions, runtimes, sources, tests, limitations, and owner specs. |
| `golden_cases.json` | Deterministic arithmetic, sign, lifecycle, and point-in-time cases. |
| `source_policy.md` | Source hierarchy, access/license rules, temporal rules, conflicts, freshness, and review policy. |
| `gap_register.md` | Current discrepancy register for the issues called out by REQ-012. |

Validate with:

```sh
PYTHONPATH=src python3 -m quantsmith.pipelines.short_term_markets_knowledge
PYTHONPATH=src pytest -q tests/test_short_term_markets_knowledge.py
```

## Common Record Contract

Machine-readable top-level records use a shared envelope:

| Field | Rule |
| --- | --- |
| `id` | Stable namespaced ID; never reuse a retired ID for a new meaning. |
| `record_type` | One of `concept`, `convention`, `lifecycle`, `capability`, or `golden_case`. |
| `name` | Preferred display name. |
| `jurisdiction` | `US` in the first pack; extensions must declare their own jurisdiction. |
| `knowledge_class` | `stable_mechanic`, `contractual_convention`, `regulatory_policy`, `market_observation`, `empirical_finding`, or `model_assumption`. |
| `knowledge_as_of` | Date this record version was knowable to the pack. |
| `effective_from` / `effective_to` | Effective interval for the underlying rule, observation, or convention. `effective_from` is inclusive; `effective_to` is exclusive. |
| `source_refs` | `source.<source_id>` entries from `sources/`, or `assumption.<id>` for explicit model assumptions. |
| `review_status` | `draft`, `reviewed`, `superseded`, or `retired`. |
| `review` | Required only for `reviewed`; carries reviewer handle, date, scope, and evidence refs. |
| `supersedes` | Prior record IDs replaced by this version. |

## Agent Use

Agents must resolve these before giving financing or short-term-markets advice:

1. product or process ID;
2. role/viewpoint ID;
3. quote, day-count, settlement, and sign convention IDs;
4. `as_of` date and effective date;
5. source refs and review status; and
6. known gaps from `coverage.json` and `gap_register.md`.

Agents may summarize this pack, but they should cite the stable record IDs and
source refs they used. When a term is ambiguous, especially `special`, `repo`,
`reverse repo`, `borrow fee`, `rebate`, `haircut`, `margin`, `price`, `rate`, or
`yield`, the agent must ask for the missing product, side, or viewpoint rather
than guessing.

## Review Status

All initial 0063 records are `draft`. Structural validation proves only that IDs,
references, temporal fields, lifecycles, source links, thresholds, and golden
case arithmetic are coherent. It does not certify market expertise.

Promotion to `reviewed` requires:

- a non-email practitioner or data/quant reviewer handle;
- review date and review scope;
- source or evidence refs that resolve through `sources/`;
- no unresolved severity-high discrepancy affecting the record; and
- explicit conflict disposition where sources disagree.

## Draft Decisions

The Draft spec leaves these decisions unresolved:

- Named practitioner reviewer for viewpoints, conventions, and lifecycles.
- Which industry or agreement materials can be used without copying licensed
  text.
- Whether `0067` owns a small reference optimizer, a model-plugin-only boundary,
  or both.
- Which non-Treasury cash product has the first real `0065` consumer.
- Whether a future MCP/resource server should expose this pack directly or via
  the existing `0052` resource discovery pattern.

This implementation records those as blocked follow-up tasks rather than
silently answering them.
