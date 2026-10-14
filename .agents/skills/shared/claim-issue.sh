#!/usr/bin/env bash
# claim-issue.sh — sync, have GitHub create the linked claim branch, announce.
# Usage: bash .agents/skills/shared/claim-issue.sh [--epic-run <EPIC>] <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG> [OTHERS...]
#   --epic-run     The Epic whose run this claim belongs to (work-epic-tasks
#                  passes it); lets a Task or Feature under that claimed Epic
#                  be claimed (PAD-19-003)
#   ISSUE_NUMBER   GitHub issue number to claim (the primary; names the branch)
#   BRANCH_PREFIX  Branch name prefix: task, bug, plan, etc.
#   SLUG           Short slug derived from the issue title
#   OTHERS         Additional bundle members claimed onto the same branch
#
# The lock is the branch on GitHub (PAD-04-001), created by the
# createLinkedBranch mutation so it is linked to the issue. That mutation does
# not fail on an existing name: it returns a null linkedBranch, which is read
# as "already claimed". `gh issue develop` is not used because it exits 0 in
# that case (ISSUE-4617, AC-1).
#
# Exit codes: 0 claimed (prints the branch name); 1 refused or failed;
#             3 a member is held by an epic run on its Epic.
set -Eeuo pipefail  # -E: functions inherit the ERR rollback trap

USAGE="Usage: claim-issue.sh [--epic-run <EPIC>] <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG> [OTHERS...]"
EPIC_RUN=""
if [ "${1:-}" = "--epic-run" ]; then
  EPIC_RUN="${2:?$USAGE}"
  shift 2
fi

ISSUE_NUMBER="${1:?$USAGE}"
BRANCH_PREFIX="${2:?$USAGE}"
SLUG="${3:?$USAGE}"
shift 3
OTHERS=("$@")
SHARED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BRANCH="${BRANCH_PREFIX}/${ISSUE_NUMBER}-${SLUG}"
MEMBERS=("${ISSUE_NUMBER}" ${OTHERS[@]+"${OTHERS[@]}"})

# Validate every member BEFORE mutating anything. Claiming is not atomic, and
# bundling multiplies the blast radius: a bad member number discovered after the
# branch exists leaves earlier members assigned and commented with no branch
# name returned to the caller, and a retry then trips the "already claimed" guard.
seen=""
for member in "${MEMBERS[@]}"; do
  if [[ ! "${member}" =~ ^[0-9]+$ ]]; then
    echo "❌ '${member}' is not an issue number." >&2
    exit 1
  fi
  case " ${seen} " in
    *" ${member} "*)
      echo "❌ #${member} is listed twice — a member would be claimed and" \
        "commented on twice." >&2
      exit 1
      ;;
  esac
  seen="${seen} ${member}"
  if ! gh issue view "${member}" --repo CERTCC/Vultron --json number \
      >/dev/null 2>&1; then
    echo "❌ #${member} does not exist or is not readable — nothing claimed." >&2
    exit 1
  fi
  # A Task or Feature under a claimed Epic belongs to that Epic's run.
  hold_rc=0
  bash "${SHARED}/epic-hold.sh" "${member}" "${EPIC_RUN}" || hold_rc=$?
  if [ "${hold_rc}" -eq 3 ]; then
    echo "❌ Nothing claimed. Ask the user before working #${member}." >&2
    exit 3
  elif [ "${hold_rc}" -ne 0 ]; then
    echo "❌ Could not check #${member}'s Epic — nothing claimed." >&2
    exit 1
  fi
done

# Sync check
bash "${SHARED}/sync-check.sh" \
  || { echo "❌ Claim aborted — sync check failed." >&2; exit 1; }

if git show-ref --quiet "refs/heads/${BRANCH}" 2>/dev/null; then
  echo "❌ Local branch ${BRANCH} already exists — delete it or pick another" \
    "slug. Nothing claimed." >&2
  exit 1
fi

# Take the lock: GitHub creates the branch at origin/main, linked to the issue.
ISSUE_ID=$(gh api graphql -f query="{
  repository(owner:\"CERTCC\", name:\"Vultron\") {
    issue(number: ${ISSUE_NUMBER}) { id }
  }
}" --jq '.data.repository.issue.id')
REPO_ID=$(bash "${SHARED}/board-id.sh" repo)
BASE_OID=$(git rev-parse origin/main)
LINKED=$(gh api graphql \
  -f query='mutation($issue:ID!, $repo:ID!, $oid:GitObjectID!, $name:String!) {
    createLinkedBranch(input: {issueId: $issue, repositoryId: $repo,
                               oid: $oid, name: $name}) {
      linkedBranch { id }
    }
  }' \
  -f issue="${ISSUE_ID}" -f repo="${REPO_ID}" -f oid="${BASE_OID}" \
  -f name="${BRANCH}" \
  --jq '.data.createLinkedBranch.linkedBranch.id // ""')
if [ -z "${LINKED}" ]; then
  echo "❌ Branch ${BRANCH} already exists on GitHub — #${ISSUE_NUMBER} is" \
    "already claimed. Nothing claimed." >&2
  exit 1
fi

# From here the branch exists, so a failure mid-bundle must say exactly which
# members were already claimed and drop the branch so a retry is possible.
CLAIMED=()
rollback() {
  echo "❌ Claim failed partway through." >&2
  if [[ ${#CLAIMED[@]} -gt 0 ]]; then
    echo "   Already assigned and commented: ${CLAIMED[*]/#/#}" >&2
    echo "   Un-assign those and delete their claim comments before retrying." >&2
  fi
  echo "   Deleting branch ${BRANCH} so the claim can be retried." >&2
  git switch - >/dev/null 2>&1 || true
  git branch -D "${BRANCH}" >/dev/null 2>&1 || true
  git push origin --delete "${BRANCH}" >/dev/null 2>&1 || true
}
trap rollback ERR

git fetch origin "${BRANCH}"
git switch -c "${BRANCH}" "origin/${BRANCH}"

# Every bundle member is announced onto the one branch (PAD-15-009). An Epic
# (planned by plan-issue) gets the comment only: its assignee is the epic-run
# claim (PAD-19-001), and assigning it here would hold its Tasks indefinitely.
claim() {
  local message="Claimed on branch \`${BRANCH}\`.$2" type
  type=$(bash "${SHARED}/query-issue-type.sh" "$1" \
    | jq -r '.data.repository.issue.issueType.name // ""')
  if [ "${type}" = "Epic" ]; then
    gh issue comment "$1" --repo CERTCC/Vultron --body "${message}"
  else
    bash "${SHARED}/announce-claim.sh" "$1" "${message}"
  fi
  CLAIMED+=("$1")
}

claim "${ISSUE_NUMBER}" ""

for member in ${OTHERS[@]+"${OTHERS[@]}"}; do
  claim "${member}" " Bundled with #${ISSUE_NUMBER} in one PR."
done

trap - ERR
echo "${BRANCH}"
