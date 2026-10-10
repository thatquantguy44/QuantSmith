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
- Change-safe data engineering (spec `0111`, slice A of `0107`): `streaming_cdc.py` (idempotent, order-safe CDC by
  per-key sequence; watermarked event-time windows with late data as side output or bitemporal restatement),
  `schema_evolution.py` (backward/forward change classification, mode enforcement, safe backward reads, drift detection
  before load), and `reprocessing.py` (lineage-exact restatement plans run under `0101` limits as new versions, diffs,
  all-or-nothing gated publication with rollback). New agents `data_engineering/streaming_cdc`, `schema_evolution`,
  `backfill_reprocessing`; a *Change-Safe Pipelines* section in `instructions/pipeline_engineering.md`.
- Skills export and registry (spec `0110`): `src/quantsmith/skills_export/` and the `quantsmith-skills` CLI generate
  a self-contained Claude skill for every agent under `.claude/skills/` (204 at generation 1) and keep a lifecycle
  registry (`.claude/skills/registry.json`: revision, introduced/updated/removed dates, generation, source and skill
  hashes, tombstones, per-target publication marks). `pending`/`mark-published` track what each target (e.g. Claude.ai)
  needs; `package` builds a plugin marketplace or per-skill zips. A `project` selection in
  `config/skills_export.json` keeps the in-repo project skills (53) within Claude Code's listing budget; all 204 stay
  registered and packaged. New `skills-export` gate, blocking in pre-commit and
  CI; `config/skills_export.json` for name overrides and exclusions; `instructions/skills_export.md`.
- Lineage and bitemporal provenance (spec `0102`): `src/quantsmith/pipelines/provenance.py` adds `LineageGraph`
  (content-hashed immutable dataset versions, source registration, validated transform runs with code version and
  column maps, `trace`, `impact`, `trace_column` with explicit gaps, `verify`, `cite`, OpenLineage-shaped events) and
  `BitemporalStore` (append-only valid-time × knowledge-time facts, no backdating, `as_of`, `snapshot`, `revisions`,
  retractions) plus `lookahead_violations`. New `agents/provenance/` group (`lineage_capture`, `bitemporal_data`) and a
  *Lineage And Bitemporal Records* section in `instructions/data_provenance.md`.
- Platform expansion roadmap recorded as the top priority in `docs/handoff.md` (What's Next #0); specs `0103`–`0109`
  reserved.
- Concurrent pipeline fleet (spec `0101`): `src/quantsmith/pipelines/pipeline_fleet.py` runs hundreds of pipelines
  under a global limit, slot-weighted pools, and mutual-exclusion keys with all-or-nothing admission, a starvation
  guard, bounded retries through admission, and `upstream_failed` isolation; `simulate` gives a deterministic capacity
  plan naming the bottleneck; `stagger_offsets` spreads schedules; `to_dagster`/`to_mage` render the limits as
  orchestrator config and list every lossy mapping. New agents `data_engineering/pipeline_concurrency` and
  `tooling/dag_orchestration` (Dagster and Mage profiles), the `adapters/schedulers/mage.md` adapter, and a
  *Concurrency At Fleet Scale* section in `instructions/pipeline_engineering.md`.
- Read-only natural-language analytics in the Knowledge Console (spec `0080` T-026): `POST /api/analytics/ask`
  answers a data question under the console viewer's clearance and returns headline, insights, `vega_lite`,
  `markdown_table`, plan echo, caveats, citations, and narrative. It never writes back, emits an envelope, or builds a
  knowledge candidate. Enable it with `knowledge_console serve --analytics-registry … --analytics-data …
  --analytics-today …` (optional `--llm-profiles`, `--viewer-override`); without it the route returns 404. A new
  *Data Questions* page renders the answer table (no chart library yet).
- Opt-in knowledge candidates for natural-language analytics (spec `0080` T-028): a publish request with
  `propose_knowledge` gets a `0049` `workflow_memory` candidate built from its headline insight, with evidence citing
  run, plan hash, record keys, metric definition, and as-of (`ChatResponse.knowledge_candidate`, or
  `knowledge_candidate_reason` when there is none). `answer()` never stages it; staging into `memory/inbox/` is the
  caller's step, and only a human's `promote` makes a record.
- Named approver for natural-language analytics write-back (spec `0080` T-027): every committed record carries
  `approver_handle`; an approved commit naming no approver records its author as approver. Write-back contracts may
  set `approver_roles` (checked against the new optional `roles` on `access/roster.yml` entries; refused while the
  roster is empty) and `require_distinct_approver`. Existing SQLite write-back tables gain the column on open.
- Model-backed interpretation and narration for natural-language analytics (spec `0080` T-025):
  `nl_analytics.interpret.LLMInterpreter` and `nl_analytics.narrate.LLMNarrator`, plugged in through
  `AnswerContext.interpreter` and `.narrator`. They take a plain `complete(prompt, system)` callable
  (`llm_runtime.as_callable()` builds one from a profile), so `nl_analytics` stays network-free. A malformed reply,
  an unknown field, an ungoverned plan, or a window past today becomes a clarification. A model narrative ships only
  if every number grounds and it has no causal wording; otherwise the template ships with a caveat. `ChatResponse`
  gains `narrative` and `narrative_mode`.
- Provider-neutral LLM backend (spec `0080` T-024): `quantsmith.adapters.llm_runtime` reads QuantMeridian's
  `llm-profiles/1` profile files unchanged (standard-library validator, cross-checked against the vendored schema) and
  resolves a profile per call with spec009's precedence and error codes. `complete()` sends single-turn completions
  to the Anthropic Messages API or any OpenAI-compatible endpoint (OpenAI, Azure OpenAI v1, gateways, vLLM, Ollama),
  with retries honoring `retry-after`, a one-hop fallback on provider errors, and a per-answer token cap. Credentials
  come only from environment variables and never appear in errors or `repr`. Shared conformance cases in
  `tests/fixtures/llm_profiles/conformance.json`. `jsonschema` joins the `dev` extra.
- First vendored agent-skills sync (spec `0100` T-006): `vendor/agent-skills/` (35 files, 366 KB) and
  `vendor/agent-skills.lock.json`, pinned at fork `thatquantguy44/agent-skills@f63ec56` (plugin `0.6.7`, version stamp
  `0.6.7+f63ec56.53469383`). Content reviewed before sync; `instructions/agent_skills.md` maps the vendored files'
  references to excluded items onto QuantSmith equivalents. Opt in once per machine with
  `quantsmith-agent-skills install --scope project`.
- agent-skills as a pinned, offline upstream (spec `0100`): `quantsmith.agent_skills` and the `quantsmith-agent-skills`
  command (`sync`, `diff`, `verify`, `status`, `install`) vendor an allowlisted subset of `addyosmani/agent-skills`
  (via the fork `thatquantguy44/agent-skills`) from a *local* clone, directory or `git archive` tarball only, with a
  per-file SHA-256 lock. Sync refuses URL sources, symlinks, executables and oversize files and prints a change summary
  before writing. Conflicting upstream items (`spec-driven-development`, `planning-and-task-breakdown`,
  `using-agent-skills`, `/spec`, `/plan`, `/build`, `/ship`, hooks) are excluded by `config/agent_skills.json`. Claude
  Code loads the subset as the namespaced plugin `agent-skills@quantsmith-local` from the local marketplace
  `.claude-plugin/marketplace.json` after a one-time per-machine opt-in (`install --scope project`); `.claude/settings.json`
  carries only the `enabledPlugins` kill switch. The wheel bundles the subset and config for `install --scope user`
  with no checkout. New gate `agent-skills` (enforced in CI) checks the tree against the lock, the allowlist,
  manifests and agent citations. New standard `instructions/agent_skills.md`; nine coding-stage agents cite the skills
  they use. The first vendored sync lands in its own PR.
- Dataset Investigator (spec `0099`): `quantsmith.dataset_investigator` and the `quantsmith-dataset-investigator` command
  investigate one CSV/TSV/Parquet/pandas/Polars dataset with 21 registered, versioned, deterministic tools (quality,
  distributions, relationships, segmentation, temporal, anomalies), rank findings with Benjamini–Hochberg-adjusted
  support, test hypotheses with declarative decision rules in a bounded loop, validate every claim (grounded numbers,
  no causal wording, re-execution, sample size), and write a fixed-order report plus an analysis package whose
  `dataset_analysis/` is the code that ran, with `reproduce` and `rerun` that need no language model. On demand as the
  saved Claude Code workflow `dataset-investigator` (`.claude/workflows/`) and the agent
  `agents/analytics/dataset_investigator/`. New optional `investigator` extra (pandas, scipy, scikit-learn, pyarrow,
  pydantic, PyYAML, Matplotlib).
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
- Specs `0101` (concurrent pipeline fleet), `0102` (lineage and bitemporal provenance), and `0110` (skills export
  and registry) approved by Joshua Lutkemuller, CFA (2026-10-10).
- `docs/packaging.md` updated — the Python-package phase is now active (real code
  exists); `docs/adoption_guide.md` rewritten to cover both the package and the
  scaffold.
- The `quantsmith` package now bundles the analytics domain pack catalog (spec `0081` REQ-013): `setup.py` copies
  `knowledge/analytics_packs/*.json` into `quantsmith/_bundled/analytics_packs/` at build time, and the build fails if
  there are none. `analytics_packs.resolve_packs()` uses an explicit root alone, else a local
  `knowledge/analytics_packs/` as a whole catalog, else the bundle, and returns a `PackSource` (kind, location, version,
  content hash). NL analytics (spec `0080` REQ-018) cites that source in every answer that applies a pack and in the
  envelope, raises when domain tags come with no catalog, and the CLI's `--domain` now works from a pip install;
  `--packs-root` is optional and errors only when it names an empty catalog.

### Fixed
- Natural-language analytics no longer discloses that a restricted metric exists (spec `0080` REQ-004): an
  access-masked plan used to return status `masked`, distinct from an unknown metric's `clarification_needed`; it now
  returns `clarification_needed` with the same reason, and `masked` is no longer a response status.
- Dataset Investigator (spec `0099`), from runs on real data (IBM Telco churn, UCI Occupancy): numbers stored as text
  (blanks among numbers) are numeric with a mixed-type quality finding; a target gap is stated high-to-low and its
  stratified (Mantel–Haenszel) test is judged on strength in the gap's own direction, so protective gaps are no
  longer rejected; the stratified test groups by the same bands the gap was measured on (it previously matched band
  labels against raw values and found no rows); findings over the same rows through another column (e.g. six
  "No internet service" add-ons) merge into one; more than 5% Mahalanobis-flagged rows is reported as likely
  regimes, not outliers; band edges start at the data minimum; tiny values keep three significant digits; and the
  planner names two-valued columns that could serve as `--target`.
- Dataset Investigator workflow: a live run broke when a step's 65 KB output was summarized by the executor agent
  instead of copied. Step output with `--context` is now compact JSON without the static tool catalog (new `catalog`
  command, fetched once), with floats to 6 significant digits, empty fields dropped, and the investigator shown its 20
  highest-ranked findings; the workflow also tolerates text an executor adds around the JSON.
- Dataset Investigator: a package from a run the model roles took part in failed its own `rerun` (the rerun was
  deterministic, the recorded outputs were not). The run now records the model's contributions — chosen analyses,
  proposals in order, review downgrades, narrative — in the state and manifest, and `rerun` replays them through the
  same validation with no model; the live Telco run reruns byte-identically. A stratified test whose groups never
  share a stratum now says so (`strata_with_both_groups`, `note`) instead of a bare "no value".
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
