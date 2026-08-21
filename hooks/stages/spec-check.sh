#!/bin/sh
# Cross-cutting - Spec-Driven Development chain & traceability gate.
#
# For each specs/<id>/ directory, validates the SDD rules from
# instructions/spec_driven_development.md:
#   R1  spec.md, plan.md, tasks.md present (no plan/tasks without a spec)
#   R2  spec.md declares requirements (REQ-*/NFR-*) and acceptance criteria (AC-*)
#   R3  every REQ-*/NFR-* is covered somewhere in plan.md or tasks.md
#   R4  every AC-* is referenced in tasks.md (test coverage map)
#   R5  no orphan tasks: every T-* row cites a REQ-*/NFR-*
# Advisory by default; set QF_STAGE_ENFORCE=1 to block.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header spec "Spec-driven chain & traceability check"
cd "$QF_ROOT"

if [ ! -d specs ]; then
  qf_info "No specs/ directory; spec-driven checks skipped."
  qf_stage_result spec
  exit $?
fi

# Collect spec directories (those containing at least one of the SDD files).
spec_dirs=""
for d in specs/*/; do
  [ -d "$d" ] || continue
  if [ -f "${d}spec.md" ] || [ -f "${d}plan.md" ] || [ -f "${d}tasks.md" ]; then
    spec_dirs="$spec_dirs $d"
  fi
done

if [ -z "$spec_dirs" ]; then
  qf_info "No spec directories found under specs/."
  qf_stage_result spec
  exit $?
fi

ids() { # extract sorted-unique IDs matching a pattern from a file
  grep -oE "$1" "$2" 2>/dev/null | sort -u
}

for d in $spec_dirs; do
  name=$(basename "$d")
  spec="${d}spec.md"
  plan="${d}plan.md"
  tasks="${d}tasks.md"
  before=$QF_FINDINGS

  # R1: chain completeness
  [ -f "$spec" ]  || qf_warn "$name: missing spec.md"
  [ -f "$plan" ]  || qf_warn "$name: missing plan.md (no plan without a spec, and no plan file at all)"
  [ -f "$tasks" ] || qf_warn "$name: missing tasks.md"
  if [ ! -f "$spec" ]; then
    # Without a spec there is nothing to trace against; move on.
    continue
  fi

  # R2: spec declares requirements and acceptance criteria
  reqs=$(ids 'REQ-[0-9]+|NFR-[0-9]+' "$spec")
  acs=$(ids 'AC-[0-9]+' "$spec")
  [ -n "$reqs" ] || qf_warn "$name: spec.md declares no REQ-*/NFR-* identifiers"
  [ -n "$acs" ]  || qf_warn "$name: spec.md declares no AC-* acceptance criteria"

  # R3: every requirement is covered in plan.md or tasks.md
  cover_src=""
  [ -f "$plan" ]  && cover_src="$cover_src $plan"
  [ -f "$tasks" ] && cover_src="$cover_src $tasks"
  for r in $reqs; do
    if [ -z "$cover_src" ] || ! grep -qE "(^|[^A-Z])$r([^0-9]|$)" $cover_src 2>/dev/null; then
      qf_warn "$name: requirement $r not covered in plan.md/tasks.md"
    fi
  done

  # R4: every acceptance criterion is referenced in tasks.md
  if [ -f "$tasks" ]; then
    for a in $acs; do
      if ! grep -qE "(^|[^A-Z])$a([^0-9]|$)" "$tasks" 2>/dev/null; then
        qf_warn "$name: acceptance criterion $a has no test reference in tasks.md"
      fi
    done
  fi

  # R5: no orphan tasks (each T-* table row cites a REQ-*/NFR-*)
  if [ -f "$tasks" ]; then
    while IFS= read -r line; do
      case "$line" in
        \|*T-[0-9]*)
          if ! printf '%s' "$line" | grep -qE 'REQ-[0-9]+|NFR-[0-9]+'; then
            tid=$(printf '%s' "$line" | grep -oE 'T-[0-9]+' | head -n1)
            qf_warn "$name: task $tid cites no REQ-*/NFR-* (orphan task)"
          fi
          ;;
      esac
    done < "$tasks"
  fi

  [ "$QF_FINDINGS" -eq "$before" ] && qf_info "$name: chain and traceability OK"
done

qf_stage_result spec
