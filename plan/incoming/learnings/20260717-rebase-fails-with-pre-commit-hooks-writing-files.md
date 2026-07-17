---
title: git rebase fails when pre-commit hooks modify working tree files during pick
type: learning
timestamp: 2026-07-17T21:30:00Z
source: ISSUE-1499
---

`git rebase origin/main` can fail with "Your local changes to the following
files would be overwritten by merge" even when `git status` shows a clean
working tree. This happens when the pre-commit hook runs during the `pick`
step and writes files to the working tree (e.g., via Black auto-format), and
that write happens in a file that is also being replayed by the rebase.

The error appears to be a known git quirk where the rebase machinery checks
file state after the hook runs but before staging.

**Workaround:** Push the branch directly (without rebasing) when origin/main
has only diverged on unrelated files. The PR will be created against main and
GitHub will detect any conflicts. For non-conflicting divergence (different
files changed), this is safe.

**Alternative:** Use `git -c core.hooksPath=/dev/null rebase origin/main` to
skip hooks during the rebase, then run hooks manually via `pre-commit run --all-files`.
