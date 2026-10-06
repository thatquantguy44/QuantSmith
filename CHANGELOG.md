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
- Model testing helpers (spec `0098`): `quantsmith.test_engineering` gains seeded generators (including convex LP/QP instances whose optimum
  is known by construction), metamorphic relations, a differential runner, KKT optimality certificates with a solver instance runner,
  regression and ML checks (determinism, label-shuffled placebo, noise features, baseline), and `metamorphic` and `differential`
  subcommands. numpy only; SciPy is used as a test oracle. Run on `solve_lp` and `solve_portfolio` it found no defect.
- Test engineering runtime (spec `0097`): `quantsmith.test_engineering` and the `quantsmith-test-engineering`
  command (`detect`, `run`, `edges`, `cpp`, `mutate`, `flaky`) for Python and C++. Zero tests never reads as a pass;
  C++ cases run one per process under AddressSanitizer and UndefinedBehaviorSanitizer; mutation testing reports
  uncovered mutants apart from survivors; flakiness checks name the seed that reproduces an order dependence.
  `coverage` is added to the `dev` extra. Items 7–9 are scoped in the spec plan.
- Venture request routing (spec `0096`): `venture_routing.py` and reviewable rules in `routing.json` turn a
  request into an ordered agent chain with review gates, decision owner, the strictest decision-path class, and
  the clearance it needs; forbidden requests (recommend an investment, designate or attribute, profile a person,
  non-public collection, release without review, set a mark, classify export control, forecast returns) are refused
  with the human who owns the decision; ambiguous requests ask. New `venture_orchestrator` agent.
- Venture predictive-model reference baselines (spec `0095`): `quantsmith.venture_models` with a
  point-in-time validation harness (`as_of_view`, `out_of_time_split`, `assert_features_known`), a
  computed `deployability` gate, competing-risks survival (Kaplan-Meier, Aalen-Johansen, discrete-time
  hazards with calibration and concordance), an emergence indicator with a Poisson noise floor,
  organization-level link prediction, a seasonal anomaly indicator, and a chain-ladder nowcast on
  real-time vintages. All validation is synthetic; the model catalog marks every model not usable for
  decisions and the pack validator enforces it.
- Venture knowledge integration (spec `0092`): the gitignored `knowledge_local/<domain>/` private
  store (templates in `templates/knowledge_local/`; `docs-link` skips it and `memory` scans it),
  `venture_knowledge.py` (store validation, memory candidates staged only inside the store, a
  clearance-first retrieval reference with a contract checker for the future `0054` server),
  `venture_products.py` (brief and memo validation, release gate, deterministic rendering), and the
  `intelligence_brief_writer` and `investment_memo_writer` agents. Fixed: `None` was read as a name in
  the pack's review sign-off, the orphan-requirement check, and the product checks.
- Venture fund and portfolio analytics (spec `0091`): `venture_fund_analytics.py` (multiples as of a
  date, XIRR that reports every root, J-curve profile and series, Kaplan-Schoar PME, vintage-matched
  peer percentile, mark-consistency flags, seeded fund-outcome, bootstrap, and reserve-policy
  simulation), three contract agents (`fund_performance_analyst`, `valuation_marks_reviewer`,
  `portfolio_reserve_analyst`), and the new XIRR, peer-percentile, and mark-flag conventions.
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
- NL analytics insights (spec `0080`, T-021/T-022) no longer sum per-group values for every metric: yields across tenors,
  VaR across desks, and ratios were summed into a single "level", and percent changes were reported for rates.
  Levels now use the semantic layer's own ungrouped value. A non-additive metric asked by a dimension reports
  each group with no total. Contributor and concentration insights need groups that add up to the total. Stocks
  and rates are read at the latest period, and `pct`/`bps` changes are reported in basis points. Analytics domain
  packs (`0081`) now apply through `nl_analytics/domain.py` (vocabulary, units, additivity, suppressed insights,
  caveats, term-conflict clarification, and a write-back refusal while any applied pack is unreviewed), with a
  stated generic fallback; the CLI gains `--domain`, which exits with an error when no packs are found under
  `--packs-root` (the packs ship with the repository, not the pip package).
- The `maintenance` gate no longer treats test files as model code. Its `*model*.py` pattern matched `tests/test_model_*.py` and warned that model code
  changed with no model card; files under `tests/` and `test_*.py` are now skipped, and real model or pipeline code still needs a card or runbook.
- Mutation testing (`0097`) now runs the tests against the mutated copy. With a `src`-layout package that was also installed (an editable
  install), the tests imported the original, every mutant survived, and the tool reported a score of 0 with no warning. The copy's `src/` and
  root now come first on `PYTHONPATH`, the tool verifies where the target module resolves from, and it refuses to score
  (`mutated_file_not_imported`, exit `2`) when it is provably outside the copy.
- The C++ boundary probe (`0097`) now uses the first installed compiler that can build and run a sanitizer program. An installed `clang++`
  without the sanitizer runtime used to hide a working `g++` and report `built: false`; the result now lists each compiler tried and why it
  failed. The CTest path is also tested against a real CMake project.
- Repaired the dead `agentic_code_tools/powerbi.py` (missing `PowerBIPayload`
  contract) so the Power BI runtime imports.

## [0.1.0] — 2026-07

### Added
- Initial QuantSmith SDK: the spec-driven engineering framework (constitution, SDD
  method, per-feature specs), the agent catalog and four-file contract, the
  `hooks/stages/` quality gates, instruction standards, prompt/template libraries,
  persistent workflow memory, and the `quantsmith` package skeleton (`pyproject.toml`).
