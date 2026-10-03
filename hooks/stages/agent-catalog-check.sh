#!/bin/sh
# Docs gate - Agent catalog sync check.
#
# Verifies every public agent (a directory containing prompt.md) is listed in the
# agent catalog, agents/README.md, and in the generated agents/agent_registry.yaml. Keeps the catalog from drifting as agents are
# added. Advisory by default; set QF_STAGE_ENFORCE=1 to block.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header agent-catalog "Agent catalog sync check"
cd "$QF_ROOT"

catalog="agents/README.md"
if [ ! -f "$catalog" ]; then
  qf_warn "Agent catalog missing: $catalog"
  qf_stage_result agent-catalog
  exit $?
fi

count=0
for agent in $(find agents -type f -name prompt.md -exec dirname {} \; | sort -u); do
  count=$((count + 1))
  rel=${agent#agents/}        # e.g. risk or data_ingestion/database_connectivity
  # The catalog references agents by their path under agents/ with a trailing slash.
  if ! grep -qF "$rel/" "$catalog" 2>/dev/null; then
    qf_warn "Agent not listed in $catalog: $rel/"
  fi
  # The machine-readable registry is generated; a missing entry means it is stale.
  if [ -f agents/agent_registry.yaml ] && ! grep -qF "  - name: \"$rel\"" agents/agent_registry.yaml 2>/dev/null; then
    qf_warn "Agent not in agents/agent_registry.yaml: $rel (run: python3 scripts/build_agent_registry.py)"
  fi
done

qf_info "Checked $count agent(s) against the catalog."
qf_stage_result agent-catalog
