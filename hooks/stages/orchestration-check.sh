#!/bin/sh
# Agentic quant gate - Orchestration envelope check.
#
# Validates spec 0070 prompt/context/harness evidence for committed example
# envelopes: run envelope references, prompt manifests, context access and
# point-in-time fields, assumption ledgers, evaluation harness layers, audit
# event relationships, and replay metadata. Advisory by default; set
# QF_STAGE_ENFORCE=1 to block.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header orchestration "Prompt/context/harness orchestration check"
cd "$QF_ROOT"

if [ ! -d templates/orchestration ]; then
  qf_warn "templates/orchestration missing -- spec 0070 templates are required."
else
  qf_info "Orchestration templates present."
fi

missing_template=0
for template in \
  templates/orchestration/run_envelope.template.json \
  templates/orchestration/prompt_manifest.template.json \
  templates/orchestration/context_manifest.template.json \
  templates/orchestration/assumption_ledger.template.jsonl \
  templates/orchestration/evaluation_harness.template.json \
  templates/orchestration/audit_events.template.jsonl; do
  if [ ! -f "$template" ]; then
    missing_template=1
    qf_warn "Missing orchestration template: $template"
  fi
done
[ "$missing_template" -eq 0 ] && qf_info "Required orchestration templates found."

if [ ! -d examples/orchestration ]; then
  qf_warn "examples/orchestration missing -- spec 0070 requires deterministic and fixture-backed examples."
  qf_stage_result orchestration
  exit $?
fi

if command -v python3 >/dev/null 2>&1; then
  if output=$(PYTHONPATH=src python3 -m quantsmith.orchestration validate --discover examples/orchestration 2>&1); then
    qf_info "$output"
  else
    qf_warn "Orchestration validation failed. Run: PYTHONPATH=src python3 -m quantsmith.orchestration validate --discover examples/orchestration"
    printf '%s\n' "$output"
  fi
else
  qf_warn "python3 not found -- cannot run orchestration validator."
fi

qf_stage_result orchestration
