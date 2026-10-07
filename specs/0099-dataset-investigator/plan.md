# Plan: Dataset Investigator

- **Spec:** 0099-dataset-investigator (`spec.md`)
- **Status:** Draft (built)
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-07

> HOW. Every requirement in the spec appears in the traceability matrix below.

## Approach

Two layers with a hard boundary between them:

1. **A deterministic runtime**, `src/quantsmith/dataset_investigator/`, that does
   all loading, measuring, ranking, hypothesis testing, validation, reporting,
   and export. It runs end to end on its own (`analyze`), with rule-based
   planning and templated hypotheses and report text. This is the path tests,
   CI, reruns, and reproduction use (REQ-014).
2. **Language-model roles** layered on top through a saved Claude Code workflow,
   `.claude/workflows/dataset-investigator.js`. Each role only reads structured
   evidence and returns schema-validated JSON; the runtime re-validates
   everything the roles return before anything executes or is published.

A workflow script has no filesystem or process access; only subagents can run
commands. So the workflow separates **reasoning agents** (planner,
investigator, validator review, writer — given evidence JSON in the prompt,
returning structured output, never asked to run anything) from a single
**executor** role per step, which runs exactly one command the script built from
already-validated JSON. The command is the enforcement boundary: it executes
only registered tools with schema-valid parameters (RISK-008).

## Architecture & Components

```
dataset ─▶ loading.load + fingerprint ─▶ roles.infer ─▶ planner.plan ────────┐
                                                                              ▼
          registry (TOOL_REGISTRY, @analysis_tool) ◀── executor.run(plan) ── executions[]
                                                                              ▼
                       findings.derive ─▶ findings.rank (I, BH) ─▶ hypotheses.loop (rounds ≤ cap)
                                                                              ▼
                                       validator.validate ─▶ report.write + export.build_package
```

| Component | Responsibility |
| --- | --- |
| `analysis/` | The whole deterministic core, **self-contained**: its modules import only the standard library, the `investigator` extra's libraries, and each other relatively. Export copies this directory byte for byte as the package's `dataset_analysis/`, so the exported code is exactly what ran (REQ-012). |
| `analysis/models.py` | Pydantic models: column profile, dataset info, tool execution, finding, hypothesis, question, validation, config, `InvestigationState`. |
| `analysis/loading.py` | Load CSV, Parquet, pandas, Polars (`to_pandas`, optional); SHA-256 file fingerprint and a content hash; read-only (REQ-001). |
| `analysis/roles.py` | Column roles with evidence; overrides; PII flags (REQ-002). |
| `analysis/registry.py` | `@analysis_tool(name, category, version, params=PydanticModel)`; `TOOL_REGISTRY`; parameter validation; content-addressed `ToolExecution` (REQ-004, REQ-005). |
| `analysis/profile.py`, `quality.py`, `distributions.py`, `relationships.py`, `segmentation.py`, `anomalies.py`, `temporal.py` | The registered tools (REQ-004, REQ-006). Results hold aggregates only; groups below the minimum cell size are pooled. |
| `analysis/planner.py` | Deterministic rule planner with reasons; `validate_plan()` for a model-proposed plan (REQ-003, REQ-017). |
| `analysis/findings.py` | Rules turning results into candidate findings; I-score components; BH adjustment; top-N (REQ-007). |
| `analysis/hypotheses.py` | Hypotheses with declarative decision rules, templates per finding kind, the bounded loop, follow-ups, research questions (REQ-008, REQ-009). |
| `analysis/validator.py` | The REQ-010 checks, including number grounding and causal-phrase rejection (same approach as `0080`'s grounding, reimplemented so the package stays self-contained). |
| `analysis/report.py`, `metadata.py` | Fixed-order Markdown, `findings.json`, `hypotheses.json`, Matplotlib figures from recorded aggregates; `run_metadata.yaml` via PyYAML (REQ-011, REQ-015). |
| `analysis/pipeline.py`, `cli.py` | `investigate()` (the whole deterministic run), `reproduce()`, `rerun()`; the package's `dataset-investigator` command (REQ-013, REQ-014). |
| `context.py` | Language-model context: profile, roles, evidence only; PII masked (REQ-017, NFR-002). Runtime only. |
| `export.py` | Builds `analysis_package/` around a copy of `analysis/`: manifest with module hashes, generated tests, `requirements.lock`, README, config, example, expected outputs (REQ-012). Runtime only. |
| `cli.py` | `quantsmith-dataset-investigator` (REQ-016): the full run plus the step commands the workflow drives. |
| `.claude/workflows/dataset-investigator.js` | On-demand workflow (REQ-016). |
| `agents/analytics/dataset_investigator/` | Agent contract (`prompt.md`, `README.md`, `instructions.md`, `tasks.md`) including the four role briefs. |

## Interfaces & Data Contracts

**State** (Pydantic models, JSON round-trip): `InvestigationState(dataset,
profile, column_roles, plan, executions, findings, hypotheses, questions,
validations, config)`.

**Tool** — `@analysis_tool(name="compare_target_rates", category="segmentation",
version="1.0.0", params={...})`; signature `fn(df, **params) -> dict`. Results
are JSON-safe (floats, ints, strings, lists, dicts; NaN encoded as null).

**Execution** — `{execution_id, tool, version, module, params, input_fingerprint,
result_sha256, duration_s}`; `execution_id` is a hash of tool, version, params,
and input fingerprint, so identical calls share an id (NFR-001).

**Finding** — `{finding_id, claim, kind, evidence, method, module, function,
params, execution_id, score: {I, M, S, P, A, weights}, p_value, p_adjusted,
n, confidence, status}`. IDs are assigned by rank order after validation, so
reruns assign the same ids.

**Hypothesis** — `{hypothesis_id, from_findings, statement, test: {tool,
params}, prediction, decision_rule, result_execution_id, status, follow_ups}`.

**Manifest** (`analysis_package/manifest.json`) — per finding: module, function,
params, execution id, expected evidence, tolerance; per module: SHA-256.

**Commands**

| Command | Purpose |
| --- | --- |
| `quantsmith-dataset-investigator analyze DATA [--target COL] [--timestamp COL] [--roles JSON] [--pii COL…] [--config FILE] [--out DIR] [--seed N]` | Full deterministic run → bundle. |
| `… profile DATA` / `… plan STATE` | Profile + roles; deterministic plan (workflow steps). |
| `… run-tool STATE TOOL --params JSON` | Execute one registered tool and append the execution and evidence (workflow executor). |
| `… validate STATE` / `… report STATE [--narrative FILE]` / `… export STATE` | Validator, report (optional model-written narrative, grounded first), package. |
| `dataset-investigator analyze DATA` / `reproduce FID --data DATA` / `rerun --data DATA` | In the exported package. Exit 0 reproduced, 3 evidence mismatch, 4 wrong dataset, 2 usage error. |

**Workflow** — `Workflow({name: "dataset-investigator", args: {dataset, target?,
timestamp?, pii?, out?, seed?, max_rounds?}})`. Phases: Profile → Plan →
Analyze → Investigate (loop) → Validate → Report → Export. Reasoning agents get
evidence JSON and return schema output; the executor agent is told to run only
the given `quantsmith-dataset-investigator` command and return its stdout. No
timestamps or randomness in the script (resume-safe); the run id comes from
`args` or the command.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P4 Correct by construction | yes | Numbers only from registered tools; roles gate eligible columns; BH adjustment; grounding rejects unbacked numbers. |
| P5 Reversibility | yes | Read-only on the source; every run is a self-contained directory that can be deleted. |
| P6 Observability | yes | Every execution recorded with params and hashes; metadata and manifest per run; optional `0070` envelope. |
| P9 Security & data | yes | Aggregates-only model context, PII masking, minimum cell size, no network, no generated-code execution. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `analysis/loading.py` | T-001 |
| REQ-002 | `analysis/roles.py` | T-002 |
| REQ-003 | `planner.py` | T-003 |
| REQ-004 | analysis tools, registry results | T-004, T-005 |
| REQ-005 | `registry.py` | T-004 |
| REQ-006 | analysis tools across six families | T-005, T-006 |
| REQ-007 | `findings.py` | T-007 |
| REQ-008 | `hypotheses.py` loop | T-008 |
| REQ-009 | `hypotheses.py` questions | T-008 |
| REQ-010 | `validator.py` | T-009 |
| REQ-011 | `report.py` | T-010 |
| REQ-012 | `export.py` | T-011 |
| REQ-013 | exported `reproduce` | T-011 |
| REQ-014 | deterministic path; exported `rerun` | T-011, T-012 |
| REQ-015 | `metadata.py` | T-010 |
| REQ-016 | `cli.py`, workflow, agent contract | T-012, T-013, T-014 |
| REQ-017 | `context.py`, `planner.validate_plan`, validator grounding | T-003, T-009, T-013 |
| NFR-001 | content-addressed execution ids; deterministic ordering; excluded-field list | T-004, T-011 |
| NFR-002 | `context.py`, output-directory confinement | T-009, T-015 |
| NFR-003 | sampling thresholds, loop caps, benchmark | T-003, T-008, T-015 |
| NFR-004 | guarded optional imports; `investigator` extra | T-001, T-006, T-015 |
| NFR-005 | source scan; no `eval`/`exec` | T-015 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Location | `src/quantsmith/dataset_investigator/` in this repo | Separate `dataset-investigator` repository | Reuses `0080` grounding, `0070` envelopes, packaging, CI, and gates. The exported package is the standalone artifact. |
| Model role | Claude Code workflow subagents | Runtime calls an LLM API directly | No credentials in the runtime; the deterministic path stays model-free; the API backend can come later through `adapters/llm_runtime/`. |
| Exported code | Byte-identical copies of the executed modules | Generated or templated code | The spec's core promise; hashes make drift detectable. |
| Data models | Pydantic | stdlib dataclasses | Owner allowed heavy libraries; Pydantic gives validated, JSON-schema-described tool parameters that model roles can be shown and held to. |
| Figures | Matplotlib PNG from recorded aggregates | Vega-Lite JSON | Readable in any Markdown viewer; drawn from results, never from raw rows. |
| Dependencies | One optional `investigator` extra | Core dependencies | The rest of `quantsmith` stays light; CI installs all extras. |
| Many tests | BH adjustment across the run | Unadjusted p-values | Investigation runs dozens of tests; unadjusted support inflates findings. |

## Validation Strategy

`tests/test_dataset_investigator.py` names each `AC-*`. Synthetic fixtures with
planted structure (fraud rate ratio, overnight denominator effect, a dated
drift, multivariate outliers, quality defects) prove each tool and rule against
hand-computed answers. The export test builds a package in a temporary
directory and runs its own tests and `reproduce` in a subprocess. The workflow
test parses the script's `meta` and statically checks its prompts. The
benchmark is skipped with a recorded reason on an under-provisioned runner.

## Rollout, Observability & Rollback

Ships as `Draft`, deterministic path first (T-001–T-012), then the workflow and
agent contract (T-013–T-014). Each run is a self-contained directory, so
rollback is deleting it; the runtime never touches the source.

## Open Questions

- ~~Optional extra and heavy libraries~~ — resolved 2026-10-07 (spec Assumptions).
- Whether `0081` domain packs should supply column semantics.
