---
title: freshen-branch.sh leaves temp branch on conflict when abort silently fails
type: learning
timestamp: "2026-07-23"
source: ISSUE-1619
signal: tooling-issue
---

When `freshen-branch.sh` encounters a cherry-pick conflict, its `else` block
calls `git cherry-pick --abort 2>/dev/null || true` then `git checkout
"$TASK_BRANCH"`. If the abort itself fails (e.g. because the cherry-pick state
is partially written), `|| true` swallows the error, but the subsequent
`git checkout "$TASK_BRANCH"` fails with "you need to resolve your current
index first" — and because the script uses `set -euo pipefail` with no `||
true` on that line, the script exits immediately, leaving the repo on the
temp branch with conflict markers in the working tree (temp branch is not
deleted).

**Recovery steps** (used on ISSUE-1619):

1. Confirm branch with `git branch --show-current` (will be `temp-freshen-*`).
2. Manually resolve conflict markers in the conflicted file.
3. `git add <conflicted-file>` then `git cherry-pick --continue --no-edit`.
4. `git branch -f "$TASK_BRANCH" HEAD && git checkout "$TASK_BRANCH" && git branch -D "$TEMP"`.

**Suggested fix**: replace `git checkout "$TASK_BRANCH"` in the else block
with `git checkout "$TASK_BRANCH" 2>/dev/null || git checkout -` so the
temp-branch deletion and exit-1 still happen even when a concurrent git
lock or unresolved state blocks the checkout.
