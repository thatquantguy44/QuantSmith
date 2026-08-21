#!/bin/sh
# Data-safety gate - Model plugin registration check.
#
# Backs adapters/model_plugin/ and templates/optimization/model_plugin_manifest.yml.
# A registered model's manifest entry is itself likely to name a real internal
# model, its real objective/constraint shape, and a real invocation endpoint --
# all company-specific -- so this gate has the same two jobs as role-context:
#   1. Deterministic: is model_plugins.yml tracked or staged by git?
#   2. Advisory: does the resolved manifest declare the required contract
#      fields per registered model entry?
# Advisory by default; QF_STAGE_ENFORCE=1 blocks on the tracked-file finding.
#
# Resolution order (mirrors templates/knowledge/knowledge_sources.yml):
#   1. $QF_MODEL_PLUGINS   path to a filled-in manifest
#   2. ./model_plugins.yml at the repo root (gitignored by default; local only)
#   3. none configured     no plugin models are registered

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header model-plugin "Model plugin registration check"
cd "$QF_ROOT"

# --- 1. Deterministic check: model_plugins.yml must never be tracked ---
for candidate in model_plugins.yml model_plugins.yaml; do
  if git ls-files --error-unmatch "$candidate" >/dev/null 2>&1; then
    qf_warn "$candidate is tracked by git -- model plugin registrations must stay local-only (see templates/optimization/model_plugin_manifest.yml)."
  elif git diff --cached --name-only 2>/dev/null | grep -qx "$candidate"; then
    qf_warn "$candidate is staged for commit -- unstage it; registrations must stay local-only."
  fi
done

# --- 2. Resolve the active manifest (if any) and check required fields ---
manifest=""
if [ -n "${QF_MODEL_PLUGINS:-}" ]; then
  manifest="$QF_MODEL_PLUGINS"
elif [ -f model_plugins.yml ]; then
  manifest="model_plugins.yml"
elif [ -f model_plugins.yaml ]; then
  manifest="model_plugins.yaml"
fi

if [ -z "$manifest" ]; then
  qf_info "No model_plugins.yml configured -- no models registered (see templates/optimization/model_plugin_manifest.yml)."
  qf_stage_result model-plugin
  exit $?
fi

if [ ! -r "$manifest" ]; then
  qf_warn "Configured model plugin manifest not readable: $manifest"
  qf_stage_result model-plugin
  exit $?
fi

count=$(grep -cE '^\s*-\s*model_id:' "$manifest" 2>/dev/null || echo 0)
qf_info "Manifest: $manifest ($count registered model(s))."

check_field() {
  if grep -qE "$2" "$1" 2>/dev/null; then qf_info "  $3: declared."
  else qf_warn "  $3: not declared in $1."; fi
}

if [ "${count:-0}" -gt 0 ]; then
  check_field "$manifest" "owner:"              "owner"
  check_field "$manifest" "category:"           "category"
  check_field "$manifest" "objective:"          "declared capability (objective)"
  check_field "$manifest" "invocation:"         "invocation block"
  check_field "$manifest" "type:"                "invocation type"
  check_field "$manifest" "review_status:"      "review status"
fi

qf_stage_result model-plugin
