#!/usr/bin/env bash
# add-to-project.sh — add a GitHub issue to Project #24 and set its Schedule.
# Usage: bash .agents/skills/shared/add-to-project.sh <ISSUE_NUMBER> [SCHEDULE]
#   ISSUE_NUMBER  GitHub issue number to add
#   SCHEDULE      Schedule value: Focus | Now | Next | Later | Someday (default: Someday)
set -euo pipefail

ISSUE_NUMBER="${1:?Usage: add-to-project.sh <ISSUE_NUMBER> [SCHEDULE]}"
SCHEDULE="${2:-Someday}"

PROJECT_ID="PVT_kwDOAjf0s84BZnre"
SCHEDULE_FIELD_ID="PVTSSF_lADOAjf0s84BZnrezhUlFOM"

case "$SCHEDULE" in
  Focus)   SCHEDULE_OPTION_ID="6bca50d7" ;;
  Now)     SCHEDULE_OPTION_ID="22e6679d" ;;
  Next)    SCHEDULE_OPTION_ID="1c1ed63d" ;;
  Later)   SCHEDULE_OPTION_ID="520032ef" ;;
  Someday) SCHEDULE_OPTION_ID="a890eacc" ;;
  *) echo "❌ Unknown schedule value: $SCHEDULE (use Focus|Now|Next|Later|Someday)" >&2; exit 1 ;;
esac

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
    fieldId: \"${SCHEDULE_FIELD_ID}\"
    value: { singleSelectOptionId: \"${SCHEDULE_OPTION_ID}\" }
  }) { projectV2Item { id } }
}" >/dev/null

echo "Added #${ISSUE_NUMBER} to Project #24 with Schedule=${SCHEDULE}" >&2
