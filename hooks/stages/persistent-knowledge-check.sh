#!/bin/sh
# Repo gate - Persistent knowledge guide sync check.
#
# PERSISTENT_KNOWLEDGE.md at the repo root is the guide to the workflow-memory
# system: what is built, what is planned, and a live status table (record
# count, spec 0048 task/AC progress). Like every narrative doc in this repo, it
# drifts the moment nobody depends on it -- and a knowledge-system guide with
# stale knowledge-system numbers undermines the very thing it is explaining.
#
# WHAT THIS CAN AND CANNOT CHECK -- stated plainly, same limit handoff-sync and
# doc-counts name about themselves:
#
#   CAN   the four numbers in the status table (records, 0048 tasks done/total,
#         ACs verified) against what the filesystem actually shows, and that a
#         change to the memory system arrives with an edit to this file.
#   CANNOT  whether the prose elsewhere in the guide is accurate. That still
#         needs a human.
#
# Advisory by default; QF_STAGE_ENFORCE=1 makes findings blocking.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header persistent-knowledge "Persistent knowledge guide sync check"
cd "$QF_ROOT"

GUIDE="PERSISTENT_KNOWLEDGE.md"
TASKS="specs/0048-workflow-memory-runtime/tasks.md"

if [ ! -f "$GUIDE" ]; then
  qf_info "$GUIDE not present; skipped (this repo may not carry the memory system)."
  qf_stage_result persistent-knowledge
  exit $?
fi
if [ ! -s "$GUIDE" ]; then
  qf_warn "$GUIDE exists but is empty."
  qf_stage_result persistent-knowledge
  exit $?
fi

# --- 1. Numeric drift -------------------------------------------------------
true_records=$(grep -h 'id: MEM' memory/*/*.yaml memory/*/*/*/*.yaml 2>/dev/null | wc -l | tr -d ' ')

if [ -f "$TASKS" ]; then
  task_rows=$(sed -n '/^## Task List/,/^Status values/p' "$TASKS" | grep -E '^\| T-')
  true_tasks_total=$(printf '%s\n' "$task_rows" | grep -c '^| T-' || true)
  true_tasks_done=$(printf '%s\n' "$task_rows" | grep -cE '\| done \|' || true)

  ac_rows=$(sed -n '/^## Test Coverage Map/,/^## Sequencing/p' "$TASKS" | grep -E '^\| AC-')
  true_acs_total=$(printf '%s\n' "$ac_rows" | grep -c '^| AC-' || true)
  true_acs_done=$(printf '%s\n' "$ac_rows" | grep -cE '\| done \|' || true)
else
  qf_info "$TASKS not found; task/AC counts not compared this run."
  true_tasks_total=""; true_tasks_done=""; true_acs_total=""; true_acs_done=""
fi

checked=0

check_count() {
  # check_count <label> <stated-regex> <true-value>
  _label=$1; _pattern=$2; _truth=$3
  [ -n "$_truth" ] || return 0
  _stated=$(grep -oE "$_pattern" "$GUIDE" 2>/dev/null | head -1 | grep -oE '[0-9]+' | head -1)
  [ -n "$_stated" ] || return 0
  checked=$((checked + 1))
  if [ "$_stated" -ne "$_truth" ]; then
    qf_warn "$GUIDE: says $_stated $_label, actual is $_truth."
  fi
}

check_count "record(s) in the store" '\*\*[0-9]+\*\* — `memory' "$true_records"
check_count "0048 tasks done" '\*\*[0-9]+ of [0-9]+ done\*\*' "$true_tasks_done"
check_count "acceptance criteria verified" '\*\*[0-9]+ of [0-9]+\*\*' "$true_acs_done"

if [ "$checked" -eq 0 ]; then
  qf_warn "No count claims matched in $GUIDE; the patterns may be stale relative to the file's format."
else
  qf_info "Truth: $true_records record(s), $true_tasks_done/$true_tasks_total spec-0048 task(s) done, $true_acs_done/$true_acs_total AC(s) verified. Checked $checked claim(s)."
fi

# --- 2. Co-change: a memory-system change should arrive with a guide edit --
# Deliberately narrow to the files that change the numbers or the shape of the
# system this guide describes -- not every repo change, which would nag and
# train people to make token edits to silence it.
changed=$(qf_changed_files)
if [ -n "$changed" ]; then
  guide_touched=0
  printf '%s\n' "$changed" | grep -qx "$GUIDE" && guide_touched=1

  memory_touched=0
  for f in $changed; do
    case "$f" in
      src/quantsmith/pipelines/workflow_memory.py) memory_touched=1 ;;
      memory/*.yaml|memory/*/*.yaml|memory/*/*/*.yaml|memory/*/*/*/*.yaml) memory_touched=1 ;;
      "$TASKS") memory_touched=1 ;;
    esac
  done

  if [ "$memory_touched" -eq 1 ] && [ "$guide_touched" -eq 0 ]; then
    qf_warn "workflow_memory.py, a memory/ record, or 0048's tasks.md changed, but $GUIDE was not touched -- its status table may now be stale."
  fi
fi

qf_stage_result persistent-knowledge
