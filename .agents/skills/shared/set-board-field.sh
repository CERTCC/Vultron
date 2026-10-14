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

ITEM_ID=$(gh api graphql -f query="mutation {
  addProjectV2ItemById(input: {
    projectId: \"${PROJECT_ID}\"
    contentId: \"${NODE_ID}\"
  }) { item { id } }
}" --jq '.data.addProjectV2ItemById.item.id')

gh api graphql -f query="mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: \"${PROJECT_ID}\"
    itemId: \"${ITEM_ID}\"
    fieldId: \"${FIELD_ID}\"
    value: { singleSelectOptionId: \"${OPTION_ID}\" }
  }) { projectV2Item { id } }
}" >/dev/null

echo "Set #${ISSUE_NUMBER} ${FIELD}=${OPTION} on Project #24" >&2
