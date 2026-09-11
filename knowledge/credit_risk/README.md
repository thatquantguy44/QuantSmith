# Credit Risk Domain Pack (spec `0072`)

Canonical, versioned, U.S.-first credit risk knowledge for QuantSmith agents and
runtimes. Owned by
[`specs/0072-credit-risk-domain-foundation/`](../../specs/0072-credit-risk-domain-foundation/).

This pack is the credit counterpart to
[`knowledge/short_term_markets/`](../short_term_markets/) (`0063`) and reuses its
record envelope deliberately, so the two are one system rather than two dialects.
Collateral, haircut, margin, and eligibility vocabulary is **not** redefined
here — it is referenced from `0063`.

## What this pack is

A knowledge and validation contract. It defines what credit terms mean, what
basis a measure is stated on, what states a credit exposure or model can be in,
what makes a record evidence rather than prose, and what a later runtime must
reproduce to claim compatibility.

## What this pack is not

- **Not a model, and not model validation.** Nothing here scores an applicant,
  measures a provision, or computes capital. Structure can be automated;
  validation under supervisory model-risk expectations requires named,
  independent human review.
- **Not legal, accounting, tax, or regulatory-capital advice.** It identifies
  authoritative material, concepts, applicability, and review dates. Whether a
  rule applies to a particular institution or exposure is a qualified owner's
  decision.
- **Not a source of credit data.** Every committed example is synthetic. No
  consumer PII, loan-level tape, bureau attribute value, credit file, internal
  counterparty term, or licensed vendor or agency methodology text is stored
  here, permanently and by requirement (`0072` NFR-006).
- **Not multi-jurisdiction.** The pack declares `jurisdiction: US`. Extensions
  must declare their own; they do not inherit U.S. defaults.

## Files

| File | Holds |
| --- | --- |
| `taxonomy.json` | Stable IDs and deterministic alias resolution for entities, facilities, exposures, measures, roles, rating and score concepts, default definitions, and processes — plus the non-interchangeable sets. |
| `conventions.json` | Measurement basis for every credit measure: units, horizon, conditioning, default definition, collateral treatment, discounting, currency, calibration population, viewpoint, and loss sign. |
| `lifecycles.json` | Three transition graphs: credit exposure state, credit approval and limit management, and the model lifecycle. |
| `decision_paths.json` | Per-workflow consumer-decision classification and the obligations that attach to it. |
| `governance.json` | Model governance artifact requirements and the deployability predicate. |
| `workflows.json` | The six end-to-end credit workflows: stages, participating agents, inputs, artifacts, gates, human decision points, and runtime boundary. |
| `coverage.json` | Capability surface mapped to current artifacts, coverage level, limitation, and owning spec. |
| `golden_cases.json` | Deterministic cases and identities later runtimes must reproduce. |
| `gap_register.md` | Observed gaps with evidence, severity, disposition, and owning spec. |
| `source_policy.md` | Evidence hierarchy, conflict resolution, licensing, and freshness rules. |

## Record envelope

Every machine-readable record carries `id`, `record_type`, `name`,
`jurisdiction`, `knowledge_as_of`, `effective_from`, `effective_to`,
`knowledge_class`, `source_refs`, `review_status`, `review`, and `supersedes`.
The interval policy is `effective_from` inclusive, `effective_to` exclusive.

`knowledge_as_of` and the effective interval are **separate axes**. A standard
may be issued today and effective in two years; a historical question must pass
the knowledge check first (was this knowable then?) and then the effective check
(did it apply to the period being measured?). Collapsing the two is how a later
rule silently rewrites an earlier answer.

`knowledge_class` extends `0063`'s enum with `accounting_standard` and
`regulatory_supervisory_rule`, because those have different freshness and
effective-date behavior from a market observation and must not share a class.

## The two things credit adds

`0063` is a measurement contract. Credit needs a measurement contract **plus a
decision contract**, because a credit output is often an act with a subject.

1. **`decision_paths.json` — the decision contract.** A workflow that supports a
   decision about an identifiable consumer must derive principal reason codes,
   record its policy version, cutoff, and overrides, carry an empty
   protected-attribute feature set, and expose a disparate-impact hook — *and*,
   because attribute absence alone certifies nothing, declare substantive
   fairness testing: a protected-class testing basis (an estimate of which is
   itself never a feature), a disparity metric with a supplied threshold
   measured at the applied cutoff, per-feature proxy association, and a
   less-discriminatory-alternative search on breach. A path that cannot do those
   is only representable as `decision_support_only` with sole-basis adverse
   action prohibited. The unsafe configuration is unrepresentable, not merely
   discouraged.
2. **The evidence boundary.** A value derived by a language model enters as a
   `0071` artifact inside a `0070` envelope, with resolvable source spans, an
   assumption-ledger entry, and replay, labeled `derived_evidence`. Promotion to
   a decision input requires named human review. No automated path performs that
   promotion.

Deployability in `coverage.json` is likewise **computed**, not asserted: an
entry is deployable only when every governance artifact in `governance.json`
resolves. There is no `deployable: true` field for an author to set.

## Review status

Records are `draft`, `reviewed`, `superseded`, or `retired`. Promotion to
`reviewed` requires a named credit-domain reviewer, review date, review scope,
supporting evidence, and no unresolved severity-high gap affecting the record.

**94 of 109 records are `reviewed`; 15 remain `draft`.** Joshua Lutkemuller,
CFA — the repository owner and this spec's approver — is the named reviewer,
recorded 2026-09-11. Stated plainly: this is the account owner's own
attestation for a portfolio SDK, not an independent third-party credit
officer's or model validator's sign-off (see `gap_register.md`'s
`G-0072-001`). The 15 records still `draft` carry a `blocked_by_gap_ids`
field naming an open, high-severity gap (`G-0072-002`: no wholesale/
counterparty measurement runtime; `G-0072-005`: no fairness harness) — the
validator refuses `reviewed` status on any record whose named gap is still
open, however complete its review object looks. Naming a reviewer was
necessary, not sufficient.

## Using this pack

Agents resolve **basis before arithmetic**. Before computing with a PD, resolve
its horizon, conditioning, and default definition; before combining an LGD,
resolve whether it is expected or downturn; before treating a number as
exposure, resolve whether it is notional, drawn balance, or EAD. A missing
convention is a question to ask, never a default to assume.

Validation lives in
[`src/quantsmith/pipelines/credit_risk_knowledge.py`](../../src/quantsmith/pipelines/credit_risk_knowledge.py)
and exposes validation helpers only — no scoring, provisioning, or capital API.

```sh
PYTHONPATH=src python3 -m quantsmith.pipelines.credit_risk_knowledge
PYTHONPATH=src pytest -q tests/test_credit_risk_knowledge.py
```
