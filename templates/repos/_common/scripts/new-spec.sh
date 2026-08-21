#!/bin/sh
# Create the next spec directory from the template.
#   ./scripts/new-spec.sh my-feature-slug
set -e
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
slug="$1"
[ -n "$slug" ] || { echo "usage: $0 <short-kebab-slug>"; exit 1; }

next=$(ls -d specs/[0-9]*/ 2>/dev/null | sed 's|specs/||;s|-.*||' | sort -n | tail -1)
next=$(printf '%04d' $(( ${next:-0} + 1 )))
dir="specs/$next-$slug"

[ -d templates/spec ] || { echo "templates/spec/ missing."; exit 1; }
mkdir -p "$dir"
cp templates/spec/*.md "$dir"/
echo "Created $dir"
echo "Next: fill in spec.md, then add its entry to docs/roadmap.md"
echo "      (the handoff-sync gate blocks the commit until you do)."
