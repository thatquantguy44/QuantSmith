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
- `agents/agent_registry.yaml` is now generated from the agents (all 200, was 6) by
  `scripts/build_agent_registry.py`: category, purpose, inputs, outputs, skill path, and
  decision-path class per agent. The six original entries keep their machine identifiers
  under `interface`; their `skills_path` values pointed at a nonexistent `skills_library/`
  and are replaced by real `skill_path`s (eight agents have a `SKILL.md`). A pytest
  (`tests/test_agent_registry.py`) and the `agent-catalog` gate fail when the registry is stale.
- `uv.lock` pins the full dependency set (all extras, Python 3.10+); CI now runs
  `uv lock --check` and installs with `uv sync --frozen --all-extras`. Refresh steps
  are in `docs/gate_runbook.md`.
- Venture & non-traditional intelligence (specs `0083`–`0090`, `0094`): the
  `knowledge/venture_intelligence/` pack (taxonomy, conventions, channels, models,
  workflows, coverage, gaps, glossary, golden cases, per-record review sign-off),
  `instructions/venture_intelligence.md`, 21 contract-only agents under
  `agents/venture_intelligence/` (multilingual document NLP, entity resolution,
  Southeast Asia, Greater China & East Asia, South Asia, and Central Asia regional
  agents, signal and sourcing agents, tradecraft and screening-support agents),
  eleven public source entries with `known_at` policies, and the stdlib helpers
  `venture_pack.py`, `venture_ingestion.py`, `venture_tradecraft.py` with tests.
  `quantsmith.asian_nlp` (spec `0094`): dependency-free language/script identification,
  segmentation baseline, rule-based amount/currency/date/era-year/fiscal-period extraction
  with verbatim spans for 12 languages, per-language evaluation, and baseline-vs-model
  comparison, with 240 synthetic fixture cases and 220 tests.
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
- Spec `0080` (Draft): natural-language analytics — governed question-to-chart
  workflow with grounded interpretation and approved SQLite write-back, an
  opt-in `0070` audit envelope, a `quantsmith-nl-analytics` CLI, and a
  worked example (`examples/nl_analytics/`) with a disclosed synthetic
  three-day transcript.
- Spec `0081`: 40 analytics domain packs across seven financial-services
  families (`knowledge/analytics_packs/`), the `analytics_packs.py` validator
  and selector, and `tests/test_analytics_packs.py`. All packs ship `draft`.
- Spec `0082`: six `agents/enterprise_risk/` agents (operational, model risk
  management, counterparty credit/XVA, AML/financial crime, liquidity and
  treasury risk, climate/ESG risk) and `instructions/enterprise_risk.md`,
  fixing a gap `0081` found — 27 of its 40 packs fell back to the generic
  `agents/risk`, whose charter is investment/portfolio risk, not these six
  disciplines. Re-points the 7 mismatched packs; `agents/risk` and the other
  20 packs are unchanged.

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
