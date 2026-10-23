---
title: git rebase fails in worktree when pre-commit hook modifies files
type: learning
timestamp: 2026-07-10T18:30:00Z
source: ISSUE-1332
---

`git rebase origin/main` in a git worktree fails with "Your local changes to
the following files would be overwritten by merge" even when `git status` shows
a clean working tree. The pre-commit hook (black, flake8) runs during the
checkout step of the rebase and modifies files, which git then sees as unstaged
changes that conflict with the incoming commits.

Workaround: use `git reset --soft origin/main` to move HEAD to the new base
while keeping staged changes, then manually inspect and re-stage only the files
from the current branch, restoring main's versions of all other files with
`git checkout origin/main -- <file>`. This achieves the same result as rebase
without triggering the hook interference.

Alternative: `git merge origin/main` also works and auto-resolves most conflicts,
but produces a merge commit rather than a linear history.

**Promoted**: 2026-07-15 — captured in AGENTS.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1458>8>8>8>8>.
