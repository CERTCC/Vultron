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
# after the Epics are reshaped is a variable change, not a code change. An
# unset variable, or a number that is not an open Epic, fails the step loudly
# after the issue is filed, rather than leaving it silently unparented.
#
# Idempotent, and it never overrides a person: an issue that already carries a
# `theme:` label keeps its label and body, and an issue that already has a
# parent keeps it. Run on both the create and the update arm, it also repairs an
# issue an earlier run left without them.
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

# shellcheck disable=SC2016  # GraphQL variables, not shell ones
issue=$(gh api graphql \
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

# Theme label and Theme: line (PAD-02-014, PAD-02-018).
if [ -n "$themes" ]; then
  echo "Issue #$num already has theme '$themes'"
else
  gh issue edit "$num" --repo "$repo" --add-label "$theme"
  line="Theme: $theme — $outcome"
  if grep -qxF "$line" <<< "$body"; then
    echo "Issue #$num already has its Theme: line"
  else
    printf '%s\n\n%s\n' "$line" "$body" \
      | gh issue edit "$num" --repo "$repo" --body-file -
  fi
  echo "Set issue #$num theme: $theme"
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
# A command substitution, not `mapfile < <(...)`, so a failed lookup fails the
# step under `set -e` instead of reading as "not an Epic".
epic_info=$(gh issue view "$epic" \
  --repo "$repo" --json id,state,issueType \
  --jq '.id, .state, (.issueType.name // "")')
mapfile -t epic_fields <<< "$epic_info"
if [ "${epic_fields[1]:-}" != "OPEN" ] || [ "${epic_fields[2]:-}" != "Epic" ]; then
  echo "::error::#$epic (repository variable $epic_var) is not an open Epic;" \
    "issue #$num has no Epic parent." >&2
  exit 1
fi

# shellcheck disable=SC2016  # GraphQL variables, not shell ones
gh api graphql \
  -f parentId="${epic_fields[0]}" \
  -f childId="$issue_id" \
  -f query='mutation($parentId: ID!, $childId: ID!) {
    addSubIssue(input: {issueId: $parentId, subIssueId: $childId}) {
      subIssue { number parent { number } }
    }
  }' --jq '"Set issue #\(.data.addSubIssue.subIssue.number) parent: #\(.data.addSubIssue.subIssue.parent.number)"'
