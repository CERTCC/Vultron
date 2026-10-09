# Work Epic Tasks — Reference

## Status file

`.claude/work-epic-<EPIC>.json` (gitignored). It records only what GitHub
cannot: the approved plan, each task's model and wave, parked questions, and
worktree paths. Update it at every state change. On re-invocation for the same
Epic, load it and compare with GitHub (issue, PR, branch state). **GitHub
wins**; tell the user about any mismatch and do not guess.

## Stall detection

You cannot see inside a background agent. Check the worktree at intervals
(`git -C /tmp/wt-<N> log`, `git status`). Treat a build as stalled when:

- elapsed time is well past the budget for its `size:` label, or
- there is no new commit or file change for a set stretch, or
- the same test/lint error repeats.

Budgets are tuning values; set them in the plan and revise from experience.
The Opus replacement gets the branch as it stands plus a note on why the first
attempt was stopped.

## Merge and sync

Use merge commits (the repo's convention). `pr-verify`'s live merge-state check
is the final gate. Never merge on red or skip a hook.

## Worktrees

Created by you, removed by explicit `git worktree remove <path>` after the
merge. If removal is not clean, report it; do not force or prune. Parked tasks
keep their worktrees until resolved.

## Report sections

Completed · Parked (with the open question) · Excluded (with reason) · Plan
changes · New issues (type, source task, blocking?) · Worktrees left behind.
