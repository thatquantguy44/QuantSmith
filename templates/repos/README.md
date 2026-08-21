# Repository shapes

Pre-canned repository skeletons. Pick a shape, scaffold it, and get a repo that
already has its directories, its docs, its git hooks, its CI, and — the part
that matters — a `quantsmith.conf` that already declares which gates block and
why. The adopter configures nothing.

```sh
./templates/repos/scaffold-repo.sh --list
./templates/repos/scaffold-repo.sh --shape quant-research --into ../my-repo
```

## Shapes

| Shape | For | Blocks on |
| --- | --- | --- |
| `quant-research` | Signal research, many cheap experiments | `secret-scan` `docs-link` `handoff-sync` |
| `quant-models` | Models that size real positions | + `spec` `backtest` `leakage` `agent-attribution` |
| `data-pipelines` | Ingestion, transforms, contracts | + `data-contract` `pipeline-contract` |

The differences between those rows are the whole point. A research repo that
demands a spec per experiment stops people experimenting; a models repo that
lets a look-ahead bug through ships a bad trade. Each shape's `README.md`
argues for its own gate selection rather than leaving it as a list.

## What every shape gets

```text
.agents/        repo-local agent contracts (four-file, gate-enforced)
.copilot/       ambient assistant instructions
.githooks/      pre-commit, commit-msg, pre-push
.github/        CI, PR/issue templates, CODEOWNERS, dependabot
config/         declared constraints and thresholds
docs/           roadmap · conformance · working_agreement · architecture · decisions/
hooks/stages/   the quality gates
instructions/   the constitution and the SDD method
memory/         workflow memory store
scripts/        setup-hooks · check · new-spec
specs/          the spec chain
src/ tests/     code and tests
templates/      spec and document templates
CLAUDE.md  CONTRIBUTING.md  CHANGELOG.md  pyproject.toml  quantsmith.conf
```

`docs/working_agreement.md` is the one to read first — it is the loop, not the
setup: what you do when work arrives, and when a change needs a spec.

## Inbound triggers

Every shape's `ci.yml` is inbound-only: no `repository_dispatch`, so no other
repository can start a workflow. The single exception ships commented and
optional — `on-upstream-release.yml`, which receives an upstream's release
event and opens a **PR** bumping the pin. It never merges. Automatic
notification, never automatic bumps.

## Adding a shape

Copy an existing one, edit `quantsmith.conf`, write a `README.md` that argues
for the gate selection, and add the overlay directories. Keep the count small:
every shape is a thing that can rot, and two well-maintained shapes beat five
stale ones.
