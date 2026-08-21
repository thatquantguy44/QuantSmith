#!/bin/sh
# Repo gate - Ownership check.
#
# A gate nobody owns is a gate that gets bypassed. When a check fails at 6pm
# and the person who hit it cannot find out why or who to ask, the rational
# move is `--no-verify` -- and a bypassed gate is worse than no gate, because
# everyone still believes it ran.
#
# This gate makes ownership a checkable fact rather than an intention. It looks
# for three things:
#
#   1. An ownership document exists and names real owners, not placeholders.
#   2. CODEOWNERS exists and carries no unreplaced placeholder.
#   3. A gate runbook exists, so "what do I do about this failure" has an
#      answer that is not a person's memory.
#
# Placeholder detection is the substance. A scaffolded repo ships `@OWNER` and
# `<@handle>` on purpose, and those are exactly the strings that survive to
# production if nothing looks for them. An unfilled template reads as governed
# while owning nothing.
#
# Advisory by default; QF_STAGE_ENFORCE=1 makes findings blocking. Worth
# promoting to blocking once a repo has more than one contributor.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header ownership "Ownership & support-path check"
cd "$QF_ROOT"

# Placeholders the scaffold ships. Finding one means the template was copied
# and never filled in.
PLACEHOLDER_RE='@OWNER\b|<@handle>|<owner>|TBD|FIXME'

# --- 1. CODEOWNERS -----------------------------------------------------------
codeowners=""
for c in .github/CODEOWNERS CODEOWNERS docs/CODEOWNERS; do
  [ -f "$c" ] && { codeowners="$c"; break; }
done

if [ -z "$codeowners" ]; then
  qf_warn "No CODEOWNERS file -- review has no defined router."
else
  if grep -qE "$PLACEHOLDER_RE" "$codeowners" 2>/dev/null; then
    n=$(grep -cE "$PLACEHOLDER_RE" "$codeowners")
    qf_warn "$codeowners still has $n unreplaced placeholder(s) -- it names no real owner."
  else
    owners=$(grep -cE '^[^#[:space:]]' "$codeowners" 2>/dev/null || echo 0)
    qf_info "$codeowners: $owners rule(s), no placeholders."
  fi
fi

# --- 2. Ownership document ---------------------------------------------------
ownership=""
for o in docs/ownership.md docs/OWNERSHIP.md OWNERSHIP.md; do
  [ -f "$o" ] && { ownership="$o"; break; }
done

if [ -z "$ownership" ]; then
  qf_warn "No docs/ownership.md -- nobody is named as the person to ask."
elif grep -qE "$PLACEHOLDER_RE" "$ownership" 2>/dev/null; then
  n=$(grep -cE "$PLACEHOLDER_RE" "$ownership")
  qf_warn "$ownership has $n unfilled owner slot(s) -- an unfilled table owns nothing."
else
  qf_info "$ownership: owners named."
fi

# --- 3. Runbook --------------------------------------------------------------
runbook=""
for r in docs/gate_runbook.md docs/runbook.md docs/RUNBOOK.md; do
  [ -f "$r" ] && { runbook="$r"; break; }
done

if [ -z "$runbook" ]; then
  qf_info "No gate runbook found; a failing gate has no written first response."
else
  # A runbook that covers a third of the gates is a start; one that covers none
  # of them is a filename.
  total=$(ls hooks/stages/*-check.sh 2>/dev/null | wc -l | tr -d ' ')
  covered=0
  for g in hooks/stages/*-check.sh; do
    name=$(basename "$g" -check.sh)
    grep -q "$name" "$runbook" 2>/dev/null && covered=$((covered + 1))
  done
  qf_info "$runbook covers $covered of $total gate(s)."
  [ "$covered" -eq 0 ] && qf_warn "$runbook names no gate -- it cannot answer a gate failure."
fi

qf_stage_result ownership
