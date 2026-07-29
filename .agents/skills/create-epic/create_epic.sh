#!/usr/bin/env bash
# create_epic.sh — Create a GitHub Epic issue for CERTCC/Vultron
#
# Usage: create_epic.sh <title> <body> [schedule]
#   schedule  Focus | Now | Next | Later | Someday (default: Someday)
#
# Prints the new issue number on stdout.
# All other output goes to stderr.
#
# Example:
#   EPIC_NUM=$(./create_epic.sh \
#     "Architecture Hardening (Phase 2): Import violations and BT sync" \
#     "$(cat body.md)" Next)

set -euo pipefail

EPIC_TITLE="${1:?Usage: create_epic.sh <title> <body> [schedule]}"
EPIC_BODY="${2:?Usage: create_epic.sh <title> <body> [schedule]}"
SCHEDULE="${3:-Someday}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADD_TO_PROJECT="${SCRIPT_DIR}/../shared/add-to-project.sh"

REPO_NODE_ID="R_kgDOIn77fA"
EPIC_TYPE_ID="IT_kwDOAjf0s84B_E1A"

# JSON-encode title and body for safe GraphQL embedding
TITLE_JSON=$(printf '%s' "${EPIC_TITLE}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
BODY_JSON=$(printf '%s' "${EPIC_BODY}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

echo "Creating Epic issue: ${EPIC_TITLE}" >&2

# Step 1: Create the issue via GraphQL with Epic issue type
RESULT=$(gh api graphql -f query="
mutation {
  createIssue(input: {
    repositoryId: \"${REPO_NODE_ID}\"
    title: ${TITLE_JSON}
    body: ${BODY_JSON}
    issueTypeId: \"${EPIC_TYPE_ID}\"
  }) {
    issue { number id url }
  }
}")

EPIC_NUMBER=$(echo "${RESULT}" | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['number'])")
EPIC_URL=$(echo "${RESULT}" | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['url'])")

echo "  Created Epic #${EPIC_NUMBER}: ${EPIC_URL}" >&2

# Step 2: Add to Project #24 and set Schedule via the shared helper, which is
# the single source of truth for the project/field/option IDs.
bash "${ADD_TO_PROJECT}" "${EPIC_NUMBER}" "${SCHEDULE}"

# Output only the Epic issue number on stdout so callers can capture it directly
echo "${EPIC_NUMBER}"
