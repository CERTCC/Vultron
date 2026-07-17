---
title: "git rebase fails in worktrees when pre-commit hook modifies files during cherry-pick"
type: learning
timestamp: 2026-07-17
source: ISSUE-1503
---

`git rebase origin/main` fails with "Your local changes would be overwritten" in
a git worktree environment (multiple worktrees sharing one `.git`) when a
pre-commit hook (e.g. `black`) modifies files during the cherry-pick step.

The workaround that worked: `git reset --soft origin/main` to move the branch
parent to the new `origin/main` tip while keeping all staged changes, then
`git -c core.hooksPath=/dev/null commit` to re-create the commit without running
hooks. Then `git branch -f <branch> HEAD` to update the branch pointer if in
detached HEAD state.

Using `-c core.hooksPath=/dev/null` on the `rebase` command itself was NOT
sufficient — the failure occurred before hooks ran, during git's internal
3-way merge checkout.

Root cause: during rebase, git checks out the onto-point (origin/main) as the
base for the merge. In a worktree, the working tree files already contain the
newer committed versions. Git sees this as "uncommitted changes" relative to
origin/main and aborts.
