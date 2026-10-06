#!/bin/sh
# Stage 6 - Maintenance & Monitoring gate.
#
# Checks that live systems keep their operational docs current: monitoring and
# runbook references, and that model/dataset cards have not gone stale relative
# to changed code. Advisory by default.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header maintenance "Monitoring & doc-freshness check"
cd "$QF_ROOT"

# Monitoring / runbook references.
if grep -riq -e "monitoring" -e "runbook" -e "alert" . --include="*.md" 2>/dev/null; then
  qf_info "Monitoring / runbook documentation referenced."
else
  qf_warn "No monitoring or runbook documentation found (see agents/maintenance_monitoring)."
fi

# If model/pipeline code changed, expect a matching card to be touched too.
changed=$(qf_changed_files)
model_changed=0
card_changed=0
for f in $changed; do
  case "$f" in
    # A test file is not model code, whatever it is named (tests/test_model_*.py tests models; it is not one).
    tests/*|*/tests/*|test_*.py|*/test_*.py|*_test.py) ;;
    *model*.py|*models/*|*pipeline*.py|*pipelines/*|*feature*.py) model_changed=1 ;;
    *model_card*.md|*dataset_card*.md|*runbook*.md) card_changed=1 ;;
  esac
done

if [ "$model_changed" -eq 1 ] && [ "$card_changed" -eq 0 ]; then
  qf_warn "Model/pipeline code changed but no model/dataset card or runbook updated."
elif [ "$model_changed" -eq 1 ]; then
  qf_info "Model/pipeline change accompanied by a doc update."
fi

qf_stage_result maintenance
