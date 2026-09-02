---
title: Git, Branch, and PR Workflow Pitfalls
status: active
description: >
  Pitfalls in the git and GitHub side of agentic development: rebase failures
  that are false positives, branch-freshening recovery, integration branches
  for related fix PRs, issue claiming preconditions, ADR number races, and the
  `Closes #N` footer rules. These are process pitfalls, not code pitfalls.
related_notes:
  - notes/parallel-development.md
  - notes/agentic-workflow.md
  - notes/specs-vs-adrs.md
  - notes/devcontainer-tooling.md
related_specs:
  - specs/project-documentation.yaml
---

# Git, Branch, and PR Workflow Pitfalls

Migrated out of the root `AGENTS.md` pitfalls list. Root keeps one-line
pointers; the full write-ups live here.

## `git rebase` "local changes would be overwritten" With a Clean Working Tree

This error can be a false positive when the rebased branch diverges far from
main and both sides touched the same files. Fix: cherry-pick onto a fresh branch
from `origin/main` (`git checkout -b temp origin/main && git cherry-pick <hash>`)
instead of rebasing. The error message is misleading — it is NOT evidence of
uncommitted work. See also: single large-commit branches with 70+ files trigger a
sequencer duplicate-pick bug; the cherry-pick workaround resolves both variants.
If `freshen-branch.sh` took this path and then hit a conflict, it can leave the
temp branch behind — delete it by hand. *Fixed in #1784: the script now guards
the cleanup checkout.*

Sources: ISSUE-1518, ISSUE-1504, ISSUE-1784

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

## Pre-commit Hooks Interfere with `git rebase` in Worktrees

Use `manage_worktree.sh ensure-synced`. Manual fix: `git reset --soft origin/main`
then `git -c core.hooksPath=/dev/null commit`.

## Worktree Sync Checks Need Ancestry Verification

Use the `ensure-synced` flow, not raw `git rebase origin/main`. See
[notes/parallel-development.md](parallel-development.md).

## A Conflict-Free Merge Is Not a Working Merge — Run Tests After Every Catch-Up

Git merges text; it cannot detect semantic breakage. When a branch retires an API,
`main`'s new callers merge cleanly and fail at runtime. Always run the full unit
tier after resolving conflicts — "0 conflicts" is no signal at all. Additionally:
when a conflict is in a file that was **split or renamed** on `main`, also check
the new location for changes your branch added to the old location; file splits do
not show up in conflict markers. For long-lived branches, sweep for each retired
API name in `vultron/` and `test/` via `grep` rather than waiting for failures.

Source: ISSUE-2238

## Multiple Related Fix PRs Targeting a Shared CI Suite Must Use an Integration Branch

When 3+ related bug fix PRs are open simultaneously and all affect the same CI
suite (e.g. Demo Integration), open a single `fix/<area>` integration branch off
`main` and target all child PRs there. Run the full CI suite against the
integration branch after each child PR merges into it. Merge the integration
branch to `main` only when the full suite is green. Racing parallel PRs to `main`
means each PR can only confirm its own scenario passes — none can confirm it
hasn't perturbed other currently-passing scenarios.

Note that **`create-pr` cannot target integration branches** — the skill always
targets `origin/main`. Use `gh pr create --base <integration-branch>` directly.

Sources: CONCERN-2137, ISSUE-2030

## `claim-issue.sh` Requires the Current Branch to Be Up to Date with `origin/main`

The script checks that your branch is ancestor-or-equal to `origin/main`. If
`main` has moved since you last synced, the check fails with a confusing error.
Run `manage_worktree.sh ensure-synced` or `git fetch origin && git rebase
origin/main` first. The presence of an existing task branch for the same issue
may also indicate the issue was started (or completed) via another PR — check
`git log --oneline origin/main | grep -i "<issue title>"` before assuming
nothing was done.

Source: ISSUE-2017

## Re-Check ADR Number Immediately Before Merge — `adr-index` Enforces Uniqueness

ADR numbers are claimed from `docs/adr/index.md` at authoring time and must be
unique. A parallel PR can claim the same number between when you check and when
you merge. `adr-index` now has a uniqueness check that fails at commit/CI time if
two ADRs share a number. To avoid a blocked merge: re-read `docs/adr/index.md`
immediately before creating the commit that adds a new ADR; if the number is
already taken, increment and update the ADR filename and `index.md` entry.

Source: CONCERN-2321

## Verify Every Acceptance Criterion Against `origin/main`, and Always Add `Closes #N`

These were three separate pitfall entries with one shared root cause: the
`Closes #N` footer is the only thing that closes an issue automatically, so a PR
that omits it leaves a fully-implemented issue OPEN — and the next agent to pick
that issue up re-implements work that already landed.

Both halves of the rule:

- **Before implementing**, verify each acceptance criterion against
  `origin/main`. An issue may already be satisfied in whole or in part by a prior
  PR that shipped without a closing footer. Implement only what is still unmet.
  Use `git log -S "<fix string>" -- <file>` against `origin/main` to confirm.
  The pre-claim gates enforce this before branching: see
  `.agents/skills/build/SKILL.md` Phase 2 § "Pre-claim AC verification gate" and
  `.agents/skills/bugfix/SKILL.md` Phase 1 § "Pre-claim defect verification".
- **When opening the PR**, include `- Closes #N` at the top of the body, one per
  line. This applies to docs and `learn` PRs too: when a docs PR fixes a bug as
  a side effect, the footer is still required.

Sources: ISSUE-1467, ISSUE-1484, ISSUE-1510, ISSUE-1787, ISSUE-2290

## Fix One, Miss the Siblings: Scan Peer Files Before Closing a Bug

When a bug is fixed in one location, always search for the same structural
pattern in sibling files and scenarios before closing. Unscanned peer instances
surface as separate backlog issues, each requiring its own investigation cycle.
The `bugfix` skill mandates this scan at Phase 2d; see
`.claude/skills/bugfix/REFERENCE.md` § "Sibling Scan Pattern".

Source: CONCERN-2413
