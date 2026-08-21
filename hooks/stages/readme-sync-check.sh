#!/bin/sh
# Docs gate - README index/runtime sync check.
#
# For every spec listed in specs/README.md's index whose Tests column names
# a real pytest module (a backtick-quoted `test_*.py` pattern), verifies the
# same spec ID also appears in root README.md's runtime table. Catches the
# one sync step agent-catalog/spec-index don't cover: specs/README.md and
# root README.md drifting apart from each other as new tested runtimes ship.
# Advisory by default; set QF_STAGE_ENFORCE=1 to block.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header readme-sync "README index/runtime sync check"
cd "$QF_ROOT"

spec_index="specs/README.md"
root_readme="README.md"

if [ ! -f "$spec_index" ] || [ ! -f "$root_readme" ]; then
  qf_info "specs/README.md or root README.md missing; readme-sync check skipped."
  qf_stage_result readme-sync
  exit $?
fi

rows=$(mktemp)
trap 'rm -f "$rows"' EXIT

grep -E '^\| \[[0-9]{4}-' "$spec_index" > "$rows" 2>/dev/null || true

count=0
while IFS= read -r line; do
  id=$(printf '%s\n' "$line" | grep -oE '^\| \[[0-9]{4}' | grep -oE '[0-9]{4}')
  [ -n "$id" ] || continue
  tests_col=$(printf '%s\n' "$line" | awk -F'|' '{print $5}')
  case "$tests_col" in
    *test_*.py*) : ;;
    *) continue ;;
  esac
  count=$((count + 1))
  if ! grep -qF "[\`$id\`]" "$root_readme" 2>/dev/null; then
    qf_warn "Spec $id has a tested runtime (see $spec_index's Tests column) but is not listed in $root_readme's runtime table."
  fi
done < "$rows"

qf_info "Checked $count spec(s) with a tested runtime against $root_readme."
qf_stage_result readme-sync
