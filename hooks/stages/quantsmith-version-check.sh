#!/bin/sh
# Repo gate - QuantSmith consumer pin check.
#
# For a repository that CONSUMES QuantSmith (an app, a service, an adopting
# quant repo), checks that its declared `quantsmith` dependency is pinned and
# matches the installed package. A floating dependency on a package whose
# DashboardSpec contract a client renders is itself a finding -- see spec
# 0047. Copy this gate into a consuming repository.
#
# Offline and deterministic by design: it compares against the INSTALLED
# package, never a remote index, so the gate cannot become flaky or
# network-dependent. The consequence, recorded honestly in spec 0047 as
# RISK-004, is that a repository which reads only rendered artifacts and never
# installs the package gets no signal here -- for that consumer the guard is
# `schema_version` on the payload itself.
#
# In QuantSmith's own repository there is no such dependency, so this reports
# "not a consumer" and exits cleanly.
#
# Advisory by default; set QF_STAGE_ENFORCE=1 to block.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header quantsmith-version "QuantSmith consumer pin check"
cd "$QF_ROOT"

# Collect declared dependencies on quantsmith from the usual places.
declared=""
for f in requirements.txt requirements-dev.txt pyproject.toml; do
  [ -f "$f" ] || continue
  # A dependency line, not a self-referential name/package declaration.
  line=$(grep -iE '(^|["'"'"' ])quantsmith[><=~!]' "$f" 2>/dev/null | head -1 || true)
  if [ -n "$line" ]; then
    declared="$f:$line"
    break
  fi
  # An unpinned mention in a dependency array, e.g. "quantsmith",
  if grep -iqE '^[[:space:]]*["'"'"']quantsmith["'"'"'][[:space:]]*,?[[:space:]]*$' "$f" 2>/dev/null; then
    declared="$f:quantsmith (no version specifier)"
    break
  fi
done

if [ -z "$declared" ]; then
  qf_info "No 'quantsmith' dependency declared; not a consumer repository, skipped."
  qf_stage_result quantsmith-version
  exit $?
fi

file=${declared%%:*}
spec_line=${declared#*:}
qf_info "Declared in $file: $(printf '%s' "$spec_line" | sed 's/^[[:space:]]*//')"

# A floating dependency on a contract-bearing package.
if ! printf '%s' "$spec_line" | grep -q '=='; then
  qf_warn "$file: 'quantsmith' is not pinned with '=='; a client rendering its DashboardSpec should pin the contract it was built against."
  qf_stage_result quantsmith-version
  exit $?
fi

pinned=$(printf '%s' "$spec_line" | sed -n 's/.*==[[:space:]]*\([0-9][0-9.]*\).*/\1/p')
if [ -z "$pinned" ]; then
  qf_warn "$file: could not read a version from the 'quantsmith' pin."
  qf_stage_result quantsmith-version
  exit $?
fi

installed=$(python3 -c 'import quantsmith; print(quantsmith.__version__)' 2>/dev/null || true)
if [ -z "$installed" ]; then
  qf_info "quantsmith is not importable here; pin $pinned not compared."
elif [ "$pinned" != "$installed" ]; then
  qf_warn "Pin drift: $file pins quantsmith==$pinned but $installed is installed."
else
  qf_info "Pin matches the installed package ($installed)."
fi

qf_stage_result quantsmith-version
