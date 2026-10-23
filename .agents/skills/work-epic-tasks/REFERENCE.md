# Work Epic Tasks — Reference

## Status file

`.claude/work-epic-<EPIC>.json` (gitignored). It records only what GitHub
cannot: the approved plan, each task's model and wave, parked questions, and
worktree paths. Update it at every state change. On re-invocation for the same
Epic, load it and compare with GitHub (issue, PR, branch state). **GitHub
wins**; tell the user about any mismatch and do not guess.

The Epic claim is not in the status file: GitHub records it as the Epic's
assignee. A resumed run claims the Epic again (step 3), because the last run
released it (step 6).

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

Use merge commits (the repo's convention): `gh pr merge --merge`, and
`gh pr update-branch` (which merges `main` in) rather than `--rebase`.
`pr-verify`'s live merge-state check is the final gate; the pre-merge check in
SKILL.md step 4 runs on the PR about to merge, never as a sweep of every open
PR after a merge (PAD-18-009, ADR-0138). Only a conflict sends a PR back to
`pr-ship`; `BEHIND` or overlapping files are cleared by `gh pr update-branch`
and a green CI run, with no local merge and no local suite. Never merge on red
or skip a hook.

## Worktrees

Created by you, removed by explicit `git worktree remove <path>` after the
merge. If removal is not clean, report it; do not force or prune. Parked tasks
keep their worktrees until resolved.

## Report sections

Completed · Parked (with the open question) · Excluded (with reason) · Taken
elsewhere (planned Bugs another agent claimed first) · Plan changes · New issues
(type, source task, blocking?) · Worktrees left behind.
