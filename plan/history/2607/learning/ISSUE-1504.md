---
title: git rebase fails with "local changes would be overwritten" when branch diverged far from main
type: learning
timestamp: "2026-07-20T00:00:00+00:00"
source: ISSUE-1504
---

When a branch diverges many commits from `origin/main` and the single implementation
commit touches 70+ files, `git rebase origin/main` can fail with:

> "Your local changes to the following files would be overwritten by merge"

even with a clean working tree. This appears to be a git sequencer quirk where the
rebase applies the commit but then re-adds a duplicate pick to the todo list.

**Workaround**:

```bash
git rebase --abort
git checkout -b temp-branch origin/main
git cherry-pick <implementation-commit-hash>
git branch -f task/<branch-name> HEAD
git checkout task/<branch-name>
git branch -d temp-branch
git push ...
```

This creates the rebased state cleanly without the sequencer confusion.

**Prevention**: Keep branches short-lived and rebase frequently to avoid large
divergence. The build skill's Phase 0 (`git fetch && git reset --hard origin/main`)
should be run immediately before starting work to root the branch at current main.

**Promoted**: 2026-07-22 — captured in `AGENTS.md (root)`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1608>8>8>.
