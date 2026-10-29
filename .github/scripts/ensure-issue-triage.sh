#!/usr/bin/env bash
# ensure-issue-triage.sh — give a bot-filed issue its theme and Theme: line.
#
# Usage: ensure-issue-triage.sh <owner/repo> <issue-number> <theme-label> \
#          <theme-outcome>
#
# Every open leaf issue needs exactly one `theme:` label (PAD-02-014) and a
# `Theme: <label> — <outcome>` line in its body (PAD-02-018). A workflow that
# files an issue sets both itself, right after `gh issue create`.
#
# It sets no parent (PAD-02-026). A fixed Epic number would need upkeep each
# time that Epic closes, is rethemed or split, or fills up, and a workflow
# cannot calve an Epic of its own. So the issue starts untriaged
# (PAD-01-007), and `theme-fit` lists it for a person to route to an Epic.
#
# Idempotent, and it never overrides a person: an issue that carries a
# different `theme:` label keeps its label and body. The line and the label
# are checked on their own, so a run on either the create or the update arm
# finishes whatever an earlier run left undone.
#
# Used by .github/actions/notify-failure and .github/workflows/demo-recordings.yml.
# Needs GH_TOKEN with issues:write.

set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: $0 <owner/repo> <issue-number> <theme-label> <theme-outcome>" >&2
  exit 2
fi
repo="$1"
num="$2"
theme="$3"
outcome="$4"

case "$theme" in
  theme:?*) ;;
  *)
    echo "::error::'$theme' is not a theme: label; issue #$num is unthemed." >&2
    exit 2 ;;
esac
if [ -z "$outcome" ]; then
  echo "::error::Empty theme outcome; issue #$num would get no Theme: line." >&2
  exit 2
fi

# shellcheck source=.github/scripts/retry.sh
source "$(dirname "${BASH_SOURCE[0]}")/retry.sh"

# shellcheck disable=SC2016  # GraphQL variables, not shell ones
issue=$(retry gh api graphql \
  -f owner="${repo%%/*}" \
  -f name="${repo##*/}" \
  -F number="$num" \
  -f query='query($owner: String!, $name: String!, $number: Int!) {
    repository(owner: $owner, name: $name) {
      issue(number: $number) {
        body
        labels(first: 100) { nodes { name } }
      }
    }
  }' \
  --jq '.data.repository.issue')
body=$(jq -r '.body // ""' <<< "$issue")
themes=$(jq -r '[.labels.nodes[].name | select(startswith("theme:"))] | join(",")' \
  <<< "$issue")

# Theme: line, then theme label (PAD-02-018, PAD-02-014). The line goes first
# and each is checked on its own, so a run that stopped between the two is
# finished by the next one.
if [ -n "$themes" ] && [ "$themes" != "$theme" ]; then
  # A person chose another theme: theirs stands.
  echo "Issue #$num already has theme '$themes'; leaving its theme alone"
  exit 0
fi
# One awk, not `grep | grep -q`: an early `-q` exit can SIGPIPE the first
# grep, and under pipefail that reads as "no line" and writes a second one.
# The label field must equal the theme, not merely contain it, so a line for
# a longer label that starts with this one is not taken for it.
if awk -v t="$theme" '$1 == "Theme:" && $2 == t { f = 1 } END { exit !f }' \
    <<< "$body"; then
  echo "Issue #$num already has a Theme: line for $theme"
else
  body_file=$(mktemp)
  trap 'rm -f "$body_file"' EXIT
  printf 'Theme: %s — %s\n\n%s\n' "$theme" "$outcome" "$body" > "$body_file"
  retry gh issue edit "$num" --repo "$repo" --body-file "$body_file"
  echo "Set issue #$num Theme: line"
fi
if [ -z "$themes" ]; then
  retry gh issue edit "$num" --repo "$repo" --add-label "$theme"
  echo "Set issue #$num theme: $theme"
fi
