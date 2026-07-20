#!/usr/bin/env bash
# Query leaf sub-issues of an Epic for candidate selection.
# Usage: query-epic-subissues.sh <EPIC_NUMBER>
set -euo pipefail

EPIC_NUMBER="${1:?Usage: $0 <EPIC_NUMBER>}"

gh api graphql -f query="{
  repository(owner:\"CERTCC\", name:\"Vultron\") {
    issue(number: ${EPIC_NUMBER}) {
      subIssues(first: 50) {
        nodes {
          number title state
          assignees(first: 1) { nodes { login } }
          blockedBy(first: 10) { nodes { number title state } }
          subIssues(first: 1) { totalCount }
          labels(first: 10) { nodes { name } }
        }
      }
    }
  }
}"
