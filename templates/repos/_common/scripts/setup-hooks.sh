#!/bin/sh
# Wire local Git hooks. Run once after cloning.
set -e
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
[ -d .githooks ] || { echo "No .githooks directory."; exit 1; }
chmod +x .githooks/*
git config core.hooksPath .githooks
echo "Git hooks enabled (core.hooksPath=.githooks)."
