#!/bin/sh
# Repo gate - agent-skills upstream integrity check (spec 0100, REQ-004).
#
# QuantSmith vendors an allowlisted subset of agent-skills under
# vendor/agent-skills/, pinned by vendor/agent-skills.lock.json. Claude Code
# sessions read that tree live (specs/0100-*/validation.md, T-001), so a hand
# edit reaches every session at once. This gate is the control that catches it.
#
# It runs `quantsmith-agent-skills verify` (one implementation of the checks,
# shared with the CLI) and reports, without network:
#   - a vendored file whose hash differs from the lock, or is missing/unlisted
#   - an allowlisted item not vendored, or a vendored item outside the allowlist
#   - a conflicting upstream item (spec-driven-development, /build, hooks, ...)
#     re-enabled in config/agent_skills.json or present in the tree (REQ-007)
#   - a marketplace/plugin source that is not a local relative path, or a
#     committed marketplace path in .claude/settings.json (AC-007)
#   - a coding-stage agent that cites no skill, or cites one that does not
#     resolve (AC-012); missing LICENSE; tree over the size budget
#
# Before the first sync (no vendor/ and no lock) only the config, manifest and
# citation checks apply. A repo without config/agent_skills.json has not adopted
# the integration and is skipped.
#
# Advisory by default; QF_STAGE_ENFORCE=1 makes findings blocking.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header agent-skills "agent-skills upstream integrity check"
cd "$QF_ROOT"

if [ ! -f config/agent_skills.json ]; then
  qf_info "No config/agent_skills.json; agent-skills integration not adopted, skipped."
  qf_stage_result agent-skills
  exit $?
fi

if ! command -v python3 >/dev/null 2>&1; then
  qf_warn "python3 not found -- cannot verify the vendored agent-skills tree."
  qf_stage_result agent-skills
  exit $?
fi

set +e
output=$(PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}" python3 -m quantsmith.agent_skills verify --root . 2>&1)
status=$?
set -e

if [ "$status" -eq 2 ] || ! findings=$(printf '%s' "$output" | python3 -c '
import json, sys
for f in json.load(sys.stdin)["findings"]:
    print(f)
' 2>/dev/null); then
  qf_warn "agent-skills verify could not run: PYTHONPATH=src python3 -m quantsmith.agent_skills verify"
  printf '%s\n' "$output"
  qf_stage_result agent-skills
  exit $?
fi

if [ -n "$findings" ]; then
  printf '%s\n' "$findings" | while IFS= read -r line; do printf '  ! %s\n' "$line"; done
  count=$(printf '%s\n' "$findings" | wc -l | tr -d ' ')
  QF_FINDINGS=$((QF_FINDINGS + count))
else
  if [ -f vendor/agent-skills.lock.json ]; then
    qf_info "vendor/agent-skills matches its lock; allowlist, manifests and citations OK."
  else
    qf_info "Not vendored yet; config, manifests and citations OK."
  fi
fi

qf_stage_result agent-skills
