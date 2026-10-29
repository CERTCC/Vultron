#!/usr/bin/env bash
# claim-epic.sh — claim an Epic for an epic run (work-epic-tasks, PAD-19-001).
# Usage: bash .agents/skills/shared/claim-epic.sh <EPIC_NUMBER>
#
# The claim is the Epic's assignee plus a comment — no label, branch, or board
# field (an Epic carries no Status, PAD-16-012). While it holds, the Epic's open
# Tasks and Features are held for this run (epic-hold.sh, bundle-fit).
#
# The assignee check and the assignment are two calls, not one atomic step, so
# two runs started at the same moment can both pass. Runs are started by a
# person, so this is accepted rather than locked (PAD-19-008).
#
# Exit codes: 0 claimed; 1 not an Epic, already claimed, or API error.
set -euo pipefail

EPIC="${1:?Usage: claim-epic.sh <EPIC_NUMBER>}"
SHARED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! "${EPIC}" =~ ^[0-9]+$ ]]; then
  echo "❌ '${EPIC}' is not an issue number." >&2
  exit 1
fi

DATA=$(gh issue view "${EPIC}" --repo CERTCC/Vultron --json state,assignees)
TYPE=$(bash "${SHARED}/query-issue-type.sh" --name "${EPIC}")
if [ "${TYPE}" != "Epic" ]; then
  echo "❌ #${EPIC} is a ${TYPE:-untyped issue}, not an Epic." >&2
  exit 1
fi
if [ "$(jq -r '.state' <<<"${DATA}")" != "OPEN" ]; then
  echo "❌ Epic #${EPIC} is closed." >&2
  exit 1
fi
LOGINS=$(jq -r '[.assignees[].login] | join(", ")' <<<"${DATA}")
if [ -n "${LOGINS}" ]; then
  echo "❌ Epic #${EPIC} is already claimed (assigned to ${LOGINS}). Another" \
    "epic run may be in progress; a human releases an abandoned one." >&2
  exit 1
fi

bash "${SHARED}/announce-claim.sh" --epic-run "${EPIC}" "$(cat <<MSG
Epic run started by \`work-epic-tasks\`. Its open Tasks and Features are held for
this run until it is released; Bugs, Ideas, and Concerns stay open to other agents.
MSG
)"
echo "Claimed Epic #${EPIC}" >&2
