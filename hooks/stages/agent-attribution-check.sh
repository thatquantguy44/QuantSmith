#!/bin/sh
# Repo gate - Agent attribution check.
#
# Rejects commits authored by an AI coding agent, and commit messages carrying
# an AI co-author trailer. The repository's commits should be attributed to the
# human accountable for them; an agent identity in `git log` makes authorship
# ambiguous, and the constitution's honest-reporting principle cuts both ways --
# work is attributed to whoever answers for it.
#
# Three layers, because each catches what the others cannot:
#   - .githooks/pre-commit  checks the identity the NEXT commit will carry,
#                           before it exists (the only place to stop it cheaply)
#   - .githooks/commit-msg  checks the message for co-author trailers
#   - .githooks/pre-push    checks the range actually being pushed
#   - CI                    the real backstop: local hooks need setup-hooks.sh
#                           and are bypassable with --no-verify
#
# Scope of the range check:
#   QF_ATTRIB_RANGE=<range>   explicit git range (CI/pre-push pass this)
#   otherwise                 commits on HEAD not on origin/main
#
# Advisory by default; QF_STAGE_ENFORCE=1 makes findings blocking.

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/common.sh"

qf_stage_header agent-attribution "Agent attribution check"
cd "$QF_ROOT"

# Identities that must never author a commit here. Matched case-insensitively
# against the author/committer "Name <email>" string.
#
# Deliberately specific: 'github-actions[bot]' and 'dependabot[bot]' are NOT
# listed. They are honest machine identities for machine-generated changes,
# which is a different thing from an agent writing code on a human's behalf.
AGENT_IDENTITY_RE='(^|[^a-z])claude([^a-z]|$)|anthropic\.com|(^|[^a-z])codex([^a-z]|$)|openai\.com|chatgpt|\[bot\]@users\.noreply\.github\.com.*copilot|copilot\[bot\]'

# Trailers and sign-offs that attribute authorship to an agent.
AGENT_TRAILER_RE='^[[:space:]]*Co-[Aa]uthored-[Bb]y:.*(Claude|Codex|ChatGPT|Copilot|anthropic\.com|openai\.com)|^[[:space:]]*(Claude|Codex)-Session:|Generated with \[(Claude Code|Codex)\]'

# --- 1. The identity the next commit would carry -----------------------------
# Only meaningful when a commit is imminent (pre-commit); harmless otherwise.
if [ "${QF_ATTRIB_CHECK_IDENTITY:-0}" = "1" ]; then
  who="$(git config user.name || true) <$(git config user.email || true)>"
  if printf '%s' "$who" | grep -qiE "$AGENT_IDENTITY_RE"; then
    qf_warn "Configured git identity is an AI agent: $who"
    qf_warn "  Set a human identity before committing, e.g.:"
    qf_warn "    git config user.name  'Your Name'"
    qf_warn "    git config user.email 'you@users.noreply.github.com'"
  else
    qf_info "Configured git identity: $who"
  fi
fi

# --- 2. Commits in range -----------------------------------------------------
range="${QF_ATTRIB_RANGE:-}"
if [ -z "$range" ]; then
  if git rev-parse --verify -q origin/main >/dev/null 2>&1; then
    range="origin/main..HEAD"
  else
    range="HEAD~20..HEAD"
  fi
fi

# An empty or invalid range is not a failure -- a fresh branch legitimately has
# nothing to check, and the gate must stay silent rather than inventing work.
if ! git rev-list "$range" >/dev/null 2>&1; then
  qf_info "No comparable range ($range); commit scan skipped."
  qf_stage_result agent-attribution
  exit $?
fi

count=0
flagged=0
for sha in $(git rev-list "$range" 2>/dev/null); do
  count=$((count + 1))
  who=$(git log -1 --format='%an <%ae>' "$sha")
  cwho=$(git log -1 --format='%cn <%ce>' "$sha")
  short=$(git log -1 --format='%h %s' "$sha" | cut -c1-60)

  if printf '%s' "$who" | grep -qiE "$AGENT_IDENTITY_RE"; then
    qf_warn "$short"
    qf_warn "  author is an AI agent: $who"
    flagged=$((flagged + 1))
  fi
  if printf '%s' "$cwho" | grep -qiE "$AGENT_IDENTITY_RE"; then
    qf_warn "$short"
    qf_warn "  committer is an AI agent: $cwho"
    flagged=$((flagged + 1))
  fi
  if git log -1 --format='%B' "$sha" | grep -qE "$AGENT_TRAILER_RE"; then
    qf_warn "$short"
    qf_warn "  message carries an AI co-author trailer"
    flagged=$((flagged + 1))
  fi
done

if [ "$flagged" -eq 0 ]; then
  qf_info "Scanned $count commit(s) in $range; no agent attribution found."
else
  qf_warn "To rewrite authorship on a range, see .github/GIT_GUIDELINES.md."
fi

qf_stage_result agent-attribution
