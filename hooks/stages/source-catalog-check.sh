#!/bin/sh
# Docs/data-safety gate - Data source catalog check.
#
# Backs sources/ and templates/data/source_catalog_entry.yml. Three jobs:
#   1. Every sources/*.yml declares the required contract fields.
#   2. Every sources/*.yml is listed in the index, sources/README.md (the same
#      "every X is indexed" pattern as spec-index-check.sh/agent-catalog-check.sh).
#   3. Advisory heuristic: credential_ref (and the file generally) doesn't
#      contain a real token-shaped secret value -- reuses secret-scan's
#      high-signal token patterns, not a new heuristic.
# Advisory by default; QF_STAGE_ENFORCE=1 blocks.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header source-catalog "Data source catalog check"
cd "$QF_ROOT"

if [ ! -d sources ]; then
  qf_info "No sources/ directory; source-catalog check skipped."
  qf_stage_result source-catalog
  exit $?
fi

index="sources/README.md"
if [ ! -f "$index" ]; then
  qf_warn "Source catalog index missing: $index"
  qf_stage_result source-catalog
  exit $?
fi

# High-signal secret token formats, same set secret-scan-check.sh uses -- a
# credential_ref should be a pointer (a name/path), never a real value.
TOKEN_RE='AKIA[0-9A-Z]{16}|ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{22,}|xox[baprs]-[0-9A-Za-z-]{10,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY-----|[A-Za-z][A-Za-z0-9+.-]*://[^:@/[:space:]]+:[^@/[:space:]]+@'

check_field() {
  if grep -qE "$2" "$1" 2>/dev/null; then qf_info "  $3: declared."
  else qf_warn "  $3: not declared in $(basename "$1")."; fi
}

count=0
for f in sources/*.yml sources/*.yaml; do
  [ -f "$f" ] || continue
  count=$((count + 1))
  id=$(basename "$f" | sed -E 's/\.ya?ml$//')

  qf_info "$(basename "$f"):"
  check_field "$f" "^source_id:"              "source_id"
  check_field "$f" "^name:"                    "name"
  check_field "$f" "^type:"                    "type"
  check_field "$f" "^owner:"                    "owner"
  check_field "$f" "^description:"             "description"
  check_field "$f" "^access_level:"            "access_level"
  check_field "$f" "^quality:"                 "quality block"
  check_field "$f" "^connection:"               "connection block"
  check_field "$f" "credential_ref:"            "credential_ref"
  check_field "$f" "^status:"                   "status"

  if ! grep -qF "$id" "$index" 2>/dev/null; then
    qf_warn "Source not listed in $index: $id"
  fi

  if grep -nE "$TOKEN_RE" "$f" 2>/dev/null | grep -v 'qf:allow-secret' >/dev/null; then
    qf_warn "$f: credential_ref or file body looks like a real secret value, not a pointer."
  fi
done

qf_info "Checked $count source(s) against the catalog."
qf_stage_result source-catalog
