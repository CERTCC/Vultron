#!/usr/bin/env bash
# announce-claim.sh — record a claim on GitHub: assign, comment, and mirror Status.
# Usage: bash .agents/skills/shared/announce-claim.sh <ISSUE_NUMBER> <MESSAGE>
#   ISSUE_NUMBER  issue or Epic being claimed
#   MESSAGE       claim comment body (names the branch, or the epic run)
#
# The one place a claim is announced (PAD-04-002, PAD-19-001): claim-issue.sh
# calls it after the lock is taken, claim-epic.sh calls it as the Epic claim.
# An Epic carries no Status (PAD-16-012), so Status is set for non-Epics only.
set -euo pipefail

ISSUE_NUMBER="${1:?Usage: announce-claim.sh <ISSUE_NUMBER> <MESSAGE>}"
MESSAGE="${2:?Usage: announce-claim.sh <ISSUE_NUMBER> <MESSAGE>}"
SHARED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TYPE=$(bash "$SHARED/query-issue-type.sh" "$ISSUE_NUMBER" \
  | jq -r '.data.repository.issue.issueType.name // ""')

gh issue edit "$ISSUE_NUMBER" --add-assignee @me --repo CERTCC/Vultron
gh issue comment "$ISSUE_NUMBER" --repo CERTCC/Vultron --body "$MESSAGE"

if [ "$TYPE" != "Epic" ]; then
  bash "$SHARED/set-board-field.sh" "$ISSUE_NUMBER" status "In Progress"
fi
