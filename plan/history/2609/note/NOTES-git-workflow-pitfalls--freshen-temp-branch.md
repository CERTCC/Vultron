---
source: NOTES-git-workflow-pitfalls--freshen-temp-branch
timestamp: '2026-09-17T17:25:21.258921+00:00'
title: freshen-branch.sh Leaves Temp Branch on Conflict When Abort Silently Fails
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) self-labeled Fixed in #1784; duplicates preceding section
**Superseded by:** .agents/skills/shared/freshen-branch.sh

---

## `freshen-branch.sh` Leaves Temp Branch on Conflict When Abort Silently Fails

*Fixed in #1784.* The script now runs cherry-pick with `core.hooksPath=/dev/null`
(preventing pre-commit hook interference) and guards the cleanup checkout with
`|| git checkout -` (preventing silent exit when `cherry-pick --abort` leaves
conflict markers). If both checkout attempts still fail (rare: genuine conflict
marker blocking every branch switch), manual recovery is required:
`git branch --show-current` (confirm `temp-freshen-*`), resolve conflict
markers, `git add <file>`, `git cherry-pick --continue --no-edit`, then
`git branch -f "$TASK_BRANCH" HEAD && git checkout "$TASK_BRANCH" && git branch -D "$TEMP"`.
Use `manage_worktree.sh ensure-synced` in preference to the raw script.
