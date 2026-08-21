#!/bin/sh
# Repo gate - Upstream drift check.
#
# QuantSmith is adopted by copying surfaces (gates, standards, templates) into
# a consuming repository. That model has one failure mode and it is guaranteed:
# ten repos copy the same gate, each tunes it a little, and within a quarter no
# two are running the same check while all ten believe they are.
#
# You cannot prevent that drift -- adopters SHOULD tune gates to their repo,
# and `docs/adoption_guide.md` says so explicitly. What you can do is make it
# VISIBLE: this gate compares each copied surface against the upstream ref the
# repo claims to be pinned to, and reports what differs.
#
# Drift is therefore a finding, never an error. A tuned gate is a legitimate
# and expected state; an UNKNOWINGLY tuned gate is the problem. The point is
# that `quantsmith.conf` records the pin, this gate reports the delta, and a
# human decides which side is right.
#
# Declared in quantsmith.conf:
#   QF_UPSTREAM_REPO     git URL or local path of the upstream
#   QF_UPSTREAM_REF      the tag/commit this repo is pinned to
#   QF_UPSTREAM_SURFACES space-separated paths this repo copied
#
# Offline-tolerant by design: if the upstream cannot be reached, the gate says
# so and exits cleanly rather than failing a build over a network blip. A gate
# that goes red when GitHub is slow is a gate people learn to ignore.
#
# In QuantSmith's own repository there is no upstream, so this reports
# "not a consumer" and exits cleanly.
#
# Advisory by default; QF_STAGE_ENFORCE=1 makes findings blocking.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header upstream-drift "Upstream surface drift check"
cd "$QF_ROOT"

[ -f quantsmith.conf ] && . ./quantsmith.conf

if [ -z "${QF_UPSTREAM_REPO:-}" ] || [ -z "${QF_UPSTREAM_REF:-}" ]; then
  qf_info "No upstream pinned (QF_UPSTREAM_REPO / QF_UPSTREAM_REF unset); not a consumer repository, skipped."
  qf_stage_result upstream-drift
  exit $?
fi

surfaces="${QF_UPSTREAM_SURFACES:-hooks/stages instructions templates/spec}"
qf_info "Pinned to $QF_UPSTREAM_REF of $QF_UPSTREAM_REPO"

work=$(mktemp -d 2>/dev/null || echo "/tmp/qf-drift-$$")
trap 'rm -rf "$work"' EXIT INT TERM

# Shallow-fetch just the pinned ref. Quiet, and failure is informational.
if ! git clone --quiet --depth 1 --branch "$QF_UPSTREAM_REF" \
        "$QF_UPSTREAM_REPO" "$work/upstream" 2>/dev/null; then
  qf_info "Upstream not reachable at $QF_UPSTREAM_REF; drift not compared this run."
  qf_info "  (Offline or the ref does not exist. This is not a failure.)"
  qf_stage_result upstream-drift
  exit $?
fi

drifted=0
missing=0
compared=0

for surface in $surfaces; do
  if [ ! -e "$surface" ]; then
    qf_warn "Declared surface '$surface' is not present in this repo."
    missing=$((missing + 1))
    continue
  fi
  if [ ! -e "$work/upstream/$surface" ]; then
    qf_warn "Declared surface '$surface' does not exist upstream at $QF_UPSTREAM_REF."
    missing=$((missing + 1))
    continue
  fi

  if [ -d "$surface" ]; then
    for f in $(find "$surface" -type f | sort); do
      compared=$((compared + 1))
      up="$work/upstream/$f"
      if [ ! -f "$up" ]; then
        qf_warn "$f is local-only (absent upstream) -- fine if deliberate, a stale copy if not."
        drifted=$((drifted + 1))
      elif ! cmp -s "$f" "$up"; then
        qf_warn "$f differs from upstream $QF_UPSTREAM_REF."
        drifted=$((drifted + 1))
      fi
    done
  else
    compared=$((compared + 1))
    cmp -s "$surface" "$work/upstream/$surface" || {
      qf_warn "$surface differs from upstream $QF_UPSTREAM_REF."
      drifted=$((drifted + 1))
    }
  fi
done

if [ "$drifted" -eq 0 ] && [ "$missing" -eq 0 ]; then
  qf_info "$compared file(s) compared; no drift from $QF_UPSTREAM_REF."
else
  qf_info "$compared file(s) compared; $drifted drifted, $missing missing."
  qf_info "Tuned deliberately? Record it in docs/ownership.md so the next reader knows."
  qf_info "Meant to be current? ./scripts/sync-upstream.sh refreshes from the pin."
fi

qf_stage_result upstream-drift
