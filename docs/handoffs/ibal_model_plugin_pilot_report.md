# IBAL Model Plugin Pilot Report

**Date:** 2026-09-17  
**Branch:** `feature/ibal-model-plugin-pilot`  
**Purpose:** Run the first manual QuantSmith model-plugin pilot for IBAL without shipping live wiring.

## Outcome

The pilot completed as a manual, artifact-boundary exercise. `IBAL` was registered in QuantSmith's local, gitignored `model_plugins.yml`; one `model_plugin_registration` understanding brief was produced; the real IBAL REST API was invoked once using synthetic data; and the reported numbers below were independently rechecked against the IBAL API response.

No dispatcher, runtime integration, production route, or Market Terminal UI change was added.

## Registration

The local manifest entry is `ibal-inventoryballast-rest-v1`. It uses the `rest_endpoint` invocation profile and keeps the concrete local endpoint in `model_plugins.yml`, which is intentionally gitignored.

The registration brief is `docs/handoffs/ibal_model_plugin_understanding_brief.md`. Its conclusion is deliberately narrow: the manifest is contract-complete enough for a manual pilot, but every capability remains a claim until a solve result is reviewed.

## Invocation

The pilot called the live local IBAL API with a synthetic dataset:

| Field | Value |
| --- | --- |
| Synthetic seed | 260917 |
| Profile | balanced |
| Scale | small |
| Request ID | `SYN-REQ-260917` |
| Request hash | `d8b1117979f6dfb13c4f5bba86fbc179d31184c4764010ed6429095a94683977` |
| Engine package | `0.1.0` |
| Solver backend | `highs 1.15.1` |
| Run ID | `inv-opt-f14b57a3f642` |
| Solver status | `optimal` / `kOptimal` |
| Termination reason | `Optimal` |
| Engine verification passed | `True` |

The raw dataset and run response were stored only in `/tmp/ibal_quant_smith_pilot/` during the pilot and were not committed.

## Independent Reverification

Every numeric value in this section is either directly extracted from the IBAL API response or recomputed from response rows. The durable evidence summary is `docs/handoffs/ibal_model_plugin_pilot_evidence.json`.

| Reported number | Value | Reverification method |
| --- | ---: | --- |
| Inventory rows | 8 | From dataset summary row counts |
| Route rows / allocation rows | 24 | Counted `result.allocations` rows |
| Demand rows | 24 | Counted `result.demand` rows |
| Balance rows | 8 | Counted `result.balances` rows |
| Constraint rows | 67 | Counted `result.constraints` rows |
| Binding rows at absolute slack <= 1e-6 | 55 | Recomputed from constraint slack values |
| Total lendable shares | 1434000.000000 | From dataset summary |
| Total current on-loan shares | 515918.236939 | Matches sum of allocation current quantities and balance pre-on-loan |
| Post on-loan shares | 1241168.950512 | Sum of `balances.post_on_loan_shares`; matches sum of allocation post quantities |
| Net allocation change | 725250.713573 | Sum of allocation post quantities minus current quantities |
| Demand raw shares | 1460198.765309 | Sum of `demand.raw_demand_shares` |
| Demand filled shares | 1241168.950512 | Sum of `demand.filled_shares` |
| Recomputed fill rate | 0.850000000000 | Filled demand divided by raw demand |
| Economics total value USD | 2963.136786211736 | Matches sum of economics component values |
| Economics total delta USD | 1799.119160298135 | Matches sum of economics component deltas |
| Max row violation | 1.164153218269e-10 | From engine verification payload |
| Max variable-bound violation | 0.000000000000e+00 | From engine verification payload |
| Objective reconstruction delta | 0.000000000000e+00 | From engine verification payload |

The largest allocation-to-balance reconciliation delta was `0.000000000000e+00`, so the route-level post quantities reconciled to inventory balances for this run.

## Findings

- The model-plugin registration flow is usable for IBAL as a manual pilot even without a QuantSmith executable dispatcher.
- Registration review and solve review must remain separate: the understanding brief only reviews declared interface metadata.
- The local API solve returned `optimal`, native status `kOptimal`, and engine verification passed on synthetic data.
- The pilot preserved the boundary required by Market Terminal's spec005: no real book/request data entered QuantSmith, and no QuantSmith-originated number is accepted without rechecking against the IBAL response.
- The current registration should not be promoted to production approval from this pilot alone; production use still needs trusted access boundary, production enablement, and a future dispatcher or repeatable invocation harness.

## Follow-Up

1. Decide whether QuantSmith should add an executable dispatcher now that IBAL is a concrete REST target.
2. If dispatcher work starts, keep raw problem payloads outside committed files and pass them by artifact URI.
3. Add a second pilot using a MIP-triggering synthetic fixture after InventoryBallast's MIP/QP decision is settled.
4. Keep Market Terminal's pin and IBAL validation docs as the source of truth for engine behavior.
