# Spec: Dataset Investigator

- **ID:** 0099-dataset-investigator
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Approver:** — (pending owner review)
- **Last updated:** 2026-10-07

> WHAT and WHY only. Implementation lives in `plan.md`.

## Problem & Context

Given a new tabular dataset, an analyst needs to know: what is in it, what is
unusual or important, what can be trusted, which hypotheses are worth testing,
and what to analyze next. Today that work is ad hoc exploratory analysis whose
numbers live in a notebook nobody can rerun, and when a language model is asked
to help it states numbers it computed itself — or did not compute at all.

The owner asked for an on-demand **Dataset Investigator**: an agentic system
that inspects a dataset, measures it with deterministic Python tools, turns the
measurements into ranked findings and testable hypotheses, tests those
hypotheses with further registered tools, validates every claim, and hands back
both a report and a Python package that reproduces every result.

The governing principle: **every analytical claim is traceable to deterministic
evidence and reproducible from packaged Python code.** The language model plans,
proposes hypotheses, chooses registered tools, interprets, and writes; it never
computes a number that appears in a finding.

The repository has fragments but nothing joined up: a minimal `EDAAgent`
(`agentic_code_tools/eda.py`, min/max/mean only), contract-only
`eda-specialist-agent` and `data_quality` agents, `0080`'s grounding validator
(rejects unbacked numbers), and the `0070` run envelope. None investigates,
tests hypotheses, or exports reproducible code.

## Goals

- One command or one on-demand workflow that turns a dataset into an
  investigation bundle: report, findings, hypotheses, and an installable
  analysis package.
- Numbers come only from registered, versioned, deterministic tools; every
  finding names the function, parameters, and evidence that produced it.
- A hypothesis loop that can *reject* a plausible reading (e.g. a rate rise
  that is a denominator effect), not just confirm observations.
- A validator that keeps unsupported, unreproducible, or overconfident claims
  out of the findings.
- A full rerun, and the reproduction of any single finding, with no language
  model involved.

## Non-Goals

Version 1 shall not:

- Train predictive models or tune hyperparameters (anomaly scorers are fitted
  for scoring only, never offered as models).
- Delete, impute, or modify observations; modify the source dataset; remove
  features; or write back to any source system.
- Make financial or business decisions or recommendations beyond "what to
  analyze next".
- Execute language-model-generated code. Generating new analysis tools
  (controlled extension) is version 2 — see Follow-ups in `tasks.md`.
- Read SQL, Snowflake, Databricks, Excel, APIs, or multiple related tables
  (future inputs).
- Present a statistical association as a cause.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall load a dataset read-only from CSV, Parquet, a pandas DataFrame, or a Polars DataFrame, and fingerprint it (SHA-256 of the file bytes for a file; a canonical content hash for an in-memory frame), recording rows and columns. A format whose optional reader is not installed shall fail with an error naming what to install. | must |
| REQ-002 | The system shall classify each column into a semantic role — `identifier`, `entity_identifier`, `timestamp`, `continuous_numeric`, `discrete_numeric`, `categorical`, `boolean`, `binary_target`, `multiclass_target`, `free_text`, `constant` — with the evidence for each role (dtype, cardinality ratio, uniqueness, missingness, name and value patterns). Caller-supplied roles, target, and timestamp override inference. An identifier shall never be analyzed as a numeric measure. | must |
| REQ-003 | The system shall plan which analyses to run from the profile, by declared rules: skip temporal analysis with no timestamp; skip supervised analyses with no target; run entity analyses when entity identifiers exist; run class-balance diagnostics for a binary or multiclass target; sample (with a recorded seed) or skip expensive methods above configurable size thresholds. Every planned and skipped analysis shall carry a reason. A language-model planner may only add, drop, or reorder analyses from the registry; an unregistered analysis is rejected. | must |
| REQ-004 | The system shall perform all numerical analysis through registered deterministic Python functions — at least `profile_dataset`, `analyze_missingness`, `analyze_duplicates`, `analyze_distributions`, `analyze_categories`, `calculate_correlations`, `compare_segments`, `compare_target_rates`, `detect_outliers`, `detect_distribution_shift`, `analyze_time_series`, `analyze_entity_concentration` — each returning a structured, JSON-serializable result. | must |
| REQ-005 | Tools shall be exposed only through a registry that records each tool's name, category, version, and parameter schema. Only registered tools may execute, and only with parameters that validate against the schema. Every execution shall be recorded: tool, version, parameters, input fingerprint, result hash, and duration. | must |
| REQ-006 | The registry shall cover six investigation families: data quality (missing values, duplicate rows and identifiers, impossible values, constant and near-constant columns, unexpected types, cardinality issues); distributions (mean, median, quantiles, variance, skew, kurtosis, tail concentration, category frequencies); relationships (Pearson, Spearman, target-rate comparisons, mutual information, grouped statistics); segmentation (subgroups by categorical and value bands); temporal (distribution and target drift, rolling statistics, trend and regime change, period comparisons); and anomalies (robust z-score, Mahalanobis distance, Isolation Forest, and Local Outlier Factor). | must |
| REQ-007 | The system shall derive candidate findings from tool results by declared rules, each carrying its claim, evidence, method, module, function, parameters, and execution id, and rank them by an interestingness score I = w₁M + w₂S + w₃P + w₄A (magnitude, statistical support, prevalence, actionability), each component in [0, 1] and recorded, with configurable weights. Statistical support shall use p-values adjusted for every test run in the investigation (Benjamini–Hochberg). The report shall surface the top findings (default 10, bounded 5–15). | must |
| REQ-008 | The system shall turn findings into testable hypotheses, each naming a registered test, its parameters, and a predicted outcome with a declared decision rule; execute the test; classify the hypothesis `supported`, `rejected`, or `inconclusive` from the evidence by that rule; and generate follow-up hypotheses, within a bounded number of rounds and tool calls. | must |
| REQ-009 | The system shall generate 5–10 research questions, each linked to the findings or hypotheses that motivated it and to a registered tool that could answer it, or marked as needing a tool the registry lacks. | should |
| REQ-010 | Before publication a validator shall check every finding: numerical evidence exists; every number stated in the claim is present in the evidence; the wording does not overstate the evidence (including causal language); sample sizes meet thresholds; the function used fits the column roles; the result is statistically or practically meaningful; it is not a duplicate; re-executing the recorded call reproduces the evidence; and confidence is calibrated to the evidence. Each finding gets `VALIDATED`, `WEAK_EVIDENCE`, `INCONCLUSIVE`, or `REJECTED`; a rejected claim shall never appear as a finding. | must |
| REQ-011 | The system shall write a report with a fixed section order — dataset, executive summary, data quality, key findings, anomalies, hypotheses, questions worth investigating, recommended next analysis — plus `findings.json`, `hypotheses.json`, and figures (Matplotlib PNG) drawn only from recorded aggregate results. | must |
| REQ-012 | The system shall export, for every run, an installable analysis package containing the **actual** analysis modules that executed (byte-identical to the runtime's modules, with their hashes in the manifest), a pipeline that replays the recorded executions, a manifest mapping every finding to its module, function, parameters, and expected evidence, generated tests, a README, a pinned `requirements.lock`, the investigation config, and an example; with a high-level `investigate(path)` API, importable individual modules, and a `dataset-investigator` command. | must |
| REQ-013 | The exported package shall reproduce any single finding from the command line (`dataset-investigator reproduce F007 --data PATH`): it first checks the dataset fingerprint, re-executes the recorded call, compares the result with the recorded evidence within a declared tolerance, and reports reproduced or not with a distinct exit code for mismatch and for a wrong dataset. | must |
| REQ-014 | The system shall re-run a whole investigation without any language model — a deterministic planner, rule-based finding and hypothesis templates, and a template report — from the package alone or from the runtime. | must |
| REQ-015 | Each run shall record metadata: run id, Python and library versions, random seeds, dataset fingerprint and dimensions, execution timestamp, tools invoked with versions and parameters, and the analysis configuration. | must |
| REQ-016 | The investigation shall be callable on demand three ways: a `quantsmith-dataset-investigator` command (`analyze`, `run-tool`, `validate`, `report`, `export`, `reproduce`); a saved Claude Code workflow, `dataset-investigator`, that takes a dataset path and options as arguments and runs the language-model roles (planner, investigator, validator review, report writer) around the deterministic command; and an agent contract under `agents/analytics/dataset_investigator/` listed in the agent catalog. | must |
| REQ-017 | Language-model roles shall receive only the profile, column roles, and structured evidence — never raw rows — and shall return output that validates against a schema (planner: registered analyses only; investigator: registered tool plus valid parameters). Any number in language-model-written text that is not backed by recorded evidence causes that text to be rejected. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Reproducibility | Same data, configuration, and seed give byte-identical `findings.json`, `hypotheses.json`, and `manifest.json` (timestamps and durations excluded, and listed as excluded). |
| NFR-002 | Data handling | The source is never modified and nothing is written outside the run directory. Reports and model context carry aggregates only, no raw rows; a segment smaller than the minimum cell size (default 10) is not reported. Columns the caller flags as PII have their values masked in every artifact. |
| NFR-003 | Performance and cost | The deterministic pass over 1,000,000 rows × 20 columns completes in under 120 s on a CI runner (benchmark, skipped with a recorded reason on an under-provisioned runner); expensive methods sample above a configurable threshold (default 200,000 rows); the hypothesis loop is capped (default 3 rounds, 25 tool calls). |
| NFR-004 | Dependencies | The runtime needs the optional `investigator` extra (pandas, scipy, scikit-learn, pyarrow, pydantic, PyYAML, Matplotlib); the rest of `quantsmith` does not, and importing `quantsmith` never imports the investigator. Polars is accepted if installed but never required. No network access. |
| NFR-005 | Scope safety | No code path trains a predictive model, imputes, deletes, or writes back; the runtime contains no `eval`/`exec` and never executes language-model-generated code. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given the synthetic fixture as CSV, Parquet, a pandas frame, and (when installed) a Polars frame, when loaded, then all give the same profile and content hash, and each file's fingerprint is the SHA-256 of its bytes; given an unsupported format or a missing optional reader, then the error says what is needed. | REQ-001 |
| AC-002 | Given a fixture with `transaction_id`, `customer_id`, `transaction_date`, `amount`, `country`, `device_id`, `note`, `is_fraud`, when inspected, then the roles are identifier, entity_identifier, timestamp, continuous_numeric, categorical, categorical, free_text, binary_target with evidence; an integer id column is an identifier and appears in no numeric analysis; a caller override wins. | REQ-002 |
| AC-003 | Given profiles with and without a timestamp, a target, and entity identifiers, and one above the size threshold, when planned, then each rule fires with its reason and sampling records its seed; given a language-model plan naming an unregistered analysis, then it is rejected. | REQ-003, REQ-017 |
| AC-004 | Given a fixture with planted duplicate rows, duplicate identifiers, a constant and a near-constant column, a negative amount, a future timestamp, and a mixed-type column, when quality tools run, then each defect is reported with its exact count. | REQ-004, REQ-006 |
| AC-005 | Given numeric and categorical columns, when distribution tools run, then every statistic matches a numpy/scipy reference within 1e-9 and category frequencies sum to the non-missing count. | REQ-004, REQ-006 |
| AC-006 | Given a planted 5.7× international fraud rate and known correlations, when relationship and segment tools run, then the rates and ratio match hand counts, Pearson and Spearman match scipy, and mutual information is deterministic. | REQ-006 |
| AC-007 | Given planted univariate and multivariate outliers, when anomaly tools run, then robust z and Mahalanobis recover them, and Isolation Forest and LOF flag them with a fixed seed and give identical counts on a second run. | REQ-006, NFR-001 |
| AC-008 | Given a planted shift in `amount` after a known date, when temporal tools run, then KS and PSI flag the shift and locate the breakpoint; given no timestamp, then no temporal tool runs. | REQ-006, REQ-003 |
| AC-009 | Given a set of candidate findings, when ranked, then order follows I with recorded components; changing a weight reorders as computed by hand; p-values are BH-adjusted across all tests; the report shows between 5 and 15. | REQ-007 |
| AC-010 | Given the overnight fixture (fraud share rises 1–4 AM, fraud count flat, volume down 62%), when investigated, then the hypothesis "fraud volume increases overnight" is `rejected` with the counts as evidence, a denominator-effect follow-up is `supported`, and the loop stops at its caps. | REQ-008, NFR-003 |
| AC-011 | Given an investigation, when questions are generated, then there are 5–10, each linked to a finding or hypothesis and to a registered tool or marked as needing a new one. | REQ-009 |
| AC-012 | Given claims with a number absent from the evidence, causal wording, a sample below threshold, a duplicate, and tampered evidence, when validated, then they are `REJECTED`, `REJECTED`, `WEAK_EVIDENCE`, merged, and `REJECTED` respectively, and no rejected claim appears under key findings. | REQ-010, REQ-017 |
| AC-013 | Given a completed run, when the report is written, then its sections appear in the declared order and `findings.json` and `hypotheses.json` validate against their schemas. | REQ-011 |
| AC-014 | Given an exported package, when inspected, then every analysis module is byte-identical to the runtime module (hashes match the manifest), every reported finding is in the manifest, and the package's own tests pass when run against the fixture. | REQ-012 |
| AC-015 | Given an exported package and the fixture, when `dataset-investigator reproduce` runs for each finding, then each reproduces (exit 0); given a modified dataset, then it exits with the wrong-dataset code; given tampered recorded evidence, then it exits with the mismatch code. | REQ-013 |
| AC-016 | Given a completed run, when it is re-run with no language model from the package and from the runtime, then `findings.json`, `hypotheses.json`, and `manifest.json` are byte-identical to the deterministic original; and a run the model roles took part in records their contributions (chosen analyses, proposals in order, review, narrative) in the manifest, and its package rerun replays them with no model to byte-identical `findings.json` and `hypotheses.json`. | REQ-014, NFR-001 |
| AC-017 | Given a run, when `run_metadata.yaml` is read, then it has every field REQ-015 lists. | REQ-015 |
| AC-018 | Given the repository, when checked, then the command runs `analyze` end to end on the fixture; the saved workflow's `meta` parses, names its phases, passes only aggregates and evidence to reasoning agents, and runs commands only through the investigator command; and the agent contract and catalog gates pass. | REQ-016, REQ-017 |
| AC-019 | Given a fixture with a sentinel string planted in an identifier and in a free-text value, and a PII-flagged column, when the context for every language-model role is built, then it contains neither the sentinel nor any PII value, and no artifact contains a PII value or a segment below the minimum cell size. | REQ-017, NFR-002 |
| AC-020 | Given a run, when it completes, then the source file's hash is unchanged, no file exists outside the run directory, and a source scan finds no `eval`, `exec`, model-training, imputation, or write-back call. | NFR-002, NFR-005 |
| AC-021 | Given 1,000,000 synthetic rows × 20 columns, when the deterministic pass runs, then it completes in under 120 s (skipped with a recorded reason on an under-provisioned runner). | NFR-003 |
| AC-022 | Given the runtime, when its imports are scanned, then it imports only the standard library, the `investigator` extra's libraries, numpy, and its own modules (Polars only behind a guarded import), and importing `quantsmith` does not import it. | NFR-004 |

## Data & Dependencies

- Inputs: caller-supplied files or frames; no connector, credential, or network
  access. Synthetic fixtures only in this repository (`0025` disclosure).
- Builds on: `0080` grounding (unbacked-number rejection, causal-language
  flags); `0070` run envelope for audit; `0081` domain packs as a later,
  optional source of column semantics and additivity.
- Libraries: the `investigator` extra (pandas, scipy, scikit-learn, pyarrow,
  pydantic, PyYAML, Matplotlib), locked in `uv.lock`.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Many tests produce spurious "findings" (multiple comparisons). | False discoveries reported as facts. | BH adjustment across every test in the run (REQ-007); validator meaningfulness and sample-size checks (REQ-010). |
| RISK-002 | The language model states numbers it did not get from a tool, or overstates them. | Unbacked claims in the report. | Grounding check rejects unbacked numbers; validator wording and calibration checks; reasoning roles see evidence only (REQ-010, REQ-017). |
| RISK-003 | Ratios and rates mislead (denominator effects, Simpson's paradox). | Wrong conclusions. | The hypothesis loop tests counts against rates and stratified comparisons (REQ-008, AC-010). |
| RISK-004 | Identifiers or codes analyzed as quantities. | Meaningless statistics and findings. | Semantic roles gate every tool's eligible columns (REQ-002). |
| RISK-005 | Raw or personal data reaches the model or the report. | Privacy breach. | Aggregates-only context, PII masking, minimum cell size (NFR-002, AC-019). |
| RISK-006 | The exported package drifts from what actually ran. | Unreproducible results. | Modules copied byte for byte with hashes in the manifest; reproduction tests in the package (REQ-012, AC-014). |
| RISK-007 | Library-version changes alter numbers on reproduction. | False "not reproduced". | Pinned `requirements.lock`, declared tolerances, versions in metadata (REQ-013, REQ-015). |
| RISK-008 | A workflow agent runs commands other than the investigator's. | Uncontrolled code execution. | Reasoning agents get no data or shell task; one executor step runs a single command the script builds from schema-validated output; the command itself accepts only registered tools (REQ-005, REQ-016). |
| RISK-009 | Associations read as causes. | Bad decisions. | Causal-language rejection; findings worded as associations; positioning in Non-Goals. |

## Assumptions & Open Questions

- Assumption: one table per run; the dataset fits in memory after optional
  column selection (larger data is sampled with a recorded seed).
- Assumption: the language-model roles run as Claude Code workflow subagents
  (no API key in the runtime); the `adapters/llm_runtime/` path is a later,
  optional backend.
- Resolved (owner, 2026-10-07): the runtime's libraries live in a new optional
  `investigator` extra, not in core `quantsmith`.
- Resolved (owner, 2026-10-07): heavy libraries are acceptable — Pydantic models,
  PyYAML for YAML artifacts, Matplotlib for figures, scikit-learn for Isolation
  Forest and LOF.
- Resolved (owner, 2026-10-07): built inside this repository
  (`src/quantsmith/dataset_investigator/`), not as a separate repository.
- Open question: should `0081` domain packs supply column semantics (units,
  additivity) when a dataset's source carries domain tags?

## Exceptions

None.
