#!/usr/bin/env bash
# Query issue type and sub-issue count for the Empty-Epic gate.
# Usage: query-issue-type.sh [--name] <ISSUE_NUMBER>
#   --name  print only the issue type's name (empty for an untyped issue)
set -euo pipefail

NAME_ONLY=false
if [ "${1:-}" = "--name" ]; then
  NAME_ONLY=true
  shift
fi
ISSUE_NUMBER="${1:?Usage: $0 [--name] <ISSUE_NUMBER>}"

if [ "$NAME_ONLY" = true ]; then
  JQ='.data.repository.issue.issueType.name // ""'
else
  JQ='.'
fi

gh api graphql --jq "$JQ" -f query="{
  repository(owner:\"CERTCC\", name:\"Vultron\") {
    issue(number: ${ISSUE_NUMBER}) {
      issueType { name }
      subIssues(first: 1) { totalCount }
      labels(first: 20) { nodes { name } }
    }
  }
}"
