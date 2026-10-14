#!/usr/bin/env bash
# release-epic.sh — end an epic run: unassign the Epic and post the summary.
# Usage: bash .agents/skills/shared/release-epic.sh <EPIC_NUMBER> <SUMMARY>
#
# Run at every stop of work-epic-tasks, finished or not (PAD-19-004). Running
# the skill again claims the Epic again and resumes from its status file.
set -euo pipefail

EPIC="${1:?Usage: release-epic.sh <EPIC_NUMBER> <SUMMARY>}"
SUMMARY="${2:?Usage: release-epic.sh <EPIC_NUMBER> <SUMMARY>}"

LOGINS=$(gh issue view "${EPIC}" --repo CERTCC/Vultron --json assignees \
  --jq '[.assignees[].login] | join(",")')
if [ -n "${LOGINS}" ]; then
  gh issue edit "${EPIC}" --repo CERTCC/Vultron --remove-assignee "${LOGINS}"
else
  echo "⚠️  Epic #${EPIC} was not assigned; posting the summary anyway." >&2
fi

gh issue comment "${EPIC}" --repo CERTCC/Vultron --body "$(printf \
  'Epic run released.\n\n%s\n' "${SUMMARY}")"
echo "Released Epic #${EPIC}" >&2
