#!/usr/bin/env bash
# query-now-epics.sh — list open Epics with Schedule=Now from Project #24.
# Output: one line per epic in the format "#N: <title>", ordered by board position.
# Usage: bash .agents/skills/shared/query-now-epics.sh
set -euo pipefail

gh api graphql --jq '
  .data.node.items.nodes[]
  | select(
      .content.state == "OPEN" and
      .content.issueType.name == "Epic" and
      (
        .fieldValues.nodes[]
        | select(.field.name == "Schedule")
        | .name
      ) == "Now"
    )
  | "#\(.content.number): \(.content.title)"
' -f query='{
  node(id: "PVT_kwDOAjf0s84BZnre") {
    ... on ProjectV2 {
      items(first: 100) {
        nodes {
          content {
            ... on Issue {
              number title state
              issueType { name }
            }
          }
          fieldValues(first: 10) { nodes {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name field { ... on ProjectV2SingleSelectField { name } }
            }
          }}
        }
      }
    }
  }
}'
