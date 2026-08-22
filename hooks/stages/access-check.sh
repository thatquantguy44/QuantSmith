#!/bin/sh
# Access gate - viewer access roster structure & safety check.
#
# Validates access/roster.yml (spec 0058-viewer-access-control): parses,
# flags duplicate handles, unrecognized clearance levels, and email/free-text
# -shaped handles, and runs the same secret/PII safety scan memory-check.sh
# already runs under memory/, applied to access/ (access is metadata about
# who sees what, same "no PII" posture as memory itself). Deliberately
# shell-only, no Python dependency: this gate must run in a copied scaffold
# that may not even carry this repo's Python package. Advisory by default;
# QF_STAGE_ENFORCE=1 blocks.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header access "Viewer access roster structure & safety check"
cd "$QF_ROOT"

if [ ! -d access ]; then
  qf_info "No access/ directory; per-person access checks skipped."
  qf_stage_result access
  exit $?
fi

ROSTER=access/roster.yml

if [ ! -f "$ROSTER" ]; then
  qf_info "No access/roster.yml; per-person access checks skipped."
else
  # Structural checks: parse the roster's flat handle/label/clearance shape
  # (comments stripped first -- '#' to end of line, mirroring
  # access_control.py's own _strip_comment, minus quote-awareness -- this is
  # a heuristic shell gate, not the parser of record).
  tmpfile=$(mktemp) || tmpfile=""
  if [ -z "$tmpfile" ]; then
    qf_warn "$ROSTER: could not create a temp file to parse it"
  else
    trap 'rm -f "$tmpfile"' EXIT
    sed 's/#.*//' "$ROSTER" | awk '
      function trim(s) {
        gsub(/^[ \t]+|[ \t]+$/, "", s)
        gsub(/^["'"'"']|["'"'"']$/, "", s)
        return s
      }
      /^[[:space:]]*-[[:space:]]*handle:/ {
        if (h != "") print h "\t" c
        line = $0
        sub(/^[[:space:]]*-[[:space:]]*handle:[[:space:]]*/, "", line)
        h = trim(line)
        c = ""
        next
      }
      /^[[:space:]]*clearance:/ {
        line = $0
        sub(/^[[:space:]]*clearance:[[:space:]]*/, "", line)
        c = trim(line)
        next
      }
      END { if (h != "") print h "\t" c }
    ' > "$tmpfile"

    if [ -s "$tmpfile" ]; then
      while IFS="$(printf '\t')" read -r handle clearance; do
        [ -n "$handle" ] || continue
        case "$clearance" in
          public | internal | restricted) ;;
          *) qf_warn "$ROSTER: entry '$handle' has unrecognized clearance '$clearance'" ;;
        esac
        case "$handle" in
          *@*) qf_warn "$ROSTER: handle '$handle' looks like an email address, not a pseudonymous handle" ;;
          *[!a-z0-9._-]*) qf_warn "$ROSTER: handle '$handle' contains characters outside a-z0-9._- (not a valid pseudonymous handle)" ;;
        esac
      done < "$tmpfile"

      dupes=$(cut -f1 "$tmpfile" | sort | uniq -d)
      if [ -n "$dupes" ]; then
        for d in $dupes; do
          qf_warn "$ROSTER: duplicate handle '$d'"
        done
      fi
    else
      qf_info "access/roster.yml has no entries; enforcement is inactive."
    fi
  fi
fi

# Safety scan: access/ is metadata about who sees what -- no secrets,
# connection strings, or PII, same rule memory-check.sh already applies to
# memory/. Runs on raw file content (comments included), so an email hidden
# in a comment is caught the same way one under memory/ would be.
CONN_RE='[A-Za-z][A-Za-z0-9+.-]*://[^:@/[:space:]]+:[^@/[:space:]]+@'
CRED_RE='(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)["'"'"' ]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9/+_-]{8,}'
KEY_RE='-----BEGIN [A-Z ]*PRIVATE KEY-----'
EMAIL_RE='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
SSN_RE='[0-9]{3}-[0-9]{2}-[0-9]{4}'

for f in $(find access -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.yml' -o -name '*.txt' \) 2>/dev/null); do
  grep -Eq "$CONN_RE" "$f" 2>/dev/null && qf_warn "$f: possible connection string with credentials in access/"
  grep -Eiq "$CRED_RE" "$f" 2>/dev/null && qf_warn "$f: possible credential value in access/"
  grep -Eq "$KEY_RE" "$f" 2>/dev/null && qf_warn "$f: private key in access/"
  grep -Eq "$EMAIL_RE" "$f" 2>/dev/null && qf_warn "$f: possible PII (email) in access/"
  grep -Eq "$SSN_RE" "$f" 2>/dev/null && qf_warn "$f: possible PII (SSN-like) in access/"
done

[ "$QF_FINDINGS" -eq 0 ] && qf_info "Access roster structure and safety OK."
qf_stage_result access
