#!/bin/sh
# Refresh copied upstream surfaces to the pinned ref.
#
#   ./scripts/sync-upstream.sh            # show what would change
#   ./scripts/sync-upstream.sh --apply    # actually overwrite
#   ./scripts/sync-upstream.sh --to v0.3.0 --apply
#
# The other half of `upstream-drift-check.sh`. The gate tells you a copied file
# has diverged from the pin; this brings it back, or moves the pin forward.
#
# Dry-run by default and deliberately so. Adopters are EXPECTED to tune gates
# to their repo -- docs/adoption_guide.md says the patterns are yours to own --
# so a sync that silently overwrote local tuning would destroy the thing the
# model is built around. You see the diff, then you decide.
#
# Reads from quantsmith.conf:
#   QF_UPSTREAM_REPO     git URL or local path
#   QF_UPSTREAM_REF      the pinned tag/commit
#   QF_UPSTREAM_SURFACES space-separated paths to keep in sync

set -e
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
[ -f quantsmith.conf ] || { echo "No quantsmith.conf at the repo root."; exit 1; }
. ./quantsmith.conf

apply=0
ref="${QF_UPSTREAM_REF:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) apply=1; shift ;;
    --to)    ref="$2"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "${QF_UPSTREAM_REPO:-}" ] || { echo "QF_UPSTREAM_REPO is not set in quantsmith.conf."; exit 1; }
[ -n "$ref" ] || { echo "No ref: set QF_UPSTREAM_REF or pass --to <ref>."; exit 1; }

surfaces="${QF_UPSTREAM_SURFACES:-hooks/stages instructions templates/spec}"

work=$(mktemp -d); trap 'rm -rf "$work"' EXIT INT TERM
echo "Fetching $QF_UPSTREAM_REPO @ $ref ..."
git clone --quiet --depth 1 --branch "$ref" "$QF_UPSTREAM_REPO" "$work/up" || {
  echo "Could not fetch $ref from $QF_UPSTREAM_REPO." >&2; exit 1; }

changed=0
for surface in $surfaces; do
  [ -e "$work/up/$surface" ] || { echo "  skip $surface (absent upstream)"; continue; }
  if [ "$apply" -eq 1 ]; then
    mkdir -p "$(dirname "$surface")"
    rm -rf "$surface"
    cp -R "$work/up/$surface" "$surface"
    echo "  synced $surface"
    changed=$((changed + 1))
  else
    if diff -rq "$surface" "$work/up/$surface" >/dev/null 2>&1; then
      echo "  ok     $surface"
    else
      echo "  DIFF   $surface"
      diff -ru "$surface" "$work/up/$surface" 2>/dev/null | head -40 || true
      changed=$((changed + 1))
    fi
  fi
done

if [ "$apply" -eq 1 ]; then
  if [ "$ref" != "${QF_UPSTREAM_REF:-}" ]; then
    sed -i.bak "s|^QF_UPSTREAM_REF=.*|QF_UPSTREAM_REF=\"$ref\"|" quantsmith.conf
    rm -f quantsmith.conf.bak
    echo
    echo "Pin moved to $ref in quantsmith.conf."
  fi
  echo
  echo "$changed surface(s) synced. Review the diff, run ./scripts/check.sh, then commit."
else
  echo
  if [ "$changed" -eq 0 ]; then
    echo "In sync with $ref. Nothing to do."
  else
    echo "$changed surface(s) differ. Re-run with --apply to overwrite local copies."
    echo "If the local version is deliberate, record why in docs/ownership.md."
  fi
fi
