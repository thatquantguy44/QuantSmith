#!/bin/sh
# Run one or all QuantSmith stage checks.
#
# Usage:
#   hooks/stages/run-stage.sh                 # run all stages
#   hooks/stages/run-stage.sh testing         # run one stage
#   hooks/stages/run-stage.sh planning design # run several
#
# Stages: spec planning design implementation testing deployment maintenance
#   (spec is the cross-cutting spec-driven traceability check; it runs first)
# Quant gates: leakage backtest repro data-contract pipeline-contract
#   alert-contract monitoring-coverage
#   (quant-specific checks; heuristic and advisory, run after the SDLC stages)
# Repo gates: secret-scan docs-link agent-catalog spec-index readme-sync doc-counts
#   quantsmith-version agent-attribution
#   (security, documentation-integrity, consumer-pin, and authorship checks)
# Knowledge gate: knowledge
#   (validates configured knowledge-base source locations)
# Memory gate: memory
#   (validates the persistent workflow memory store)
#
# Environment:
#   QF_STAGE_ENFORCE=1  make findings blocking (non-zero exit)
#   QF_RUN_TESTS=1      let the testing stage run the suite
#   QF_DIFF_BASE=<ref>  diff changed files against <ref> instead of the worktree

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

ALL="spec planning design implementation testing deployment maintenance leakage backtest repro data-contract pipeline-contract alert-contract monitoring-coverage secret-scan docs-link agent-catalog spec-index readme-sync doc-counts quantsmith-version agent-attribution knowledge memory role-context data-provenance model-plugin source-catalog"
stages="$*"
[ -z "$stages" ] && stages="$ALL"

rc=0
for stage in $stages; do
  script="$DIR/${stage}-check.sh"
  if [ ! -f "$script" ]; then
    printf 'Unknown stage: %s\n' "$stage" >&2
    printf 'Valid stages: %s\n' "$ALL" >&2
    rc=2
    continue
  fi
  sh "$script" || rc=1
done

exit "$rc"