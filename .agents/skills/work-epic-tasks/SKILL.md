---
name: work-epic-tasks
description: >
  Orchestrates sub-agents to work an Epic's remaining open Tasks (and easy
  Bugs) to completion: plans waves of independent work, builds each in its own
  worktree, ships each PR through a fresh pr-ship agent, and merges on
  READY-TO-MERGE. Never closes the Epic; reports what was done. Use when the
  user asks to finish, drain, or "end-run" an Epic whose open children are
  about 10 or fewer Tasks.
---

# Skill: Work Epic Tasks

You are the **orchestrator**. You plan and coordinate; sub-agents implement
and review. Never close the Epic. Details: [REFERENCE.md](REFERENCE.md).

## Quick Start

```bash
/work-epic-tasks 1234            # Epic number; default max 3 agents at once
/work-epic-tasks 1234 --agents 2 # user-chosen concurrency
```

## Workflow

### 1. Entry check

Load the Epic's open children
(`bash .agents/skills/shared/query-epic-subissues.sh <N>`) and judge them:

- Not an Epic, or an Idea/Concern that could change what the Tasks build:
  **refuse**, saying why.
- More than 10 Tasks: ask permission before continuing.
- Bug: look quickly. Easy and self-contained → plan it with `bugfix`. Depends
  on a large decision → ask the user how to proceed.
- Claimed/assigned, `stale-claim`, `needs-info`, `ready-for-human`, blocked
  outside the Epic, or already has a PR: **exclude and report**, with the
  reason. Exclude anything downstream of an excluded issue too.

### 2. Plan (think hard)

Read the issues and the code they touch. Do not trust `blockedBy` alone:
look for shared files, one task needing another's helper, and shared specs.
Build **waves** of truly independent tasks; serialize anything that overlaps.
Use `bundle-fit` and `shared/bundling.md` for bundles (a bundle never mixes
Tasks and Bugs). Pick each task's build model: **Opus** for multi-file,
protocol/architecture, or judgment work; **Sonnet** for mechanical work.
Every `pr-ship` agent is **Opus**.

### 3. Approve

Show the plan (waves, bundles, models, exclusions, expected open worktrees).
**Always wait for approval.** Start nothing before it.

### 4. Execute

Write the status file, then run up to the agent cap at once. Per task:

1. Create `/tmp/wt-<issue>` from `origin/main` (never `git worktree prune`).
2. Spawn the build agent (`build`, or `bugfix`) in that worktree.
3. On PR open, spawn a **fresh** agent in the same worktree to run `pr-ship`.
4. Merge only on `READY-TO-MERGE`, as soon as it arrives. Then sync every
   other open PR with `main`; re-run `pr-ship` only if the sync touched its
   files or conflicted.
5. Remove that worktree by explicit path.

Parked tasks (waiting on the user) do not use a slot. Keep running everything
that does not depend on them; stop only when every path needs the user.

### 5. Handle trouble

- **Gate or question:** park the task, ask the user, pass the answer to the
  sub-agent. Deferrals get no question: fix in the PR or hold the PR.
- **Sonnet fails or stalls:** stop it and hand the worktree to an Opus agent
  that decides whether to keep or reset the work. Park if Opus also fails.
- **Plan was wrong:** reorder or serialize automatically and log it. Ask the
  user before any scope change (split/merge bundles, drop a task, new issue).
- **New Concern/Idea/Bug from a sub-agent:** it is filed under the Epic by the
  normal rules. Do not work it without asking. If it blocks an original task,
  say so plainly and let the user choose whether to add it to the plan.

### 6. Report

List completed (PR, merge), parked, excluded, plan changes, and new issues
(type, producing task, blocking or not). Do not close the Epic.
