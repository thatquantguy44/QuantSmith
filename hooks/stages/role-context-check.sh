#!/bin/sh
# Data-safety gate - Role context check.
#
# Backs agents/role_operations/ and templates/role_operations/role_context.yml.
# The whole point of role_context.yml is that it can carry real platform/team/
# data specifics locally so agents can be tailored to actual work -- which is
# exactly why it must never be committed. This gate has one deterministic job
# (is role_context.yml tracked by git?) and one advisory, heuristic job (does
# the shipped template still look like placeholders?), held to DIFFERENT
# enforcement: the deterministic job uses qf_warn and is what
# QF_STAGE_ENFORCE=1 actually blocks on; the heuristic job uses qf_notice --
# visible, but never counted toward the blocking exit code, since a
# placeholder-shaped false positive should never fail CI on every run.
#
# Resolution order (mirrors templates/knowledge/knowledge_sources.yml):
#   1. $QF_ROLE_CONTEXT   path to a filled-in context file
#   2. ./role_context.yml at the repo root (gitignored by default; local only)
#   3. none configured -- role_operations agents work generically without one

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header role-context "Role context check"
cd "$QF_ROOT"

# --- 1. Deterministic check: role_context.yml must never be tracked by git ---
# (a real config is exactly the kind of file that accumulates platform names,
# team/committee names, and other company-specific detail over time.)
for candidate in role_context.yml role_context.yaml; do
  if git ls-files --error-unmatch "$candidate" >/dev/null 2>&1; then
    qf_warn "$candidate is tracked by git -- role context must stay local-only (see templates/role_operations/role_context.yml)."
  elif git diff --cached --name-only 2>/dev/null | grep -qx "$candidate"; then
    qf_warn "$candidate is staged for commit -- unstage it; role context must stay local-only."
  fi
done

# --- 2. Resolve the active context file (if any), report only its shape ---
context=""
if [ -n "${QF_ROLE_CONTEXT:-}" ]; then
  context="$QF_ROLE_CONTEXT"
elif [ -f role_context.yml ]; then
  context="role_context.yml"
elif [ -f role_context.yaml ]; then
  context="role_context.yaml"
fi

if [ -z "$context" ]; then
  qf_info "No role_context.yml configured -- role_operations agents will work generically (see templates/role_operations/role_context.yml)."
else
  if [ ! -r "$context" ]; then
    qf_warn "Configured role context not readable: $context"
  else
    keys=$(grep -cE '^[a-zA-Z_][a-zA-Z0-9_]*:' "$context" 2>/dev/null || echo 0)
    qf_info "Role context: $context ($keys top-level key(s) found)."
  fi
fi

# --- 3. Advisory template-hygiene nudge: the shipped template should read as
#        placeholders, not as anyone's real specifics. Heuristic; false
#        positives/negatives are expected, same caveat as the leakage gate. ---
template="templates/role_operations/role_context.yml"
if [ -f "$template" ]; then
  if grep -qE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$template" 2>/dev/null; then
    qf_notice "$template contains what looks like an email address -- use a placeholder instead."
  fi
  if grep -qE '\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b' "$template" 2>/dev/null; then
    qf_notice "$template contains what looks like an SSN-shaped number -- remove it."
  fi
fi

qf_stage_result role-context
