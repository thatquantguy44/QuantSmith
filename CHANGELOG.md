# Changelog

All notable changes to QuantSmith are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

QuantSmith is two layers (see `docs/packaging.md`): a versioned Python package
(`quantsmith`) and a copyable Markdown/shell scaffold. This changelog covers both.

## Versioning policy

- **MAJOR** — a breaking change to a public runtime interface (`quantsmith.pipelines`
  / `quantsmith.adapters`), the agent contract, or an enforced gate's contract.
- **MINOR** — a new spec/runtime, agent, gate, or template; backward-compatible
  additions.
- **PATCH** — fixes and doc/heuristic tuning with no interface change.

Adopters pin a version or Git tag; the scaffold is copied-and-owned, so tune gate
patterns locally rather than expecting them to update in place.

## [Unreleased]

### Added
- Reference runtimes with tests for specs `0001`, `0006`–`0019`
  (`src/quantsmith/pipelines/`, `src/quantsmith/adapters/`): momentum signal,
  return forecasting, portfolio construction, execution scheduling, the optimization
  solver toolkit (LP/MILP/flow/DP), the metrics semantic layer, experimentation, the
  end-to-end analytics pipeline, the DAG runner, pipeline observability, and the
  dashboard renderers (Power BI, Excel, React, Streamlit, Looker, Superset, Qlik)
  with executable `scaffold_react` / `write_xlsx` / `scaffold_streamlit` providers.
- Data Engineer agent group (`agents/data_engineering/`) and Data Analyst
  communication layer (`agents/analytics/`), plus BI-tool and React/Streamlit
  `agents/tooling/` agents.
- Quality gates `spec-index` and `pipeline-contract`, and the standards
  `instructions/metrics_semantic_layer.md`, `instructions/data_storytelling.md`,
  `instructions/pipeline_engineering.md`.
- A CI job that installs the package (`.[dev,data,quant]`) and runs `tests/`.
- Trackers: `specs/README.md` (spec index) and
  `src/quantsmith/pipelines/README.md` (runtime catalog).

### Changed
- `docs/packaging.md` updated — the Python-package phase is now active (real code
  exists); `docs/adoption_guide.md` rewritten to cover both the package and the
  scaffold.

### Fixed
- Repaired the dead `agentic_code_tools/powerbi.py` (missing `PowerBIPayload`
  contract) so the Power BI runtime imports.

## [0.1.0] — 2026-07

### Added
- Initial QuantSmith SDK: the spec-driven engineering framework (constitution, SDD
  method, per-feature specs), the agent catalog and four-file contract, the
  `hooks/stages/` quality gates, instruction standards, prompt/template libraries,
  persistent workflow memory, and the `quantsmith` package skeleton (`pyproject.toml`).
