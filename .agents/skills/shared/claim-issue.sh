#!/usr/bin/env bash
# claim-issue.sh — sync, create task branch, assign, and post claim comment.
# Usage: bash .agents/skills/shared/claim-issue.sh <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG>
#   ISSUE_NUMBER   GitHub issue number to claim
#   BRANCH_PREFIX  Branch name prefix: task, bug, ingest, etc.
#   SLUG           Short slug derived from the issue title
# Exits non-zero on sync failure or if branch already exists.
set -euo pipefail

ISSUE_NUMBER="${1:?Usage: claim-issue.sh <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG>}"
BRANCH_PREFIX="${2:?Usage: claim-issue.sh <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG>}"
SLUG="${3:?Usage: claim-issue.sh <ISSUE_NUMBER> <BRANCH_PREFIX> <SLUG>}"

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
gh issue edit "${ISSUE_NUMBER}" --add-assignee @me --repo CERTCC/Vultron
gh issue comment "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --body "Claimed on branch \`${BRANCH}\`."
echo "${BRANCH}"
