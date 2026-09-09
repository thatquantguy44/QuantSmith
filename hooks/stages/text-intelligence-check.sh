#!/bin/sh
# Agentic quant gate - NLP/LLM/text-intelligence evidence check.
#
# Validates spec-0071 templates and committed manifests, including their
# source, access, point-in-time, transformation, task, signal, evaluation,
# audit, and authoritative spec-0070 envelope links. Advisory by default;
# set QF_STAGE_ENFORCE=1 to block.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header text-intelligence "NLP/LLM/text-intelligence evidence check"
cd "$QF_ROOT"

missing_template=0
for template in \
  templates/text_intelligence/text_intelligence_manifest.template.json \
  templates/text_intelligence/corpus_snapshot.template.json \
  templates/text_intelligence/transform_chain.template.json \
  templates/text_intelligence/model_capabilities.template.json \
  templates/text_intelligence/embedding_artifact.template.json \
  templates/text_intelligence/index_snapshot.template.json \
  templates/text_intelligence/training_run.template.json \
  templates/text_intelligence/task_results.template.json \
  templates/text_intelligence/text_signals.template.json \
  templates/text_intelligence/text_evaluation.template.json; do
  if [ ! -f "$template" ]; then
    missing_template=1
    qf_warn "Missing text-intelligence template: $template"
  fi
done
[ "$missing_template" -eq 0 ] && qf_info "Required text-intelligence templates found."

if [ ! -d examples/text_intelligence ]; then
  qf_warn "examples/text_intelligence missing -- spec 0071 requires offline reference evidence."
  qf_stage_result text-intelligence
  exit $?
fi

if command -v python3 >/dev/null 2>&1; then
  if output=$(PYTHONPATH=src python3 -m quantsmith.text_intelligence validate --discover examples/text_intelligence 2>&1); then
    qf_info "$output"
  else
    qf_warn "Text-intelligence validation failed. Run: PYTHONPATH=src python3 -m quantsmith.text_intelligence validate --discover examples/text_intelligence"
    printf '%s\n' "$output"
  fi
else
  qf_warn "python3 not found -- cannot run text-intelligence validator."
fi

qf_stage_result text-intelligence
