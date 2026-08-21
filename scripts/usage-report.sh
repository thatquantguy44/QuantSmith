#!/bin/sh
# Summarize the gate usage log.
#
#   QF_USAGE_LOG=.qf-usage.tsv sh hooks/stages/run-stage.sh   # collect
#   ./scripts/usage-report.sh .qf-usage.tsv                   # read
#
# Answers the questions nobody can answer today: which gates ever fire, which
# never do, which are worth promoting from advisory to blocking, and which are
# pure overhead. Investment in this system currently follows intuition; this is
# the cheapest way to make it follow evidence.
#
# The log holds timestamp, gate, finding count, enforce flag -- and nothing
# else. No paths, no finding text, no identity. It is local and gitignored.

set -e
log="${1:-${QF_USAGE_LOG:-.qf-usage.tsv}}"
[ -f "$log" ] || { echo "No usage log at $log."; echo; sed -n '4,6p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

runs=$(wc -l < "$log" | tr -d ' ')
gates=$(cut -f2 "$log" | sort -u | wc -l | tr -d ' ')
first=$(head -1 "$log" | cut -f1)
last=$(tail -1 "$log" | cut -f1)

printf 'Gate usage: %s records across %s gate(s)\n' "$runs" "$gates"
printf '  %s  ->  %s\n\n' "$first" "$last"

printf '%-22s %6s %8s %9s\n' "GATE" "RUNS" "FINDINGS" "FIRE-RATE"
printf '%-22s %6s %8s %9s\n' "----" "----" "--------" "---------"
cut -f2,3 "$log" | sort | awk -F'\t' '
  { runs[$1]++; if ($2+0 > 0) fired[$1]++; total[$1]+=$2 }
  END { for (g in runs)
          printf "%-22s %6d %8d %8.0f%%\n", g, runs[g], total[g],
                 (fired[g]/runs[g])*100 }
' | sort -k4 -rn

echo
echo "Reading this:"
echo "  fire-rate 0%    never found anything here -- either the repo is clean"
echo "                  or the gate does not apply. Check which before removing."
echo "  fire-rate 100%  fires every run -- likely a known unfixed finding that"
echo "                  people have learned to ignore. Fix it or drop the gate."
echo "  high runs, 0%   pure overhead in this repo; a candidate to drop from"
echo "                  QF_GATES_ADVISORY so the signal stays readable."
