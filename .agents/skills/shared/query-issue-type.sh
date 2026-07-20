#!/usr/bin/env bash
# Query issue type and sub-issue count for the Empty-Epic gate.
# Usage: query-issue-type.sh <ISSUE_NUMBER>
set -euo pipefail

ISSUE_NUMBER="${1:?Usage: $0 <ISSUE_NUMBER>}"

gh api graphql -f query="{
  repository(owner:\"CERTCC\", name:\"Vultron\") {
    issue(number: ${ISSUE_NUMBER}) {
      issueType { name }
      subIssues(first: 1) { totalCount }
      labels(first: 20) { nodes { name } }
    }
  }
}"
