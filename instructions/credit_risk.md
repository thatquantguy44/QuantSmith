# Credit Risk

Operating standard for any agent touching credit risk. Owned by spec
[`0072`](../specs/0072-credit-risk-domain-foundation/); the canonical contracts
live in [`knowledge/credit_risk/`](../knowledge/credit_risk/).

Read [`point_in_time.md`](point_in_time.md),
[`model_validation.md`](model_validation.md), and
[`data_provenance.md`](data_provenance.md) alongside this. They hold the general
rules; this document holds what credit adds.

## 1. Resolve basis before arithmetic

The single most common credit error is not a wrong formula. It is a right
formula applied to operands stated on incompatible bases, which reconciles
internally and fails externally.

Before computing with a number, resolve:

| Quantity | Resolve |
| --- | --- |
| PD | horizon, conditioning (through-the-cycle / point-in-time), default definition |
| LGD | expected or downturn, discounting, cost treatment, workout window |
| Exposure | notional, drawn balance, or EAD; gross or net of collateral |
| ECL | twelve-month or lifetime; IFRS 9 or CECL; discount rate |
| Rating / score | ordinal grade, model score, or band — none are probabilities |

A missing convention is **a question to ask, never a default to assume**. If a
caller gives you a "PD" with no basis, say what you need rather than picking one.
`knowledge/credit_risk/taxonomy.json`'s ambiguity rules name exactly what each
ambiguous term requires.

Terms that are **not** interchangeable, and that agents most often collapse:
obligor / facility / exposure / counterparty; PD / observed default rate;
TTC PD / PIT PD; one-year PD / lifetime PD; LGD / loss rate / recovery rate;
EAD / notional / drawn balance / CCF; ECL / impairment / provision / charge-off;
charge-off / write-off; rating grade / score / band; and every pair of default
definitions.

Collateral is counted **once**. It belongs in LGD, not also in EAD.

## 2. A consumer decision is a regulated act

Where a workflow supports a decision about an identifiable consumer applicant or
borrower, the obligations in `decision_paths.json` are structural, not advisory:

- principal reason codes derivable from the model inputs that drove the outcome;
- decision policy version, cutoff, and any override recorded;
- protected attributes absent from the feature set — where an institution
  lawfully holds them, they are for segregated fairness testing only;
- a callable disparate-impact hook.

A path that cannot meet all four is **decision-support-only** and must not be the
sole basis of an adverse action. This is not a judgement call to make per
request: the validator rejects the unsafe configuration.

Adverse action reason ordering must be deterministic. Ties break on a declared
stable feature order, never on dictionary insertion or raw float comparison —
two runs on the same application must disclose the same reasons.

## 3. Credit leakage is not market leakage

`point_in_time.md` covers look-ahead generally. Credit adds six modes, all
enforced by `rule.pit.*` in `golden_cases.json`:

1. **Outcome-window alignment** — a value whose performance window closes after
   the decision date may be a label, never a feature of that decision. This is
   the mode most likely to make a credit model look excellent offline.
2. **Attribute as-of versus refresh date** — a refreshed bureau or internal
   attribute is not the value that was knowable at decision time.
3. **Reject inference** — any claim about rejected applicants' outcomes is a
   declared model assumption with a stated method, never an observation.
4. **Scenario vintage** — a macroeconomic scenario may not be used before its
   publication date, even where its projection period covers the target date.
5. **Restatement and re-rating backfill** — a restated financial or a re-rating
   must not overwrite what was knowable at the decision date.
6. **Survivorship** — closed and charged-off accounts stay in the population.
   Dropping them biases performance upward.

## 4. Text-derived values are evidence, not inputs

A covenant extracted from an agreement or a risk flag inferred from a filing is
useful and unverified. It enters as a `0071` artifact inside a `0070` envelope
with resolvable source spans, an assumption-ledger entry, and replay, labeled
`derived_evidence`.

Promotion to a decision input requires **named human review**. No agent performs
that promotion, and no agent may cite a derived value as though it were a
sourced fact.

## 5. Say what a model is not validated for

Structure can be automated; validation cannot. An agent may check that a model
card, validation evidence, challenger comparison, monitoring thresholds,
override log, owner, and fallback policy are all present — that is what the
deployability predicate in `governance.json` computes. It may never conclude
from that check that a model is *correct*, and it may never describe its own
output as validation.

Where a model lacks any of those artifacts, say which one is missing rather than
qualifying the answer vaguely.

## 6. Never fabricate credit data

No consumer PII, credit file, loan tape, bureau attribute value, internal
counterparty term, MNPI, or licensed vendor or agency methodology text belongs
in this repository — and none may be invented to fill a gap in an example. Every
committed fixture is synthetic and disclosed per
[`data_provenance.md`](data_provenance.md).

If a demonstration needs data the repository cannot hold, say so and describe
what the adopter must supply. An invented loan tape that looks plausible is
worse than an absent one.

## 7. Jurisdiction is declared, never inherited

The pack is U.S.-first and declares `jurisdiction: US`. International framework
text is not the applicable rule for any institution — national implementation
governs. An answer that does not know its jurisdiction is not an answer.
