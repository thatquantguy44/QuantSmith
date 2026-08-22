# QuantSmith Hooks

This is the public hook surface of the SDK. It ships lightweight quality gates
aligned to the six development stages, each paired with the agent that owns that
stage.

Active local Git hooks live in `.githooks/` and are wired by `setup-hooks.sh`.
The scripts here are portable stage checks you can run manually, in CI, or wire
into Git hooks.

## Stage Hooks

Located in `hooks/stages/`, one per development stage plus a cross-cutting
spec-driven check that runs first:

| Stage | Script | Companion agent |
| --- | --- | --- |
| 0. Spec-driven chain (cross-cutting) | `spec-check.sh` | all — enforces `instructions/spec_driven_development.md` |
| 1. Planning / Requirements | `planning-check.sh` | `agents/planning_requirements/` |
| 2. Design | `design-check.sh` | `agents/design_architecture/` |
| 3. Coding / Implementation | `implementation-check.sh` | `agents/implementation/` |
| 4. Testing | `testing-check.sh` | `agents/testing_validation/` |
| 5. Deployment | `deployment-check.sh` | `agents/deployment_release/` |
| 6. Maintenance | `maintenance-check.sh` | `agents/maintenance_monitoring/` |

### Quant Gates (cross-cutting)

Quant-specific heuristic checks that run after the SDLC stages. Advisory and
pattern-based; tune them to your repository.

| Gate | Script | Companion |
| --- | --- | --- |
| Look-ahead & leakage | `leakage-check.sh` | `instructions/point_in_time.md`, `agents/feature_engineering/` |
| Backtest integrity | `backtest-check.sh` | `agents/backtest_review/` |
| Reproducibility | `repro-check.sh` | `templates/docs/run_card.md`, `agents/implementation/` |
| Data contract | `data-contract-check.sh` | `templates/data/data_contract.md`, `agents/data_quality/` |
| Pipeline contract | `pipeline-contract-check.sh` | `templates/data/pipeline_manifest.md`, `agents/data_engineering/` |
| Alert contract | `alert-contract-check.sh` | `templates/data/alert_policy.md`, `agents/alerts/` |
| Monitoring coverage | `monitoring-coverage-check.sh` | `templates/docs/model_monitoring_plan.md`, `agents/monitoring/` |
| Data provenance | `data-provenance-check.sh` | `templates/docs/synthetic_data_disclosure.md`, `instructions/data_provenance.md` |

### Repo Gates (security & docs integrity)

| Gate | Script | Companion |
| --- | --- | --- |
| Secret leak scan | `secret-scan-check.sh` | `agents/secrets_management/` |
| Markdown link check | `docs-link-check.sh` | all docs |
| Agent catalog sync | `agent-catalog-check.sh` | `agents/README.md` |
| Spec index sync | `spec-index-check.sh` | `specs/README.md` |
| README index/runtime sync | `readme-sync-check.sh` | `specs/README.md`, root `README.md` |
| Documented-count drift | `doc-counts-check.sh` | root `README.md`, `docs/handoff.md`, `docs/sdk_plan.md` |
| QuantSmith consumer pin | `quantsmith-version-check.sh` | a consuming repo's `requirements*.txt` / `pyproject.toml` (copy this gate there) |
| Commit authorship | `agent-attribution-check.sh` | commit author/committer identity and co-author trailers in a git range |
| Handoff roadmap sync | `handoff-sync-check.sh` | every spec is referenced in `docs/handoff.md`; a new spec arrives with its entry |
| Upstream surface drift | `upstream-drift-check.sh` | copied gates/standards vs the pinned upstream ref (consumer repos) |
| Ownership & support path | `ownership-check.sh` | CODEOWNERS, `docs/ownership.md`, and a gate runbook name real owners, not placeholders |
| Persistent knowledge guide sync | `persistent-knowledge-check.sh` | `PERSISTENT_KNOWLEDGE.md`'s status table vs. the real record/task/AC counts; co-change with `workflow_memory.py`/`memory/`/spec `0048` |
| Source catalog sync | `source-catalog-check.sh` | `sources/README.md`, `templates/data/source_catalog_entry.yml` |
| Knowledge source check | `knowledge-check.sh` | `agents/knowledge/` |
| Workflow memory check | `memory-check.sh` | `memory/`, `agents/knowledge/` |
| Access roster check | `access-check.sh` | `access/roster.yml`, `specs/0058-viewer-access-control/` |
| Role context check | `role-context-check.sh` | `templates/role_operations/role_context.yml`, `agents/role_operations/` |
| Model plugin registration check | `model-plugin-check.sh` | `templates/optimization/model_plugin_manifest.yml`, `adapters/model_plugin/`, `agents/optimization/model_plugin_registration/` |

Each script:

- checks for the artifacts and hygiene that stage cares about;
- **degrades gracefully** — missing tools or files produce a warning, not a crash;
- is **advisory by default** (prints findings, exits `0`) so it never blocks
  exploratory work.

## Usage

```sh
# Run every stage check:
hooks/stages/run-stage.sh

# Run one or several stages:
hooks/stages/run-stage.sh testing
hooks/stages/run-stage.sh planning design

# Run only the spec-driven traceability check:
hooks/stages/run-stage.sh spec

# Run only the quant/content gates:
```

## Quant Gates

- **`leakage-check.sh`** scans changed Python/notebook files for high-signal
  look-ahead and leakage smells (negative `shift`, `bfill`, unshuffled
  `train_test_split`, whole-sample scaler fit) per `instructions/point_in_time.md`.
  Heuristic — it points a reviewer at lines, it does not prove leakage.
- **`backtest-check.sh`** verifies a backtest report artifact addresses transaction
  costs, out-of-sample, benchmark, turnover/capacity, and multiple-testing.
- **`repro-check.sh`** checks for a run manifest (`run_card`), a dependency
  lockfile, and seeded randomness in changed code.
- **`data-contract-check.sh`** verifies a data contract declares schema, keys,
  point-in-time rules, and missingness rules.
  pack, including config, draft-pack template, sample fixture, content agent
  contracts, scheduler profile, runtime smoke test, manual approval flag, and
  no-autopost boundary.
- **`data-provenance-check.sh`** verifies a synthetic-data disclosure artifact
  declares its required fields (location, reason, generation method,
  reviewer), and advisorially flags report/dashboard-shaped artifacts that
  mention synthetic data with no matching disclosure anywhere in the tree.
  See `instructions/data_provenance.md`.

## Repo Gates

- **`secret-scan-check.sh`** detects committed secrets. Uses `gitleaks` or
  `detect-secrets` when installed; otherwise a high-signal regex fallback over
  changed code/config files (docs and SDK scaffolding are skipped). Allowlist a
  file via `.secretscanignore`, or a line with a trailing `qf:allow-secret`
  marker. Enforced in CI.
- **`docs-link-check.sh`** verifies relative Markdown links and image paths
  resolve to existing files. External links and pure anchors are skipped.
- **`agent-catalog-check.sh`** verifies every public agent (a directory with
  `prompt.md`) is listed in `agents/README.md`.
- **`spec-index-check.sh`** verifies every tracked spec (a directory under `specs/`
  with `spec.md`) is listed in the spec index, `specs/README.md`. Enforced in CI.
- **`knowledge-check.sh`** validates the configurable knowledge-base source
  locations for `agents/knowledge/`: it resolves a manifest
  (`$QF_KNOWLEDGE_SOURCES`, then `knowledge_sources.yml`, then the ad-hoc
  `$QF_KNOWLEDGE_BASE` colon-separated paths), verifies each path exists and is
  readable, and reports its subfolder domains and file counts. See
  `templates/knowledge/knowledge_sources.yml`.
- **`memory-check.sh`** validates the persistent workflow memory store (`memory/`):
  that records carry provenance (`first_seen`, `last_confirmed`, `access_level`) and
  that memory holds no secrets, connection strings, or PII (memory is metadata only).
  See `instructions/workflow_memory.md` and `specs/0002-workflow-memory/`.
- **`access-check.sh`** validates the per-person viewer access roster
  (`access/roster.yml`): parses it, flags duplicate handles, unrecognized
  clearance levels, and email/free-text-shaped handles, and runs the same
  secret/PII safety scan `memory-check.sh` applies to `memory/`, applied to
  `access/`. See `specs/0058-viewer-access-control/` and `access/README.md`.
- **`role-context-check.sh`** guards the configurable context for
  `agents/role_operations/`: it deterministically flags a `role_context.yml`
  that is tracked or staged (blocking under `QF_STAGE_ENFORCE=1`), reports the
  shape of whatever context is resolved (`$QF_ROLE_CONTEXT`, then
  `./role_context.yml`), and advisorially checks the shipped template for
  placeholder hygiene. See `templates/role_operations/role_context.yml` and
  `instructions/role_operations.md`.
- **`model-plugin-check.sh`** guards the registration manifest for
  `adapters/model_plugin/`: it deterministically flags a `model_plugins.yml`
  that is tracked or staged (blocking under `QF_STAGE_ENFORCE=1`), resolves
  whatever manifest is configured (`$QF_MODEL_PLUGINS`, then
  `./model_plugins.yml`), and checks each registered entry declares the
  required contract fields (owner, category, objective, invocation type,
  review status). See `templates/optimization/model_plugin_manifest.yml` and
  `instructions/model_plugin_integration.md`.
- **`source-catalog-check.sh`** validates the data source catalog
  (`sources/`): every `sources/*.yml` declares the required fields (source
  id, name, type, owner, description, access level, quality block,
  connection block, credential reference, status), every file is listed in
  the index (`sources/README.md`), and `credential_ref` doesn't contain a
  token-shaped secret value (reuses `secret-scan`'s patterns). Unlike
  `role-context`/`model-plugin`, `sources/*.yml` is meant to be tracked —
  this gate protects the credential field, not the file's git status. See
  `templates/data/source_catalog_entry.yml` and
  `instructions/data_source_catalog.md`.

## Spec-Driven Check

`spec-check.sh` validates the Spec-Driven Development chain across every
`specs/<id>/` directory (see `instructions/spec_driven_development.md`):

- `spec.md`, `plan.md`, `tasks.md` are present (no plan/tasks without a spec).
- `spec.md` declares requirements (`REQ-*`/`NFR-*`) and acceptance criteria (`AC-*`).
- Every requirement is covered in `plan.md` or `tasks.md`.
- Every acceptance criterion is referenced in `tasks.md` (test coverage map).
- No orphan tasks — every `T-*` cites a requirement.

Run it in enforce mode to block merges that break traceability:

```sh
QF_STAGE_ENFORCE=1 hooks/stages/run-stage.sh spec
```

## Configuration

Behavior is controlled by environment variables:

| Variable | Effect |
| --- | --- |
| `QF_STAGE_ENFORCE=1` | Make findings blocking (non-zero exit). Use in CI or as a strict gate. |
| `QF_RUN_TESTS=1` | Let the testing stage actually run the suite (`pytest`) when present. |
| `QF_DIFF_BASE=<ref>` | Diff changed files against `<ref>` (e.g. `origin/main`) instead of the working tree. |
| `QF_KNOWLEDGE_SOURCES=<path>` | Path to a knowledge-source manifest for the `knowledge` gate. |
| `QF_KNOWLEDGE_BASE=<paths>` | Colon-separated knowledge-base locations for the `knowledge` gate (ad-hoc, no manifest). |
| `QF_ROLE_CONTEXT=<path>` | Path to a filled-in role-context file for the `role-context` gate and `agents/role_operations/` (local only; never commit it). |
| `QF_MODEL_PLUGINS=<path>` | Path to a filled-in model-plugin manifest for the `model-plugin` gate and `adapters/model_plugin/` (local only; never commit it). |

## Wiring Into Git

To run a subset of stage checks on commit, add a call from `.githooks/pre-commit`:

```sh
# In .githooks/pre-commit
sh hooks/stages/run-stage.sh implementation testing
```

To gate a push against the release-oriented stages:

```sh
# In .githooks/pre-push
QF_STAGE_ENFORCE=1 sh hooks/stages/run-stage.sh deployment
```

## Wiring Into CI

Run the full set in enforce mode against the pull request base:

```sh
QF_STAGE_ENFORCE=1 QF_DIFF_BASE=origin/main sh hooks/stages/run-stage.sh
```

## Design Notes

- Hooks are guardrails, not traps. Advisory mode keeps research fast; enforce
  mode is opt-in for the paths that must not regress.
- Checks are conventional, not prescriptive: they look for common artifact names
  and doc sections. Adjust the patterns to your repository's layout.
- Every stage hook points back to its companion agent so a finding has an owner.
