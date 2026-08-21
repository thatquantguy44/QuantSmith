#!/bin/sh
# Repo gate - Handoff sync check.
#
# `docs/handoff.md` is the roadmap a new owner reads first. It drifts silently,
# because nothing has ever depended on it: a spec can be written, approved, and
# shipped without the handoff ever mentioning it, and the only symptom is that
# the next person cannot find the work.
#
# WHAT THIS CAN AND CANNOT CHECK -- stated plainly, because the gate's name
# overpromises:
#
#   CAN   every spec directory is referenced somewhere in the handoff, and a
#         newly added spec arrives together with a handoff edit.
#   CANNOT  whether what the handoff SAYS about a spec is true. Prose that
#         describes 0044 as "planned" passes forever if the id appears. This
#         gate defends against silence, not against staleness.
#
# The same limit `0043`'s doc-counts gate names: the countable part is
# mechanical, the narrative part still needs a human. Countable drift is caught
# by doc-counts; missing entries are caught here; wrong entries are caught by
# neither.
#
# Advisory by default; QF_STAGE_ENFORCE=1 makes findings blocking. The
# pre-commit hook runs it blocking, so a new spec cannot be committed without
# its handoff entry.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header handoff-sync "Handoff roadmap sync check"
cd "$QF_ROOT"

# The roadmap's filename is per-repo: this SDK calls it docs/handoff.md, a
# scaffolded repo calls it docs/roadmap.md. Read the declared path when the
# repo ships a quantsmith.conf, and fall back to this repo's own name so
# nothing changes here.
HANDOFF="docs/handoff.md"
if [ -f quantsmith.conf ]; then
  # shellcheck disable=SC1091
  . ./quantsmith.conf
  [ -n "${QF_DOC_ROADMAP:-}" ] && HANDOFF="$QF_DOC_ROADMAP"
fi

if [ ! -s "$HANDOFF" ]; then
  qf_warn "$HANDOFF is missing or empty -- the roadmap a new owner reads first."
  qf_stage_result handoff-sync
  exit $?
fi

# --- 1. Coverage: every spec must be referenced somewhere in the handoff -----
# Deterministic, and the durable invariant. Mirrors how spec-index guards
# specs/README.md and readme-sync guards the root README runtime table.
total=0
unreferenced=0
for dir in specs/[0-9]*/; do
  [ -d "$dir" ] || continue
  slug=$(basename "$dir")
  id=${slug%%-*}
  total=$((total + 1))
  # Match the bare id (`0044`) or the full slug, in any surrounding punctuation.
  if ! grep -qE "(^|[^0-9])${id}([^0-9]|$)|${slug}" "$HANDOFF"; then
    qf_warn "Spec $slug is not referenced in $HANDOFF -- a reader of the roadmap cannot find it."
    unreferenced=$((unreferenced + 1))
  fi
done

if [ "$unreferenced" -eq 0 ]; then
  qf_info "All $total spec(s) referenced in $HANDOFF."
fi

# --- 2. Co-change: a NEW spec must arrive with a handoff edit ----------------
# Deliberately narrow. Firing on *any* spec edit would nag on typo fixes and
# train people to make token handoff edits to silence it -- which is worse than
# no gate. A new spec directory is a real event and exactly when the roadmap
# needs a new entry.
changed=$(qf_changed_files)
if [ -n "$changed" ]; then
  handoff_touched=0
  printf '%s\n' "$changed" | grep -qx "$HANDOFF" && handoff_touched=1

  new_specs=""
  for f in $changed; do
    case "$f" in
      specs/[0-9]*/spec.md)
        slug=$(printf '%s' "$f" | cut -d/ -f2)
        id=${slug%%-*}
        # Only a spec the handoff does not yet mention counts as "new" here;
        # editing an already-documented spec is not this gate's business.
        if ! grep -qE "(^|[^0-9])${id}([^0-9]|$)|${slug}" "$HANDOFF"; then
          new_specs="$new_specs $slug"
        fi
        ;;
    esac
  done

  if [ -n "$new_specs" ] && [ "$handoff_touched" -eq 0 ]; then
    for s in $new_specs; do
      qf_warn "New spec $s is in this change but $HANDOFF is not -- add its roadmap entry in the same commit."
    done
  fi
fi

qf_stage_result handoff-sync
