# Adoption Guide

How to adopt QuantSmith in an existing quant repository. QuantSmith is now **two
layers**, and you can take either or both:

1. **A Python package** (`quantsmith`) — importable, tested reference runtimes:
   signal/forecast/portfolio/execution, optimization solvers, the metrics semantic
   layer, experimentation, the DAG runner + observability, and the dashboard
   renderers. `pip install` it and call it from your code.
2. **A scaffold of Markdown and shell** — agents, instructions, prompts, templates,
   the constitution, and the quality gates. Copy the surfaces you want and wire the
   gates into your hooks and CI.

See `docs/packaging.md` for the distribution model behind these two layers.

## What You Are Adopting

| Surface | Layer | What it gives you | Take it if… |
| --- | --- | --- | --- |
| `pip install quantsmith` | package | Tested reference runtimes you import | you want working code, not just checklists |
| `instructions/` | scaffold | The constitution and reusable standards | always — this is the backbone |
| `hooks/stages/` | scaffold | Portable quality gates | you want mechanical checks in hooks/CI |
| `agents/` | scaffold | Role definitions for research, review, and tooling | you use an agent runtime or want review checklists |
| `templates/` | scaffold | Spec, doc, data-contract, and pipeline-manifest templates | you want consistent artifacts |
| `prompts/` | scaffold | Task-ready prompts | you drive work with prompts |
| `specs/` | scaffold | The per-feature spec convention + worked examples | you adopt Spec-Driven Development |
| `CLAUDE.md` | scaffold | Activates the framework for agents in the repo | you use Claude Code or similar |

Adopt incrementally — the gates take named stages, and the package's extras are
optional, so you can start with one of either layer.

---

## Part 1 — The Python package

### 1. Install

```sh
# From a checkout (editable), with the extras you need:
pip install -e ".[dev,data,quant]"        # or: uv sync --frozen --all-extras (pinned by uv.lock)

# Or from Git (pin a tag/commit for reproducibility):
pip install "quantsmith @ git+https://github.com/joshualutkemuller/quantsmith@<tag>"
```

Extras: `quant` (scipy), `data` (pandas), `dev` (pytest, openpyxl). The core depends
only on numpy; every reference pipeline under `quantsmith.pipelines` is
standard-library-only, so most runtimes work with no extras at all.

### 2. Use the runtimes

Each runtime maps to a spec (see `specs/README.md`) and has tests under `tests/`.

```python
# Cross-sectional forecast -> portfolio -> execution (specs 0006/0007/0012)
from quantsmith.pipelines import (
    run_forecast, solve_portfolio, ConstraintSet, optimal_schedule,
)

# Optimization toolkit (spec 0013): LP / MILP / min-cost flow / dynamic programming
from quantsmith.pipelines import solve_lp, solve_milp, min_cost_flow, solve_dp

# Data Analyst (specs 0008/0009/0010): governed metrics, A/B tests, end-to-end
from quantsmith.pipelines import SemanticLayer, analyze_experiment, run_pipeline

# Data Engineer (specs 0011/0019): DAG runner + observability
from quantsmith.pipelines import Pipeline, Step, DataContract, run, observe

# Dashboards (specs 0014-0018): one governed DashboardSpec, seven render targets
from quantsmith.pipelines import DashboardSpec, Panel, render_powerbi, render_streamlit
from quantsmith.adapters.dashboard_render import scaffold_react, write_xlsx
```

These are **reference implementations** — dependency-free, deterministic, and tested.
Use them directly for small work, or swap the simple internals (e.g. the linear
baseline in `return_forecasting`, or `write_xlsx`'s openpyxl provider) for
production equivalents behind the same interfaces.

### 3. Run the tests

```sh
python -m pytest tests/ -q
```

The CI test job (`.github/workflows/ci.yml`) installs `.[dev,data,quant]` and runs
this suite on every push and PR.

---

## Part 2 — The scaffold

### 4. Copy the surfaces

From the SDK repo, copy the directories you want into your repo root. At minimum:

```sh
cp -R quantsmith/instructions   your-repo/
cp -R quantsmith/hooks          your-repo/
cp    quantsmith/CLAUDE.md       your-repo/    # optional but recommended
# add agents/, templates/, prompts/, specs/ as needed
```

(Or use the SDK repo as a GitHub template / `degit` source — see `docs/packaging.md`.)

### 5. Wire the gates into CI

The portable gates live in `hooks/stages/` and run via `run-stage.sh`. Add to your
CI (advisory first, then enforce what fits):

```sh
# Advisory — prints findings, never fails the build:
sh hooks/stages/run-stage.sh

# Enforce specific gates — fails the build on findings:
QF_STAGE_ENFORCE=1 sh hooks/stages/run-stage.sh spec spec-index secret-scan
```

The gates this repo enforces in CI, for reference:

| Gate | Fires when | What it checks |
| --- | --- | --- |
| `spec` | always | Spec-driven chain & traceability (no orphan tasks/ACs) |
| `spec-index` | always | Every `specs/NNNN` is listed in `specs/README.md` |
| `agent-catalog` | always | Every agent is listed in `agents/README.md` |
| `docs-link` | always | Relative Markdown links resolve |
| `secret-scan` | on diff | No secrets introduced |
| `backtest` | a backtest report exists | Cost, OOS, benchmark, turnover, financing |
| `pipeline-contract` | a pipeline manifest exists | Owner, schedule, retry/backfill, idempotency, runbook |
| `leakage` | on diff (advisory) | Point-in-time / look-ahead smells |

For diff-based gates (`leakage`, `secret-scan`) in a pull request, pass the base:

```sh
QF_DIFF_BASE="origin/${GITHUB_BASE_REF:-main}" sh hooks/stages/run-stage.sh leakage
```

A good starting CI policy: **enforce** `secret-scan`, `spec`, `spec-index`, and
`agent-catalog`; run everything else **advisory** until you have tuned the patterns.

### 6. Wire the gates into Git hooks (optional)

```sh
# in your .git hooks (or a pre-commit framework):
sh hooks/stages/run-stage.sh implementation secret-scan
```

The SDK's own `.githooks/` and `setup-hooks.sh` enforce *SDK-repo* invariants
(required docs, the agent contract). Adopt those only if you keep the SDK layout;
otherwise wire the `hooks/stages/` gates into your own hooks and skip `.githooks/`.

### 7. Configure

Behavior is controlled by environment variables (see `hooks/README.md`):

| Variable | Effect |
| --- | --- |
| `QF_STAGE_ENFORCE=1` | Make gate findings blocking. |
| `QF_RUN_TESTS=1` | Let the testing gate run your suite. |
| `QF_DIFF_BASE=<ref>` | Diff against a base branch for diff-based gates. |
| `QF_KNOWLEDGE_SOURCES` / `QF_KNOWLEDGE_BASE` | Point the knowledge gate at your knowledge locations. |

If you use the knowledge agents, copy `templates/knowledge/knowledge_sources.yml`
to your repo root as `knowledge_sources.yml` and set real paths.

### 8. Tune the gates to your repo

The gates are conventional, not prescriptive — they look for common artifact names
and doc sections. Adjust the patterns to your layout:

- `backtest-check.sh` / `data-contract-check.sh` / `pipeline-contract-check.sh` —
  file-name globs for your reports, contracts, and pipeline manifests.
- `secret-scan-check.sh` — add path globs to `.secretscanignore`, or append a
  `qf:allow-secret` marker to a line; install `gitleaks`/`detect-secrets` for a
  stronger scan.
- `repro-check.sh` — the lockfile and run-manifest names your repo uses.

### 9. Adopt Spec-Driven Development (recommended)

1. Read `instructions/engineering_principles.md` (the constitution) and
   `instructions/spec_driven_development.md` (the method).
2. For your next non-trivial change, create `specs/NNNN-slug/` from `templates/spec/`
   and assign IDs (`REQ`/`NFR`/`AC`/`RISK`/`T`).
3. Enforce the chain in CI: `QF_STAGE_ENFORCE=1 sh hooks/stages/run-stage.sh spec spec-index`.
4. Let the `workflow_orchestrator` agent (or a human) drive the flow through the gates.

Copy `specs/0001-daily-momentum-signal/` as a filled-in reference, and any of
`specs/0006`–`0019` as examples of a spec with a runnable, tested runtime.

---

## Recipes by project type

- **Notebook-heavy research repo.** Take `instructions/`, `CLAUDE.md`, the research
  and modeling agents, and enforce `secret-scan` + `leakage` (advisory). `pip install
  quantsmith` and use `momentum_signal`/`return_forecasting` as baselines.
- **Production quant/data repo.** Take everything. Enforce `spec`, `spec-index`,
  `secret-scan`, `pipeline-contract`, and the pytest job. Use the `data_pipeline`
  DAG runner + `pipeline_observability`, and the `metrics_semantic_layer`.
- **BI / analytics repo.** Take the `analytics/` and `tooling/` agents. `pip install
  quantsmith` and render one governed `DashboardSpec` to Power BI/Excel/React/
  Streamlit; scaffold live artifacts with `scaffold_react`/`write_xlsx`/
  `scaffold_streamlit`.

## Keep it updated

QuantSmith splits into two consumption classes (see `docs/packaging.md`):

- **Reference / stable** (the package, the constitution, agent prompts, templates) —
  pin a version and update deliberately. For the package, pin a Git tag or version;
  for the Markdown, re-copy the reference surfaces.
- **Owned / tuned** (`hooks/stages/*` patterns, CI wiring, your `specs/*`) — you own
  these; never let an update overwrite your local tuning.

Track releases in `CHANGELOG.md`.

## Minimal adoption (the 5-minute version)

```sh
# Package: get the runtimes.
pip install -e ".[quant]"

# Scaffold: get the constitution + a secret-scan gate.
cp -R quantsmith/instructions your-repo/
cp -R quantsmith/hooks        your-repo/
# add to CI:
#   QF_STAGE_ENFORCE=1 sh hooks/stages/run-stage.sh secret-scan spec-index
#   sh hooks/stages/run-stage.sh        # everything else, advisory
```

That gives you the runtimes, the constitution, the standards, and a secret-scan gate
on day one; grow from there.
