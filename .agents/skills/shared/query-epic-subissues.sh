#!/usr/bin/env bash
# Query leaf sub-issues of an Epic for candidate selection.
# Usage: query-epic-subissues.sh <EPIC_NUMBER>
#
# Emits the raw GraphQL payload. Alongside the eligibility fields (state,
# assignees, blockedBy, subIssues, labels) it returns the two signals the fit
# stage needs and consumers used to have to guess at:
#   - issueType     — which skill can execute the issue (Task -> build, Bug ->
#                     bugfix, Idea/Concern -> plan-issue)
#   - Schedule      — the authoritative priority tier (PAD-03-001), read from
#                     Project #24 on both the Epic and each leaf
# Pipe into `PYTHONPATH= uv run bundle-fit` to apply fit; see shared/bundling.md.
set -euo pipefail

EPIC_NUMBER="${1:?Usage: $0 <EPIC_NUMBER>}"

# Titles (not bodies) are requested on purpose: bodies would multiply this
# payload by ~50x in an agent's context, and the coherence hints that read them
# work from spec IDs and paths, which titles already carry.
gh api graphql -f query="{
  repository(owner:\"CERTCC\", name:\"Vultron\") {
    issue(number: ${EPIC_NUMBER}) {
      number title
      projectItems(first: 5) { nodes {
        project { number }
        fieldValueByName(name: \"Schedule\") {
          ... on ProjectV2ItemFieldSingleSelectValue { name }
        }
      }}
      subIssues(first: 50) {
        nodes {
          number title state
          issueType { name }
          assignees(first: 1) { nodes { login } }
          blockedBy(first: 10) { nodes { number title state } }
          subIssues(first: 1) { totalCount }
          labels(first: 10) { nodes { name } }
          projectItems(first: 5) { nodes {
            project { number }
            fieldValueByName(name: \"Schedule\") {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
          }}
        }
      }
    }
  }
}"
