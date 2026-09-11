# Synthetic Data Disclosure — Credit Risk Worked Example

- **Artifact:** `examples/credit_risk_worked_example/`
- **Author:** QuantSmith credit-risk maintainers (specs `0072`, `0073`, `0074`, `0077`)
- **Last updated:** 2026-09-11
- **Reviewer / sign-off:** Cascadia's document-intelligence step is
  structurally approved by the recorded `spec0071` fixture review object
  carried through unchanged, matching `0077`'s own disclosure. The wholesale
  and retail steps use synthetic institution/counterparty/applicant data;
  production and real credit-decision use are not approved.

## Priority Check

- [x] Actual sourced data was considered first.
- [x] Real obligor, counterparty, and applicant data were intentionally not
      used because this artifact exists to prove three already-tested
      runtimes (`0073`, `0074`, `0077`) compose into one coherent narrative,
      not to report on a real institution's book. Real credit-committee
      inputs, real counterparty names, and a real retail applicant
      population would each raise separate confidentiality, PII, and
      licensing questions this cross-cutting demonstration does not need to
      resolve.

## Disclosure Table

| Location (section / chart / field) | What's synthetic | Why real data wasn't used | Generation method | Real-data follow-up |
| --- | --- | --- | --- | --- |
| `document_intelligence/documents/credit-memo-cascadia-*.txt` | Fictional obligor ("Cascadia Fabricators, Inc."), leverage/covenant commentary — no real obligor, agreement, or counterparty is named or implied | Same rationale as `0077`'s own committed example: proving the admission-boundary wiring needs no real, licensed document | Fixed strings and timestamps in `credit_risk_worked_example.run_document_intelligence_step`, delegating to `0071`'s unchanged deterministic producer; no random sampling, no model call | Register and approve a real, licensed credit-document corpus before any real-document ingestion (`0072` gap `G-0072-006`) |
| `report.json`'s `wholesale_measurement` (PD, LGD, risk weight, drawn balance, limit, CCF for Cascadia and its two peer counterparties) | All facility, obligor, and counterparty identifiers and figures are fictional; PD/LGD/risk-weight values are illustrative credit-committee assumptions, not a model output | `0073` deliberately ships no rating/PD/LGD estimation model (adopter-plugin-only); this worked example supplies the same kind of caller-provided inputs `0073`'s own acceptance tests use | Fixed literal values chosen in `run_wholesale_measurement_step` to exercise both a limit breach (Northfield) and a concentration-threshold breach (Cascadia's share), not sampled | An adopter would substitute their own registered rating/PD/LGD source; the measurement, limit, and concentration arithmetic itself does not change |
| `report.json`'s `retail_fairness` (all 300 synthetic applicants) | Every applicant ID, score, protected-class flag, and feature value is synthetic | `0074` deliberately ships no scorecard or protected-class estimator; a real retail applicant population would also be regulated consumer data this demonstration has no standing to hold | `random.Random(2026)` (seeded, deterministic); scores drawn `gauss(680, 45)` / `gauss(635, 45)` for reference/protected groups, `zip_income_proxy` drawn `gauss(72000, 11000)` / `gauss(52000, 11000)` — the same generation pattern `tests/test_retail_fairness_harness.py`'s own `_population()` helper uses, reseeded here for a reproducible committed example | An adopter would run `run_fairness_harness` against their own scored, real applicant population; the disparity/proxy/LDA-search arithmetic itself does not change |

## Traceability

- The document-intelligence step's evidence is hash-linked by
  `document_intelligence/text_intelligence_manifest.json`, produced by
  `0071`'s unchanged producer inside a `0070` run envelope, exactly like
  `0077`'s own committed example.
- The wholesale and retail steps are pure, deterministic functions
  (`quantsmith.pipelines.wholesale_credit_measurement`,
  `quantsmith.pipelines.retail_fairness_harness`) with no I/O of their own;
  `report.json` is their literal computed output, not a hand-typed summary.
- `tests/test_credit_risk_worked_example.py` proves the composition,
  including that regenerating the example reproduces `report.json` exactly.

## Open Items

- None. This artifact is a demonstration, not a production report; no
  further real-data follow-up is tracked here beyond what `0072`'s own gap
  register already names for each underlying spec.
