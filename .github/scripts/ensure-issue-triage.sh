#!/usr/bin/env bash
# ensure-issue-triage.sh — give a bot-filed issue a theme and an Epic parent.
#
# Usage: ensure-issue-triage.sh <owner/repo> <issue-number> <theme-label> \
#          <theme-outcome> <epic-number> <epic-variable-name>
#
# Every open leaf issue needs exactly one `theme:` label (PAD-02-014), a
# `Theme: <label> — <outcome>` line in its body (PAD-02-018) and an Epic
# ancestor (PAD-01-007). A workflow that files an issue sets all three itself,
# right after `gh issue create`, so `theme-fit` stays clean.
#
# The parent Epic is passed in from a repository variable (named by
# <epic-variable-name>, e.g. CI_FAILURE_EPIC), so re-homing a bot's issues
# after the Epics are reshaped is a variable change, not a code change. The
# step fails loudly, after the theme is set, when the variable is unset or
# names anything but an open Epic that carries the theme and has room for
# another sub-issue (GitHub caps a parent at 100, closed ones included).
#
# Idempotent, and it never overrides a person: an issue that carries a
# different `theme:` label keeps its label, body and parent (or lack of one,
# since the bot's Epic carries the bot's theme), and an issue that already has
# a parent keeps it. Each part is checked on its own, so a run on either
# the create or the update arm finishes whatever an earlier run left undone.
#
# Used by .github/actions/notify-failure and .github/workflows/demo-recordings.yml.
# Needs GH_TOKEN with issues:write.

set -euo pipefail

if [ "$#" -ne 6 ]; then
  echo "usage: $0 <owner/repo> <issue-number> <theme-label> <theme-outcome>" \
    "<epic-number> <epic-variable-name>" >&2
  exit 2
fi
repo="$1"
num="$2"
theme="$3"
outcome="$4"
epic="$5"
epic_var="$6"
# The cap GitHub puts on one parent's sub-issues.
max_sub_issues=100

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
        id body parent { number }
        labels(first: 100) { nodes { name } }
      }
    }
  }' \
  --jq '.data.repository.issue')
issue_id=$(jq -r '.id' <<< "$issue")
body=$(jq -r '.body // ""' <<< "$issue")
parent=$(jq -r '.parent.number // ""' <<< "$issue")
themes=$(jq -r '[.labels.nodes[].name | select(startswith("theme:"))] | join(",")' \
  <<< "$issue")

# Theme: line, then theme label (PAD-02-018, PAD-02-014). The line goes first
# and each is checked on its own, so a run that stopped between the two is
# finished by the next one.
if [ -n "$themes" ] && [ "$themes" != "$theme" ]; then
  # A person chose another theme, so the bot's Epic, which carries the bot's
  # theme, is the wrong parent (PAD-02-017): leave the parent to them too.
  echo "Issue #$num already has theme '$themes'; leaving its theme and parent alone"
  exit 0
else
  # One awk, not `grep | grep -q`: an early `-q` exit can SIGPIPE the first
  # grep, and under pipefail that reads as "no line" and writes a second one.
  # The label field must equal the theme, not merely contain it, so a line
  # for a longer label that starts with this one is not taken for it.
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
fi

# Epic parent (PAD-01-007).
if [ -n "$parent" ]; then
  echo "Issue #$num already has parent #$parent"
  exit 0
fi
if ! [[ "$epic" =~ ^[1-9][0-9]*$ ]]; then
  echo "::error::Repository variable $epic_var is '$epic', not an Epic number;" \
    "issue #$num has no Epic parent. Set it under Settings > Secrets and" \
    "variables > Actions > Variables." >&2
  exit 1
fi
# shellcheck disable=SC2016  # GraphQL variables, not shell ones
if ! epic_info=$(retry gh api graphql \
  -f owner="${repo%%/*}" \
  -f name="${repo##*/}" \
  -F number="$epic" \
  -f query='query($owner: String!, $name: String!, $number: Int!) {
    repository(owner: $owner, name: $name) {
      issue(number: $number) {
        id state issueType { name } subIssues { totalCount }
        labels(first: 100) { nodes { name } }
      }
    }
  }' \
  --jq '.data.repository.issue | .id, .state, (.issueType.name // ""),
    .subIssues.totalCount, ([.labels.nodes[].name] | join(","))'); then
  # A number naming no issue, or a pull request, errors here; say which
  # variable to fix rather than leave only retry's generic error.
  echo "::error::Could not read Epic #$epic (repository variable $epic_var);" \
    "issue #$num has no Epic parent." >&2
  exit 1
fi
mapfile -t epic_fields <<< "$epic_info"
if [ "${epic_fields[1]:-}" != "OPEN" ] || [ "${epic_fields[2]:-}" != "Epic" ]; then
  echo "::error::#$epic (repository variable $epic_var) is not an open Epic;" \
    "issue #$num has no Epic parent." >&2
  exit 1
fi
if ! [[ ",${epic_fields[4]:-}," == *",$theme,"* ]]; then
  echo "::error::Epic #$epic (repository variable $epic_var) does not carry" \
    "$theme, so its sub-issue would break PAD-02-017; issue #$num has no" \
    "Epic parent." >&2
  exit 1
fi
if [ "${epic_fields[3]:-0}" -ge "$max_sub_issues" ]; then
  echo "::error::Epic #$epic (repository variable $epic_var) already has" \
    "$max_sub_issues sub-issues, GitHub's cap; point $epic_var at another" \
    "Epic. Issue #$num has no Epic parent." >&2
  exit 1
fi

# Not retried: a call that landed but reported an error would fail again as
# "already a sub-issue", and the next run finds the parent set anyway.
# shellcheck disable=SC2016  # GraphQL variables, not shell ones
gh api graphql \
  -f parentId="${epic_fields[0]}" \
  -f childId="$issue_id" \
  -f query='mutation($parentId: ID!, $childId: ID!) {
    addSubIssue(input: {issueId: $parentId, subIssueId: $childId}) {
      subIssue { number parent { number } }
    }
  }' --jq '"Set issue #\(.data.addSubIssue.subIssue.number) parent: #\(.data.addSubIssue.subIssue.parent.number)"'
