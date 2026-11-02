#!/usr/bin/env bash
# announce-claim.sh — record a claim on GitHub: assign, comment, and mirror Status.
# Usage: bash .agents/skills/shared/announce-claim.sh [--epic-run] <ISSUE_NUMBER> <MESSAGE>
#   --epic-run    the claim is an epic run on this Epic (claim-epic.sh only)
#   ISSUE_NUMBER  issue or Epic being claimed
#   MESSAGE       claim comment body (names the branch, or the epic run)
#
# The one place a claim is announced (PAD-04-002/005/006, PAD-19-001): claim-issue.sh
# calls it after the lock is taken, claim-epic.sh calls it as the Epic claim.
#   - non-Epic: assign @me, comment, set Status = In Progress
#   - Epic, --epic-run: assign @me and comment (an Epic has no Status,
#     PAD-16-012)
#   - Epic otherwise (plan-issue planning it): comment only — an Epic's
#     assignee means an epic run, and nothing would ever release it
set -euo pipefail

USAGE="Usage: announce-claim.sh [--epic-run] <ISSUE_NUMBER> <MESSAGE>"
EPIC_RUN=false
if [ "${1:-}" = "--epic-run" ]; then
  EPIC_RUN=true
  shift
fi
ISSUE_NUMBER="${1:?$USAGE}"
MESSAGE="${2:?$USAGE}"
SHARED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TYPE=$(bash "$SHARED/query-issue-type.sh" --name "$ISSUE_NUMBER")

if [ "$TYPE" != "Epic" ] || [ "$EPIC_RUN" = true ]; then
  gh issue edit "$ISSUE_NUMBER" --add-assignee @me --repo CERTCC/Vultron
fi
gh issue comment "$ISSUE_NUMBER" --repo CERTCC/Vultron --body "$MESSAGE"

if [ "$TYPE" != "Epic" ]; then
  bash "$SHARED/set-board-field.sh" "$ISSUE_NUMBER" status "In Progress"
fi
