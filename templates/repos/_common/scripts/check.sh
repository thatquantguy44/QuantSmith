#!/bin/sh
# Run everything CI runs, locally, in the same order. One command before a PR.
set -e
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
. ./quantsmith.conf

echo "== shell syntax =="
for f in hooks/stages/*.sh scripts/*.sh .githooks/*; do [ -f "$f" ] && sh -n "$f"; done

echo "== blocking gates =="
QF_STAGE_ENFORCE=1 sh hooks/stages/run-stage.sh $QF_GATES_BLOCKING

echo "== advisory gates =="
sh hooks/stages/run-stage.sh $QF_GATES_ADVISORY || true

echo "== tests =="
pytest -q
