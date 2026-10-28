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

While you run, you hold an **Epic claim**: the Epic is assigned to you, and its
open Tasks and Features are held for this run, so no other `build` takes one,
even from a later wave (PAD-19). Bugs, Ideas, and Concerns stay open to others.

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
- The Epic is already assigned: another epic run holds it, or one stopped
  without releasing it. **Refuse** and tell the user. A human releases an
  abandoned claim with `release-epic.sh` (the sweeper flags it `stale-claim`).
- More than 10 Tasks: ask permission before continuing.
- Bug: look quickly. Easy and self-contained → plan it with `bugfix`. Depends
  on a large decision → ask the user how to proceed.
- Claimed/assigned, `stale-claim`, `needs-info`, `ready-for-human`, blocked
  outside the Epic, already has a PR, date-gated, waiting on something outside
  the run, or described as a human step: **exclude and report**, with the
  reason and what would unblock it. Never wait for a date. Exclude anything
  downstream of an excluded issue too. Ask only if the user could plausibly
  want it included.

### 2. Plan (think hard)

Read each issue's full body (the Epic query returns titles only) and the code
it touches. Do not trust `blockedBy` alone: look for shared files, tests, or
constants, one task needing another's helper, and shared specs. Build
**waves** of truly independent tasks; serialize anything that overlaps.
`bundle-fit` and `shared/bundling.md` score one bundle at a time; they do not
plan waves. A bundle never mixes Tasks and Bugs. If a Task is oversized or its
parts need different review, propose a **split** into several PRs (each says
`Part of #N`; only the last says `Closes #N`; no new issues) and say why.
If the order makes an acceptance criterion moot, put the reworded criterion in
the plan. Pick each task's build model: **Opus** for multi-file,
protocol/architecture, or judgment work; **Sonnet** for mechanical work.
Every `pr-ship` agent is **Opus**.

### 3. Approve

Show the plan (waves, bundles, splits, reworded criteria, models, exclusions,
expected open worktrees). **Always wait for approval.** Start nothing before
it. A reworded criterion goes in the builder's prompt and in a comment on the
issue; never edit the issue text, and say in the PR body how it was met.

After approval and before any build starts, claim the Epic:

```bash
bash .agents/skills/shared/claim-epic.sh <EPIC>
```

If it fails, start nothing and report why. From here on, every exit path runs
step 6's release.

### 4. Execute

Write the status file, then run up to the agent cap at once. Per task:

1. Create `/tmp/wt-<issue>` from `origin/main` (never `git worktree prune`).
2. Spawn the build agent in that worktree. A Task gets
   `build <N> --epic-run <EPIC>`, which clears the hold for this run only.
   A Bug is not held, so check it first: if it is now assigned or has a claim
   branch, another agent took it. Drop it, keep going, and report it as
   "taken elsewhere". Otherwise spawn `bugfix <N>`.
3. On PR open, spawn a **fresh** agent in the same worktree to run `pr-ship`.
4. Merge only on `READY-TO-MERGE`, as soon as it arrives. Right before
   merging, check this PR, and only this PR, against current `main` from its
   worktree (its own, or a fresh one on its head) (PAD-18-009):

   ```bash
   # fresh worktree only if the PR's own is gone:
   git fetch origin <head_ref> && git worktree add --detach /tmp/wt-<issue> FETCH_HEAD
   # in that worktree:
   git fetch origin main
   bash .agents/skills/shared/merge-state.sh <pr>   # exit 1 = CONFLICTING; JSON merge_state_status BEHIND
   git merge-tree --write-tree --name-only HEAD origin/main > /dev/null   # exit 1 = conflict
   PYTHONPATH= uv run targeted-tests --base origin/main --overlap   # exit 1 = overlap
   ```

   Take the first row that matches:

   | Check | Action |
   |---|---|
   | `CONFLICTING`, `DIRTY`, or `merge-tree` exit `1` | Re-run `pr-ship` (a fresh agent; its execute phase merges `main` and resolves). The only case that needs an agent |
   | `BEHIND`, or overlap lists files | Update on GitHub and wait on the new head (block below). Exit `0`: merge. Exit `1`: re-run `pr-ship` with the failure as input. Exit `2` (timeout): wait again; never merge before green |
   | Neither | Merge |

   Merge the head that CI passed on, and only that head:

   ```bash
   gh pr update-branch <pr>                                    # BEHIND / overlap row only
   sha=$(gh pr view <pr> --json headRefOid --jq .headRefOid)   # after any update-branch
   WAIT_CI_HEAD_SHA="$sha" bash .agents/skills/shared/wait-for-ci.sh <pr>   # BEHIND / overlap row only
   gh pr merge <pr> --merge --match-head-commit "$sha"
   ```

   Read `sha` after `gh pr update-branch` and before `wait-for-ci.sh`, so a
   push that lands during the wait makes the merge fail rather than ship an
   untested head; a refused merge goes back through `pr-ship`.

   Always pass `WAIT_CI_HEAD_SHA`. Left unset, `wait-for-ci.sh` expects the
   worktree's local `HEAD`, but `update-branch` makes its merge commit on
   GitHub only, so the wait polls for a head that never comes and times out.
   In a detached worktree it checks no head at all, and the previous head's
   green run reads as a pass (#3902).

   Update at most once per merge: if `main` moves again during the CI wait,
   merge on green anyway unless GitHub now reports a conflict. Repeating the
   update on every movement is the loop ADR-0138 removed; a semantic conflict
   between files neither PR shares is caught by CI on `main` (ADR-0126).

   After a merge, leave every other open PR alone. Each gets this same check
   when its own turn to merge comes; a PR still in `pr-ship` needs no nudge,
   because its execute phase merges `main` itself on a conflict and
   `pr-verify` re-reads the live merge state.
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

Release the Epic first, on **every** stop: finished, parked on the user,
refused mid-run, or failed. Pass the report's summary:

```bash
bash .agents/skills/shared/release-epic.sh <EPIC> "<summary>"
```

Running the skill again claims the Epic again and resumes from the status file.

List completed (PR, merge), parked, excluded, taken elsewhere, plan changes,
and new issues (type, producing task, blocking or not). Add the run's net issues per
`completeness-doctrine.md` § "Net Issues: Close More Than You Open": closed,
opened by reason (`excursion` excluded), dedup/`wontfix` closures on their own
line. Report the numbers without a verdict; call out any `opened:deferred` as a
process defect. Do not close the Epic.
