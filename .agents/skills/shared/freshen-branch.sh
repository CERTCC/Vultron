#!/usr/bin/env bash
# freshen-branch.sh — bring the current task branch current with origin/main
# by cherry-picking its commits onto a fresh branch from origin/main.
#
# Avoids the git sequencer duplicate-pick bug that `git rebase` triggers on
# large single-commit branches (see plan/incoming/learnings/
# 20260720-git-rebase-duplicate-pick-on-large-branch.md).
#
# Usage: bash .agents/skills/shared/freshen-branch.sh
#
# Exit codes:
#   0  — branch is fresh (either already up-to-date or cherry-pick succeeded)
#   1  — cherry-pick conflicts; callers must open a draft PR with needs-rebase label
#   2  — unexpected error (not a conflict)
set -euo pipefail

TASK_BRANCH=$(git branch --show-current)
if [ -z "$TASK_BRANCH" ]; then
  echo "❌ freshen-branch: not on a named branch (detached HEAD?)" >&2
  exit 2
fi

git fetch origin main

MERGE_BASE=$(git merge-base HEAD origin/main)
ORIGIN_TIP=$(git rev-parse origin/main)

if [ "$MERGE_BASE" = "$ORIGIN_TIP" ]; then
  echo "✓ Branch already rooted at origin/main — nothing to do."
  exit 0
fi

COMMITS=$(git log --reverse --format="%H" origin/main..HEAD)
if [ -z "$COMMITS" ]; then
  echo "✓ No commits ahead of origin/main — nothing to cherry-pick."
  exit 0
fi

TEMP="temp-freshen-$$"
git checkout -b "$TEMP" origin/main

if git cherry-pick $COMMITS; then
  git branch -f "$TASK_BRANCH" HEAD
  git checkout "$TASK_BRANCH"
  git branch -D "$TEMP"
  echo "✓ Branch freshened onto origin/main."
  exit 0
else
  # Cherry-pick stopped on a conflict — clean up and signal the caller.
  git cherry-pick --abort 2>/dev/null || true
  git checkout "$TASK_BRANCH"
  git branch -D "$TEMP"
  echo "⚠ Cherry-pick conflict — push un-rebased branch and open a draft PR with needs-rebase label." >&2
  exit 1
fi
