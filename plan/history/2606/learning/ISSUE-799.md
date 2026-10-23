---
source: ISSUE-799
timestamp: '2026-06-08T13:41:55.585779+00:00'
title: Rebase worktree branch to origin/main before opening PR
type: learning
---

## 2026-06-05 ISSUE-799 — Rebase worktree branch to origin/main before opening PR

When creating a task branch inside a worktree slot (e.g. `wt/pinky`), always
check that the worktree branch is up to date with `origin/main` before branching.
In this session `wt/pinky` was behind `origin/main` by one commit; the naive
`git rebase origin/main` reported "already up to date" because the worktree tip
was the merge-base of `origin/main`, not its descendant. The fix:
`git merge-base origin/main <worktree-branch>` to diagnose, then
`git rebase origin/main` from the task branch after confirming the base is correct.

**Promoted**: 2026-06-08 — captured in `AGENTS.md`, `notes/codebase-structure.md`, and `notes/domain-model-separation.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/818>.
