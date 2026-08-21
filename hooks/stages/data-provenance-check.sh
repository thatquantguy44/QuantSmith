#!/bin/sh
# Data-safety gate - Data provenance / synthetic-data disclosure check.
#
# Backs instructions/data_provenance.md: any content built from data or
# visuals must be traceable to its source, actual data is preferred over
# synthetic, and every use of synthetic data is disclosed. This gate has two
# jobs, deliberately held to DIFFERENT enforcement:
#   1. When a Synthetic Data Disclosure artifact exists, verify it declares
#      the required fields (see templates/docs/synthetic_data_disclosure.md).
#      Structural -- a real artifact either has the field or it does not.
#      This is what QF_STAGE_ENFORCE=1 blocks on (qf_warn).
#   2. Heuristic: flag generated-looking report/dashboard artifacts that
#      mention synthetic/simulated/mock data with no matching disclosure
#      anywhere in the tree. Same honestly-scoped limitation as the leakage
#      gate -- false positives/negatives expected -- so it is reported via
#      qf_notice, visible but NEVER blocking, even under enforce. Wiring it
#      to the same counter as (1) means a narrative doc's honest mention of
#      "synthetic" (e.g. describing this SDK's own disclosed synthetic
#      backtest examples) would fail CI on every single run forever, which
#      is what happened before this distinction existed.
# Advisory by default; QF_STAGE_ENFORCE=1 blocks only on (1).

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header data-provenance "Data provenance / synthetic-data disclosure check"
cd "$QF_ROOT"

path_ignored() {
  case "$1" in
    agents/*|templates/*|prompts/*|instructions/*|hooks/*|specs/*|.githooks/*) return 0 ;;
  esac
  return 1
}

# --- 1. Disclosure artifacts: validate required fields when present ---
disclosures=""
for pattern in "*synthetic_data_disclosure*.md" "docs/*synthetic*disclosure*.md"; do
  for f in $pattern; do
    [ -f "$f" ] || continue
    path_ignored "$f" && continue
    disclosures="$disclosures $f"
  done
done

check_field() {
  if grep -riqE "$3" "$1" 2>/dev/null; then qf_info "$(basename "$1"): $2 declared."
  else qf_warn "$(basename "$1"): $2 not declared."; fi
}

if [ -n "$disclosures" ]; then
  seen=""
  for d in $disclosures; do
    case " $seen " in *" $d "*) continue ;; esac
    seen="$seen $d"
    check_field "$d" "disclosed location"     "location.*section.*chart|section / chart"
    check_field "$d" "reason real data unused" "why real data|reason.*not used|unavailable"
    check_field "$d" "generation method"       "generation method|seed|distribution|synthetic method"
    check_field "$d" "reviewer sign-off"       "reviewer|sign-?off"
  done
else
  qf_info "No synthetic data disclosure artifact detected (see templates/docs/synthetic_data_disclosure.md)."
fi

# --- 2. Advisory heuristic: generated artifacts mentioning synthetic data ---
# Scope: report/dashboard-shaped files outside scaffold directories only, to
# keep the SDK's own instructional use of the word "synthetic" from firing.
candidates=""
for pattern in "docs/*.md" "docs/**/*.md" "examples/*.md" "examples/**/*.md"; do
  for f in $pattern; do
    [ -f "$f" ] || continue
    path_ignored "$f" && continue
    case "$f" in *synthetic_data_disclosure*) continue ;; esac
    candidates="$candidates $f"
  done
done

flagged=0
for f in $candidates; do
  if grep -liqE "synthetic data|simulated data|mock data|fabricated data|placeholder data" "$f" 2>/dev/null; then
    flagged=$((flagged + 1))
    if [ -z "$disclosures" ]; then
      qf_notice "$f mentions synthetic/simulated data with no disclosure artifact found."
    fi
  fi
done
[ "$flagged" -gt 0 ] && qf_info "Checked $flagged candidate artifact(s) mentioning synthetic data."

qf_stage_result data-provenance
