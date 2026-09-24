#!/usr/bin/env bash
# claim-issue.sh — sync, create task branch, assign, and post claim comment.
# Usage: bash .agents/skills/shared/claim-issue.sh <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG> [OTHERS...]
#   ISSUE_NUMBER   GitHub issue number to claim (the primary; names the branch)
#   BRANCH_PREFIX  Branch name prefix: task, bug, ingest, etc.
#   SLUG           Short slug derived from the issue title
#   OTHERS         Additional bundle members claimed onto the same branch
# Exits non-zero on sync failure or if branch already exists.
set -euo pipefail

ISSUE_NUMBER="${1:?Usage: claim-issue.sh <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG> [OTHERS...]}"
BRANCH_PREFIX="${2:?Usage: claim-issue.sh <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG> [OTHERS...]}"
SLUG="${3:?Usage: claim-issue.sh <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG> [OTHERS...]}"
shift 3
OTHERS=("$@")

BRANCH="${BRANCH_PREFIX}/${ISSUE_NUMBER}-${SLUG}"
MEMBERS=("${ISSUE_NUMBER}" ${OTHERS[@]+"${OTHERS[@]}"})

# Validate every member BEFORE mutating anything. Claiming is not atomic, and
# bundling multiplies the blast radius: a bad member number discovered after the
# branch exists leaves earlier members assigned and commented with no branch
# name returned to the caller, and a retry then trips the "already exists" guard.
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
done

# Sync check
bash "$(dirname "$0")/sync-check.sh" \
  || { echo "❌ Claim aborted — sync check failed." >&2; exit 1; }

# Abort if branch already exists (issue already claimed)
if git show-ref --quiet "refs/heads/${BRANCH}" 2>/dev/null; then
  echo "❌ Branch ${BRANCH} already exists — issue already claimed." >&2
  exit 1
fi

git switch -c "${BRANCH}"

# From here the branch exists, so a failure mid-bundle must say exactly which
# members were already claimed and drop the branch so a retry is possible.
CLAIMED=()
rollback() {
  echo "❌ Claim failed partway through the bundle." >&2
  if [[ ${#CLAIMED[@]} -gt 0 ]]; then
    echo "   Already assigned and commented: ${CLAIMED[*]/#/#}" >&2
    echo "   Un-assign those and delete their claim comments before retrying." >&2
  fi
  echo "   Deleting branch ${BRANCH} so the claim can be retried." >&2
  git switch - >/dev/null 2>&1 || true
  git branch -D "${BRANCH}" >/dev/null 2>&1 || true
}
trap rollback ERR

# The branch is the distributed lock (it is created once, above); every bundle
# member is then claimed onto it the same way a single issue always was.
claim() {
  gh issue edit "$1" --add-assignee @me --repo CERTCC/Vultron
  gh issue comment "$1" --repo CERTCC/Vultron \
    --body "Claimed on branch \`${BRANCH}\`.$2"
  CLAIMED+=("$1")
}

claim "${ISSUE_NUMBER}" ""

for member in ${OTHERS[@]+"${OTHERS[@]}"}; do
  claim "${member}" " Bundled with #${ISSUE_NUMBER} in one PR."
done

trap - ERR
echo "${BRANCH}"
