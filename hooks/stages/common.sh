#!/bin/sh
# Shared helpers for QuantSmith stage hooks.
#
# Stage hooks are advisory by default: they print findings and exit 0 so they
# never block exploratory work. Set QF_STAGE_ENFORCE=1 to make findings blocking
# (exit non-zero), for use in CI or as a strict local gate.

# Resolve repo root when run from anywhere inside a checkout.
if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
  QF_ROOT=$(git rev-parse --show-toplevel)
else
  QF_ROOT=$(pwd)
fi

QF_FINDINGS=0

qf_info() {
  printf '  - %s\n' "$1"
}

qf_warn() {
  printf '  ! %s\n' "$1"
  QF_FINDINGS=$((QF_FINDINGS + 1))
}

qf_stage_header() {
  printf '\n[qf:%s] %s\n' "$1" "$2"
}

# Return 0 if any of the given glob patterns matches at least one existing path.
# Each pattern is expanded independently, so a non-matching pattern does not
# mask a matching one (unlike `ls a* b*`, which fails if any glob is empty).
qf_glob_exists() {
  for _qf_pattern in "$@"; do
    for _qf_match in $_qf_pattern; do
      [ -e "$_qf_match" ] && return 0
    done
  done
  return 1
}

# Files changed against a base ref, falling back to the working-tree diff and
# then to staged files. Prints one path per line.
qf_changed_files() {
  base="${QF_DIFF_BASE:-}"
  if [ -n "$base" ] && git rev-parse --verify "$base" >/dev/null 2>&1; then
    git diff --name-only --diff-filter=ACMR "$base"...HEAD 2>/dev/null
    return
  fi
  # Union of unstaged and staged changes, deduplicated — a staged file must not be
  # hidden just because some other file also has unstaged edits.
  {
    git diff --name-only --diff-filter=ACMR 2>/dev/null
    git diff --name-only --cached --diff-filter=ACMR 2>/dev/null
  } | sort -u
}

# Exit according to mode. Advisory (default) always exits 0.
# Append one line of usage telemetry, if the repo opted in.
#
# OFF unless QF_USAGE_LOG names a path. It never phones home, never leaves the
# machine, and records only: timestamp, gate, finding count, enforce mode. No
# file paths, no finding text, no identity -- a usage log that carried findings
# would carry company data, and this must stay safe to enable anywhere.
#
# The point is to answer questions nobody can answer today: which gates ever
# fire, which never do, which are worth promoting to blocking. Investment in
# this system currently follows intuition; this is the cheapest way to make it
# follow evidence.
qf_usage_record() {
  [ -n "${QF_USAGE_LOG:-}" ] || return 0
  dir=$(dirname "$QF_USAGE_LOG")
  [ -d "$dir" ] || mkdir -p "$dir" 2>/dev/null || return 0
  printf '%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "${QF_STAGE_ENFORCE:-0}" \
    >> "$QF_USAGE_LOG" 2>/dev/null || true
}

qf_stage_result() {
  stage="$1"
  qf_usage_record "$stage" "$QF_FINDINGS"
  if [ "$QF_FINDINGS" -eq 0 ]; then
    printf '[qf:%s] no findings\n' "$stage"
    return 0
  fi
  printf '[qf:%s] %s finding(s)\n' "$stage" "$QF_FINDINGS"
  if [ "${QF_STAGE_ENFORCE:-0}" = "1" ]; then
    return 1
  fi
  printf '[qf:%s] advisory mode (set QF_STAGE_ENFORCE=1 to block)\n' "$stage"
  return 0
}
