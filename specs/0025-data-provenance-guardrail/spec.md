# Spec: Data Provenance & Synthetic-Data Disclosure Guardrail

- **ID:** 0025-data-provenance-guardrail
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-09

## Problem & Context

`agents/role_operations/` (spec `0024`) and several existing groups
(`agents/analytics/dashboard_design`, `agents/analytics/data_storytelling`)
produce content backed by data and visuals. Nothing in the SDK previously
made source-traceability a first-class, checked property: `dashboard_design`
and `data_storytelling` already require numbers to trace to a governed
source, but nowhere was there an explicit priority stack (real data before
synthetic) or a disclosure mechanism for when synthetic data is used —
despite synthetic/seeded data appearing throughout the SDK's own reference
runtimes (e.g. `sec_lending.py`'s synthetic universe, several `pipelines/`
test fixtures). A reviewer had no single, checked artifact to consult for
"where in this report is the data not real."

## Goals

- Add a cross-cutting standard, `instructions/data_provenance.md`, defining
  the priority stack (actual data → sampled actual data → synthetic, as a
  documented last resort) and the disclosure requirement.
- Add `templates/docs/synthetic_data_disclosure.md`, the companion report
  that lists every location synthetic data is used, not a summary.
- Add a gate, `data-provenance`, that validates a disclosure artifact's
  required fields when one exists and advisorially flags likely undisclosed
  synthetic-data language in generated (non-scaffold) artifacts.
- Wire the standard into `agents/role_operations/` (all four agents,
  explicitly called out in `rapid_scaffolder` since it is the one most
  likely to reach for synthetic data to make a scaffold runnable) and add a
  lightweight cross-reference from the two existing visual/narrative
  standards (`dashboard_design`, `data_storytelling`).

## Non-Goals

- No automated real-vs-synthetic classifier; the gate's heuristic scan looks
  for synthetic-data *language* in generated artifacts, not statistical
  evidence that data is fabricated — same honestly-scoped limitation as the
  `leakage` gate.
- No retroactive audit of existing runtimes' synthetic-data fallbacks (e.g.
  `sec_lending.py`'s `_build_synthetic()`); those are documented, labeled
  demo/test paths, not the "content produced for a decision" case this
  guardrail targets. Extending disclosure requirements to runtime demo
  fixtures is a candidate follow-up, not this slice.
- No change to `agents/analytics/dashboard_design` or `data_storytelling`
  beyond a one-line cross-reference each; a fuller rework of those groups'
  provenance handling is out of scope here.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall define a priority stack (actual data, then sampled actual data, then synthetic as a disclosed last resort) as a documented standard. | must |
| REQ-002 | The system shall provide a Synthetic Data Disclosure template that requires every occurrence of synthetic data to be listed individually, with its reason and generation method. | must |
| REQ-003 | The system shall provide a gate that validates a disclosure artifact's required fields when present, and advisorially flags generated artifacts mentioning synthetic data with no matching disclosure. | must |
| REQ-004 | `agents/role_operations/` shall reference the standard in its shared guardrails, with `rapid_scaffolder` explicitly requiring disclosure of any synthetic data used to make a scaffold runnable. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Gate hygiene | Degrades gracefully (reports "not applicable," no findings) when no disclosure artifact and no synthetic-data language exist. |
| NFR-002 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `secret-scan`, `role-context`, `data-provenance` gates and the full pytest suite pass. |
| NFR-003 | Heuristic honesty | The gate's advisory synthetic-language scan is documented as a heuristic (false positives/negatives expected), not a completeness guarantee, matching the `leakage` gate's precedent. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a filled Synthetic Data Disclosure artifact with all required fields, when the `data-provenance` gate runs, then each field is reported declared and no findings result. | REQ-002, REQ-003 |
| AC-002 | Given a report-shaped artifact under `docs/` that mentions synthetic/simulated data with no disclosure artifact anywhere in the tree, when the gate runs, then it is flagged. | REQ-003 |
| AC-003 | Given the same artifact from AC-002 once a matching disclosure artifact exists, when the gate re-runs, then the finding clears. | REQ-003 |
| AC-004 | Given no disclosure artifact and no synthetic-data language anywhere scanned, when the gate runs, then it reports cleanly with no findings. | NFR-001 |
| AC-005 | Given `agents/role_operations/rapid_scaffolder/instructions.md`, when inspected, then it explicitly requires disclosing any synthetic data used to make a scaffold runnable. | REQ-004 |

## Data & Dependencies

No data dependencies; no runtime code. A POSIX shell gate consistent with
the existing `hooks/stages/` scripts, adding no new tooling dependency.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | The heuristic synthetic-language scan misses a disclosure obligation phrased without the scanned keywords (e.g. "illustrative figures," "for demonstration only"). | An undisclosed synthetic-data use ships unflagged. | Documented as a heuristic, not a guarantee, in the gate's header comment and this spec's Non-Goals/NFR-003; the deterministic field-validation check (AC-001) is the stronger guarantee once a disclosure artifact exists, and human review remains the backstop, matching the constitution's stance on heuristic gates generally. |
| RISK-002 | A false-positive flag on the SDK's own instructional use of "synthetic" (e.g. in `agents/deep_learning/generative_models/`). | Noise erodes trust in the gate. | The scan excludes `agents/`, `templates/`, `prompts/`, `instructions/`, `hooks/`, `specs/` — the same scaffold-directory exclusion `secret-scan` already uses — so only report/example-shaped output is scanned. |
| RISK-003 | Disclosure becomes a checkbox exercise (filled once, never updated as the artifact changes). | Stale disclosure misleads a reader. | `instructions/data_provenance.md`'s Standards state the disclosure travels with the artifact; this is a documentation/process control, not something the gate itself can enforce mechanically in this slice. |

## Assumptions & Open Questions

- Assumption: role_operations agents are the right first adopters (spec
  `0024` just shipped and already carries a "no fabrication" guardrail this
  extends naturally); `dashboard_design`/`data_storytelling` get a
  lightweight cross-reference rather than a full rework in this slice.
- Open question: should the disclosure requirement eventually extend to
  runtime demo/test fixtures that use synthetic data by design (e.g.
  `sec_lending.py`), or is labeling them "synthetic demo mode" in their own
  docstrings/READMEs sufficient given they are not decision-facing content?

## Exceptions

None.
