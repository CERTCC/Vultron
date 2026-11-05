#!/usr/bin/env bash
# set-board-field.sh — put an issue on Project #24 and set one single-select field.
# Usage: bash .agents/skills/shared/set-board-field.sh <ISSUE_NUMBER> <schedule|status> <OPTION>
#   ISSUE_NUMBER  GitHub issue number
#   FIELD         schedule (Epics, PAD-02-001) or status (non-Epics, PAD-16-001)
#   OPTION        option name, e.g. Now, or "In Progress"
#
# Adding an item that is already on the board returns the existing item, so the
# script is safe to run on an issue the board already carries.
set -euo pipefail

ISSUE_NUMBER="${1:?Usage: set-board-field.sh <ISSUE_NUMBER> <schedule|status> <OPTION>}"
FIELD="${2:?Usage: set-board-field.sh <ISSUE_NUMBER> <schedule|status> <OPTION>}"
OPTION="${3:?Usage: set-board-field.sh <ISSUE_NUMBER> <schedule|status> <OPTION>}"

case "$FIELD" in
  schedule|status) ;;
  *) echo "❌ Unknown field: $FIELD (use schedule|status)" >&2; exit 1 ;;
esac

# All board IDs are resolved live-and-cached via board-id.sh — never hardcoded
# (they rotate when a field's options are edited).
BOARD_ID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/board-id.sh"
PROJECT_ID=$(bash "$BOARD_ID" project)
FIELD_ID=$(bash "$BOARD_ID" "${FIELD}-field")
case "$FIELD" in
  schedule) VALID="Focus|Now|Next|Later|Someday" ;;
  status) VALID="Backlog|Ready|In Progress|In Review|Done" ;;
esac
if ! OPTION_ID=$(bash "$BOARD_ID" "$FIELD" "$OPTION"); then
  echo "❌ Unknown ${FIELD} value: $OPTION (use ${VALID})" >&2
  exit 1
fi

NODE_ID=$(gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: '"${ISSUE_NUMBER}"') { id }
  }
}' --jq '.data.repository.issue.id')

# A board automation adds new issues to the project too. When it races this add,
# GitHub refuses with "Content already exists in this project" instead of
# returning the existing item, so fall back to reading the item the issue
# already has on this project.
existing_item_id() {
  gh api graphql -f query='query($id: ID!) {
    node(id: $id) { ... on Issue { projectItems(first: 20) {
      nodes { id project { id } } } } }
  }' -f id="${NODE_ID}" \
    --jq ".data.node.projectItems.nodes[] | select(.project.id == \"${PROJECT_ID}\") | .id"
}

ADD_ERR=$(mktemp)
trap 'rm -f "${ADD_ERR}"' EXIT
if ! ADD_OUT=$(gh api graphql -f query="mutation {
  addProjectV2ItemById(input: {
    projectId: \"${PROJECT_ID}\"
    contentId: \"${NODE_ID}\"
  }) { item { id } }
}" --jq '.data.addProjectV2ItemById.item.id' 2>"${ADD_ERR}"); then
  if ! grep -q "Content already exists" "${ADD_ERR}"; then
    cat "${ADD_ERR}" >&2
    exit 1
  fi
  ADD_OUT=""
  for _ in 1 2 3 4 5; do
    ADD_OUT=$(existing_item_id)
    [[ -n "${ADD_OUT}" ]] && break
    sleep 2
  done
  if [[ -z "${ADD_OUT}" ]]; then
    echo "❌ #${ISSUE_NUMBER} is reported as already on the board, but no item was found" >&2
    exit 1
  fi
fi
ITEM_ID="${ADD_OUT}"

gh api graphql -f query="mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: \"${PROJECT_ID}\"
    itemId: \"${ITEM_ID}\"
    fieldId: \"${FIELD_ID}\"
    value: { singleSelectOptionId: \"${OPTION_ID}\" }
  }) { projectV2Item { id } }
}" >/dev/null

echo "Set #${ISSUE_NUMBER} ${FIELD}=${OPTION} on Project #24" >&2
