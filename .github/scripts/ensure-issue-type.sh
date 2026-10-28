#!/usr/bin/env bash
# ensure-issue-type.sh — give an issue an issue type, unless it already has one.
#
# Usage: ensure-issue-type.sh <owner/repo> <issue-number> <type-name>
#
# `gh issue create` cannot set an issue type, and a label applied with
# GITHUB_TOKEN never fires label-to-issue-type.yml, so a bot that files an
# issue sets the type itself (CISEC-05-007). The type ID is resolved by name,
# so it survives a type being re-created. Idempotent: an issue that already
# carries a type is left alone, which also repairs an issue an earlier failed
# assignment left untyped. A repository with no type of that name fails loudly
# rather than leaving the issue silently untyped.
#
# Used by .github/actions/notify-failure (Bug) and
# .github/workflows/demo-recordings.yml (Task). Needs GH_TOKEN.

set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <owner/repo> <issue-number> <type-name>" >&2
  exit 2
fi
repo="$1"
num="$2"
type_name="$3"

# `issueTypes` is null when the owner has no issue types at all (user-owned
# forks); `// []` keeps jq from aborting before the error below names the issue.
# shellcheck disable=SC2016  # GraphQL variables, not shell ones
types=$(gh api graphql \
  -f owner="${repo%%/*}" \
  -f name="${repo##*/}" \
  -f query='query($owner: String!, $name: String!) {
    repository(owner: $owner, name: $name) {
      issueTypes(first: 100) { nodes { id name } }
    }
  }' \
  --jq '(.data.repository.issueTypes.nodes // [])[] | [.name, .id] | @tsv')
# Matched in the shell, not in jq, so the name is compared as plain text.
type_id=$(awk -F '\t' -v want="$type_name" '$1 == want { print $2; exit }' <<< "$types")
if [ -z "$type_id" ]; then
  echo "::error::No '$type_name' issue type found in $repo; issue #$num is untyped." >&2
  exit 1
fi

mapfile -t issue_fields < <(gh issue view "$num" \
  --repo "$repo" --json id,issueType \
  --jq '.id, (.issueType.name // "")')
issue_node_id="${issue_fields[0]}"
current_type="${issue_fields[1]:-}"
if [ -n "$current_type" ]; then
  echo "Issue #$num already has type '$current_type'"
  exit 0
fi

# shellcheck disable=SC2016  # GraphQL variables, not shell ones
gh api graphql \
  -f id="$issue_node_id" \
  -f typeId="$type_id" \
  -f query='mutation($id: ID!, $typeId: ID!) {
    updateIssue(input: {id: $id, issueTypeId: $typeId}) {
      issue { number issueType { name } }
    }
  }' --jq '"Set issue #\(.data.updateIssue.issue.number) type: \(.data.updateIssue.issue.issueType.name)"'
