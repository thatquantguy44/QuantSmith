# Spec: Collateral & Margin Allocation Optimizer Contract

- **ID:** 0067-collateral-margin-optimizer-contract
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-09-09

## Problem & Context

`docs/handoff.md`'s Planned specs table reserves `0067` as "Collateral,
margin, and allocation optimization... decide reference optimizer versus
plugin boundary explicitly." `agents/optimization/collateral_margin_optimization/`
already exists as a design-and-review role, but nothing in the SDK defines
what a collateral/margin allocation *problem* or *solution* actually looks
like as data. `adapters/model_plugin/` (spec `0026`) already supplies a
provider-neutral registration/invocation envelope for any already-built
optimization model — but its own Design Rule states it deliberately holds
no domain objective/constraint shape ("agents own problem framing"). A
collateral optimizer registered through `0026` today would have to invent
its own `input_schema_uri`/`output_schema_uri` content from scratch, with no
grounding in `0063`'s now-canonical short-term-markets taxonomy
(`concept.haircut`, `concept.margin_amount`,
`convention.collateral.haircut_ratio`,
`convention.collateral.margin_amount`, `lifecycle.collateral`).

The reviewer resolved `0067`'s open boundary decision directly: no reference
optimizer ships in this SDK; a real collateral optimizer is being built
externally and needs a general, stable contract to fit against later. This
spec supplies exactly that contract — nothing more.

## Goals

- Add `templates/optimization/collateral_margin_optimizer_contract.md`: the
  domain-specific problem/solution schema for a collateral-and-margin
  allocation model, composing `0026`'s registration/invocation envelope
  unchanged and grounding every field in a `0063` taxonomy/convention ID.
- Add `templates/optimization/collateral_margin_problem.template.json` and
  `.../collateral_margin_solution.template.json`: placeholder-only machine-
  readable shapes an adopter's `model_plugins.yml` entry points its
  `input_schema_uri`/`output_schema_uri` at.
- Update `agents/optimization/collateral_margin_optimization/instructions.md`
  with a `Spec-Driven Role` section naming this contract and the `0026`
  plugin path as the way a real optimizer enters the SDK.
- Close `0067`'s optimizer-boundary open question in `0063`'s own tracked
  Draft Decisions (`knowledge/short_term_markets/README.md`,
  `specs/0063-short-term-markets-domain-foundation/tasks.md`) and move
  `0067` from "reserved, not yet written" to "written, implemented, active
  as Draft" in `docs/handoff.md`, matching `0063`/`0070`/`0071`'s own
  precedent.

## Non-Goals

- No reference optimizer implementation, solver, or heuristic ships in this
  SDK for collateral/margin allocation — explicitly decided by the reviewer.
  A real optimizer remains adopter-owned and locally registered through
  `0026`, exactly like every other `optimization/` plugin.
- No behavior verification of a registered collateral optimizer's output;
  that remains `solver_diagnostics_sensitivity`'s job once a real model is
  invoked, per `0026`'s own Non-Goals.
- No numeric constraint values, real counterparty data, or real position
  data anywhere in the committed templates — placeholders only, matching
  `0026`'s `model_plugin_manifest.yml` precedent.
- No change to `0063`'s taxonomy, conventions, or lifecycle records; this
  spec references existing IDs (`concept.haircut`, `concept.margin_amount`,
  `convention.collateral.haircut_ratio`,
  `convention.collateral.margin_amount`, `lifecycle.collateral`) without
  modifying them.
- No `0064`/`0065`/`0066` runtime dependency; this contract composes only
  `0063` (taxonomy/conventions) and `0026` (envelope), both already
  implemented, so it does not wait on the repo-economics or securities-
  lending correction specs.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide a domain-specific collateral/margin problem-and-solution schema document composing `0026`'s registration/invocation envelope unchanged. | must |
| REQ-002 | Every schema field naming a collateral or margin quantity shall reference an existing `0063` `concept.*`/`convention.*`/`lifecycle.*` ID rather than inventing new vocabulary. | must |
| REQ-003 | The system shall provide committed, placeholder-only JSON templates for the problem and solution payloads, containing no real numeric constraint, counterparty, or position data. | must |
| REQ-004 | `agents/optimization/collateral_margin_optimization/instructions.md` shall state, in a `Spec-Driven Role` section, that no reference optimizer exists in this SDK and that a real optimizer is registered through `0026` using this contract. | must |
| REQ-005 | `0067`'s optimizer-boundary open question shall be marked resolved in `0063`'s tracked Draft Decisions, with the resolution, reviewer, and date recorded. | must |
| REQ-006 | The agent catalog, spec index, and `docs/handoff.md`'s Planned specs table shall reflect `0067` as written and implemented rather than reserved. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Contract consistency | The problem/solution envelope fields (`status`, `correlation_id`, `objective_value`, `diagnostics_uri`, `timestamp_utc`, `retryable`, `error_code`, `error_message_redacted`) match `adapter_contract.md`'s Invocation Output field-for-field, so `0026`'s existing review/audit handling applies unchanged. |
| NFR-002 | Repository hygiene | `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `agent-catalog` gates and the full pytest suite pass. |
| NFR-003 | Data safety | No real objective coefficient, real constraint number, real counterparty identifier, or real position appears in any committed template or doc — placeholders only. |
| NFR-004 | Honest scope | Every doc referencing this contract states plainly that no optimizer logic is supplied, matching `0026`'s own "interface, not implementation" standard. |

## Acceptance Criteria

| ID | Given / When | Then | Covers |
| --- | --- | --- | --- |
| AC-001 | Given `templates/optimization/collateral_margin_optimizer_contract.md`, when inspected | it documents the problem payload, solution payload, and states the envelope composes `0026` unchanged. | REQ-001, NFR-001 |
| AC-002 | Given the problem and solution JSON templates, when inspected | every collateral/margin field cites a `0063` `concept.*`/`convention.*`/`lifecycle.*` ID and every value is a placeholder. | REQ-002, REQ-003, NFR-003 |
| AC-003 | Given `agents/optimization/collateral_margin_optimization/instructions.md`, when inspected | its `Spec-Driven Role` section states no reference optimizer exists and names `0026` plus this contract as the registration path. | REQ-004, NFR-004 |
| AC-004 | Given `knowledge/short_term_markets/README.md` and `specs/0063.../tasks.md`, when inspected | the `0067` optimizer-boundary decision is marked resolved with reviewer and date. | REQ-005 |
| AC-005 | Given `agents/README.md`, `specs/README.md`, and `docs/handoff.md`, when inspected | `0067` appears as written/implemented, not reserved. | REQ-006 |
| AC-006 | Given the full gate suite, when run | `spec`, `docs-link`, `spec-index`, `doc-counts`, `handoff-sync`, `agent-catalog` all pass. | NFR-002 |

## Data & Dependencies

No data dependencies, no runtime code — pure contract/documentation, matching
`0026`'s own precedent. Depends on `0063` (taxonomy/convention IDs, already
implemented) and `0026` (registration/invocation envelope, already
implemented). Does not depend on `0064`/`0065`/`0066`.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A future reader assumes this contract implies a QuantSmith-built optimizer exists or is coming. | Wasted effort waiting on a build that isn't planned, or a duplicate optimizer built inside the SDK. | Every doc touched by this spec (contract, agent instructions, `0063` Draft Decisions) states explicitly that no reference optimizer ships and the boundary is adopter-plugin-only, decided by the reviewer. |
| RISK-002 | The schema drifts from `0063`'s taxonomy if `concept.haircut`/`convention.collateral.*` are later revised. | A registered optimizer's payloads reference a stale convention. | `knowledge_pack_ref` on the problem payload pins the `0063` pack version a run was framed against, the same reproducibility discipline `0071` uses for its own manifests. |
| RISK-003 | An adopter inlines real constraint numbers or counterparty data into a committed example out of convenience. | Proprietary/confidential data lands in the repo. | Both templates are placeholder-only by construction (matching `model_plugin_manifest.yml`'s own pattern); `secret-scan` remains the deterministic backstop. |

## Assumptions & Open Questions

- Assumption: the four constraint families named in `0067`'s reserved scope
  (eligibility, concentration, counterparty/netting, substitution) are
  sufficient for a first contract; a fifth family can be added the same way
  if a concrete optimizer needs one.
- Assumption: `templates/optimization/` (alongside `model_plugin_manifest.yml`)
  is the right home for this schema, not `adapters/model_plugin/`, because
  that directory's own Design Rule excludes domain objective/constraint
  shape.
- Open question: once a real optimizer is registered against this contract,
  should `0067` gain a structural JSON-Schema validator (mirroring
  `0063`'s `short_term_markets_knowledge.py` pattern), or does the existing
  `model-plugin` gate's manifest-level checking stay sufficient?

## Exceptions

None.
