#!/usr/bin/env bash
# sync-with-main.sh — merge origin/main into the current task branch so an
# already-pushed PR is conflict-free against its base.
#
# Use this (not freshen-branch.sh) once a branch has been pushed and a PR is
# open: it records a merge commit instead of rewriting history, so no
# force-push is needed and reviewers' line comments survive.
#   - freshen-branch.sh → BEFORE the first push (rewrites, keeps history linear)
#   - sync-with-main.sh → AFTER a PR exists (merges, preserves pushed SHAs)
#
# On conflict this script deliberately leaves the merge IN PROGRESS with the
# conflict markers in the worktree — resolving them needs judgment the script
# does not have. The caller resolves, stages, and commits (or aborts).
#
# Usage:
#   bash .agents/skills/shared/sync-with-main.sh                 # merge origin/main
#   bash .agents/skills/shared/sync-with-main.sh fix/demo-ci     # stacked PR base
#   bash .agents/skills/shared/sync-with-main.sh --abort          # abandon a merge
#
# Pass the PR's actual base branch when it is not `main` — stacked PRs target
# another task branch, and syncing those against main is wrong. The branch name
# may be given bare (`fix/demo-ci`) or remote-qualified (`origin/fix/demo-ci`).
#
# Exit codes:
#   0 — already up to date, or merged cleanly (merge commit may be created)
#   1 — conflicts left in the worktree; conflicted paths printed to stdout
#   2 — unexpected error (detached HEAD, dirty tree, merge already in progress)
set -uo pipefail

BASE_BRANCH=${1:-main}
BASE_BRANCH=${BASE_BRANCH#origin/}
BASE_REF="origin/${BASE_BRANCH}"

if [ "${1:-}" = "--abort" ]; then
  if git merge --abort 2>/dev/null; then
    echo "✓ Merge aborted; worktree restored."
    exit 0
  fi
  echo "❌ sync-with-main: no merge in progress to abort." >&2
  exit 2
fi

TASK_BRANCH=$(git branch --show-current)
if [ -z "$TASK_BRANCH" ]; then
  echo "❌ sync-with-main: not on a named branch (detached HEAD?)" >&2
  exit 2
fi

if [ -e "$(git rev-parse --git-dir)/MERGE_HEAD" ]; then
  echo "❌ sync-with-main: a merge is already in progress. Resolve it or run --abort." >&2
  exit 2
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "❌ sync-with-main: worktree is dirty. Commit or stash before syncing." >&2
  git status --porcelain >&2
  exit 2
fi

if ! git fetch origin "$BASE_BRANCH"; then
  echo "❌ sync-with-main: git fetch of origin/$BASE_BRANCH failed." >&2
  exit 2
fi

BASE_TIP=$(git rev-parse "$BASE_REF")
if git merge-base --is-ancestor "$BASE_TIP" HEAD; then
  echo "✓ Branch already contains $BASE_REF ($(git rev-parse --short "$BASE_TIP")) — nothing to sync."
  exit 0
fi

echo "→ Merging $BASE_REF ($(git rev-parse --short "$BASE_TIP")) into $TASK_BRANCH"

if git merge --no-edit "$BASE_REF"; then
  echo "✓ Merged $BASE_REF cleanly into $TASK_BRANCH."
  exit 0
fi

CONFLICTED=$(git diff --name-only --diff-filter=U)
if [ -z "$CONFLICTED" ]; then
  echo "❌ sync-with-main: merge failed but no conflicted paths found — investigate." >&2
  exit 2
fi

echo "⚠ Merge conflicts — resolve these paths, then stage and commit:" >&2
printf '%s\n' "$CONFLICTED"
exit 1
