#!/bin/sh
# Docs gate - Documented-count drift check.
#
# The narrative docs state headline counts: how many agents, quality gates,
# and instruction standards the SDK has. agent-catalog, spec-index, and
# readme-sync each check that an *entity* is listed somewhere; none of them
# can check a number written in prose, which is how all three counts came to
# drift at once. This gate derives the truth from the filesystem and reports
# every stated count that disagrees with it.
#
# Only counts derivable from the filesystem are in scope -- a claim like
# "advisory by default" is prose no gate should adjudicate.
#
# Advisory by default; set QF_STAGE_ENFORCE=1 to block.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header doc-counts "Documented-count drift check"
cd "$QF_ROOT"

# --- derived truth ---------------------------------------------------------
# The agent definition is deliberately the same one agent-catalog-check.sh and
# .githooks/pre-commit use, so all three move together rather than diverging.
true_agents=$(find agents -type f -name prompt.md 2>/dev/null | wc -l | tr -d ' ')
true_gates=$(ls hooks/stages/*-check.sh 2>/dev/null | wc -l | tr -d ' ')
true_instructions=$(ls instructions/*.md 2>/dev/null | grep -v 'README\.md$' | wc -l | tr -d ' ')
true_specs=$(find specs -mindepth 2 -name spec.md 2>/dev/null | wc -l | tr -d ' ')

checked=0
scanned=0

# scan_entity: file, label, truth, pattern
# POSIX grep has no capture groups, so match the whole phrase and then pull
# the digits out of each match. Spaces are folded to underscores first so
# word-splitting cannot break a multi-word phrase apart.
scan_entity() {
  _file=$1
  _label=$2
  _truth=$3
  _pattern=$4
  for _match in $(grep -oEi "$_pattern" "$_file" 2>/dev/null | tr ' ' '_'); do
    _stated=$(printf '%s' "$_match" | grep -oE '[0-9]+' | head -1)
    [ -n "$_stated" ] || continue
    checked=$((checked + 1))
    if [ "$_stated" -ne "$_truth" ]; then
      qf_warn "$_file: says $_stated $_label, actual is $_truth."
    fi
  done
}

for doc in README.md docs/handoff.md docs/sdk_plan.md; do
  if [ ! -f "$doc" ]; then
    qf_info "$doc not present; skipped."
    continue
  fi
  scanned=$((scanned + 1))

  scan_entity "$doc" "agents" "$true_agents" '[0-9]+ agents'
  scan_entity "$doc" "agents" "$true_agents" '[0-9]+ agent contracts'
  scan_entity "$doc" "agents" "$true_agents" '[0-9]+ narrow, inspectable agent roles'
  scan_entity "$doc" "agents" "$true_agents" 'Agents \([0-9]+'
  # Shields.io badge form, e.g. badge/Agents-161-6f42c1
  scan_entity "$doc" "agents" "$true_agents" 'badge/Agents-[0-9]+'

  scan_entity "$doc" "quality gates" "$true_gates" '[0-9]+ quality gates'
  scan_entity "$doc" "quality gates" "$true_gates" 'Gates \([0-9]+\)'
  scan_entity "$doc" "quality gates" "$true_gates" '\([0-9]+ gates\)'
  # Must start AFTER the URL-encoded space: a pattern including "%20" would
  # have its digits read as "20" by the first-digits extraction below.
  scan_entity "$doc" "quality gates" "$true_gates" 'Gates-[0-9]+'

  scan_entity "$doc" "instruction standards" "$true_instructions" '[0-9]+ instruction standards'
  scan_entity "$doc" "instruction standards" "$true_instructions" 'Instructions \([0-9]+\)'

  scan_entity "$doc" "specs" "$true_specs" 'badge/Specs-[0-9]+'
done

# Report coverage: a regex that silently stops matching would otherwise look
# exactly like a pass.
qf_info "Truth: $true_agents agent(s), $true_gates gate(s), $true_instructions instruction standard(s), $true_specs spec(s)."
qf_info "Checked $checked count claim(s) across $scanned document(s)."
if [ "$checked" -eq 0 ] && [ "$scanned" -gt 0 ]; then
  qf_warn "No count claims matched in any scanned document; the patterns may be stale."
fi

qf_stage_result doc-counts
