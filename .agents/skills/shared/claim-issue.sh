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

# Sync check
bash "$(dirname "$0")/sync-check.sh" \
  || { echo "❌ Claim aborted — sync check failed." >&2; exit 1; }

# Abort if branch already exists (issue already claimed)
if git show-ref --quiet "refs/heads/${BRANCH}" 2>/dev/null; then
  echo "❌ Branch ${BRANCH} already exists — issue already claimed." >&2
  exit 1
fi

git switch -c "${BRANCH}"

# The branch is the distributed lock (it is created once, above); every bundle
# member is then claimed onto it the same way a single issue always was.
claim() {
  gh issue edit "$1" --add-assignee @me --repo CERTCC/Vultron
  gh issue comment "$1" --repo CERTCC/Vultron \
    --body "Claimed on branch \`${BRANCH}\`.$2"
}

claim "${ISSUE_NUMBER}" ""

for member in ${OTHERS[@]+"${OTHERS[@]}"}; do
  claim "${member}" " Bundled with #${ISSUE_NUMBER} in one PR."
done

echo "${BRANCH}"
