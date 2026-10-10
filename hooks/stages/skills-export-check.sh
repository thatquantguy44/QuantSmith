#!/bin/sh
# Repo gate - Skills export freshness check (spec 0110).
#
# Every public agent is exported as a Claude skill under .claude/skills/<name>/,
# recorded in .claude/skills/registry.json with its revision, dates, and hashes.
# Those files are GENERATED from agents/ by `quantsmith-skills build`. This gate
# runs the date-free `check` and reports, without network:
#   - an agent with no skill or registry entry (new agent, not rebuilt)
#   - an agent whose files changed since the last build (stale skill)
#   - a SKILL.md that differs from what the agent renders to (hand edit)
#   - a removed agent whose skill is still active or whose directory remains
#   - an invalid, reserved, colliding, or over-long skill name; a config entry
#     naming an unknown agent (config/skills_export.json)
#
# Fix every finding with: PYTHONPATH=src python3 -m quantsmith.skills_export build
#
# Advisory by default; QF_STAGE_ENFORCE=1 makes findings blocking.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header skills-export "Skills export freshness check"
cd "$QF_ROOT"

if [ ! -f .claude/skills/registry.json ] && [ ! -f config/skills_export.json ]; then
  qf_info "No skills export adopted (.claude/skills/registry.json absent); skipped."
  qf_stage_result skills-export
  exit $?
fi

if ! command -v python3 >/dev/null 2>&1; then
  qf_warn "python3 not found -- cannot check the skills export."
  qf_stage_result skills-export
  exit $?
fi

set +e
output=$(PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}" python3 -m quantsmith.skills_export check 2>&1)
status=$?
set -e

if [ "$status" -eq 0 ]; then
  qf_info "$output"
elif [ "$status" -eq 1 ]; then
  printf '%s\n' "$output" | while IFS= read -r line; do printf '  ! %s\n' "$line"; done
  count=$(printf '%s\n' "$output" | grep -vc '^fix:' || true)
  QF_FINDINGS=$((QF_FINDINGS + count))
else
  qf_warn "skills export check could not run: PYTHONPATH=src python3 -m quantsmith.skills_export check"
  printf '%s\n' "$output"
fi

qf_stage_result skills-export
