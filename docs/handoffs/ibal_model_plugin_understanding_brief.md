# IBAL Model Plugin Registration Understanding Brief

**Date:** 2026-09-17  
**Agent contract:** `agents/optimization/model_plugin_registration/`  
**Manifest entry reviewed:** `ibal-inventoryballast-rest-v1` from local, gitignored `model_plugins.yml`  
**Scope:** Registration review only; not approval of solver correctness or production use.

## Declared Capability (As Stated)

The manifest claims that `ibal-inventoryballast-rest-v1` exposes the already-built InventoryBallast engine through a REST endpoint for securities-lending inventory allocation.

The manifest claims the model's objective is securities-lending inventory allocation across route-level quantities, with InventoryBallast declaring LP, MIP, and QP families where supported by the pinned engine.

The manifest claims the decision-variable shape is per-route securities-lending allocation quantity plus related inventory-balance quantities. No objective coefficients, constraint matrix, book data, or proprietary formulation detail was included in this repository.

The manifest claims the relevant constraint families are inventory balance/reserve constraints, demand caps, borrower/counterparty limits, utilization policy limits, and discrete route rules where supported by InventoryBallast.

The manifest states three known limitations: registration review is not solve verification; exact MIP plus QP remains unsupported by the pinned HiGHS-backed engine unless InventoryBallast later advertises it; and real book/request data must not enter QuantSmith.

## Contract Compliance

| Required field | Status | Notes |
| --- | --- | --- |
| `model_id` | Present | `ibal-inventoryballast-rest-v1` |
| `owner` | Present | Team/role, not a person's name |
| `category` | Present | `other`, because the declared engine spans LP/MIP/QP rather than one enum value |
| `declared_capability.objective` | Present | Capability claim only |
| `declared_capability.decision_variables` | Present | Shape only; no coefficients |
| `declared_capability.constraint_types` | Present | Constraint families only |
| `declared_capability.known_limitations` | Present | Includes no-real-data and unsupported-combination caveats |
| `invocation.type` | Present | `rest_endpoint` |
| `invocation.reference` | Present locally | Kept only in gitignored `model_plugins.yml`; not repeated here |
| `invocation.timeout_seconds` | Present | 60 seconds |
| `input_schema_uri` | Present | Points to Market Terminal wrapper contract |
| `output_schema_uri` | Present | Points to Market Terminal wrapper contract |
| `review_status` | Present | `unreviewed`; this brief does not advance status |
| `last_reviewed` | Present | `null` in manifest |

## Unverifiable Claims

- The manifest's claim that InventoryBallast correctly solves the securities-lending allocation problem cannot be verified from registration metadata alone.
- The manifest's claimed LP/MIP/QP support cannot be accepted from metadata alone; it requires service capability checks and solve evidence.
- The manifest's stated endpoint availability cannot be verified from the committed repository because the endpoint is intentionally local-only.
- The manifest's objective and constraint-family descriptions are interface-level claims, not inspected formulation logic.
- The registration does not prove production authorization, authentication boundary, or suitability for real book data.

## Handoff

Route any actual invocation result to `solver_diagnostics_sensitivity` for solve review and to `risk` for production-boundary review before any downstream consumer treats model output as approved. Keep `review_status` unchanged until a human owner decides whether this registration should become `reviewed` or `approved`.
