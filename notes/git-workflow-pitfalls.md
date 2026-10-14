---
title: Git, Branch, and PR Workflow Pitfalls
status: active
kind: guidance
description: >
  Pitfalls in the git and GitHub side of agentic development: false-positive
  rebase failures, syncing a worktree, catch-up merges that break or revert
  work silently, integration branches for related fix PRs, ADR number races,
  verifying acceptance criteria before claiming, the `Closes #N` footer, and
  never merging on red.
related_notes:
  - notes/parallel-development.md
  - notes/agentic-workflow.md
  - notes/specs-vs-adrs.md
  - notes/devcontainer-tooling.md
  - notes/flaky-tests.md
  - notes/ci-workflow-authoring.md
related_specs:
  - specs/project-documentation.yaml
  - specs/build-workflow.yaml
  - specs/parallel-development.yaml
---

# Git, Branch, and PR Workflow Pitfalls

## `git rebase` "local changes would be overwritten" With a Clean Working Tree

The error is a false positive when the branch diverges far from `main` and both
sides touched the same files; it is not evidence of uncommitted work. A large
single-commit branch also trips a sequencer duplicate-pick bug. Cherry-pick
onto a fresh branch from `origin/main` instead of rebasing
(`git checkout -b temp origin/main && git cherry-pick <hash>`); `create-pr`
does this through `freshen-branch.sh` (ISSUE-1518).

## Sync a Worktree Through `sync-check.sh`, Not a Raw Rebase

Run `.agents/skills/shared/sync-check.sh`, which uses the `manage-worktree`
`ensure-synced` flow (ancestry-checked) when it is installed. Raw
`git rebase origin/main` in a worktree can trip pre-commit hooks mid-rebase.
Never rebase a branch with an open PR: merge `main` into it (PAD-11-001). See
[parallel-development](parallel-development.md).

## A Conflict-Free Merge Is Not a Working Merge — Run Tests After Every Catch-Up

Git merges text, not meaning. When a branch retires an API, `main`'s new
callers merge cleanly and fail at runtime, so "0 conflicts" is no signal: run
the unit tier after every catch-up merge. When a conflict lands in a file that
`main` split or renamed, check the new location for changes your branch made to
the old one. On a long-lived branch, grep `vultron/` and `test/` for each
retired API name (ISSUE-2238).

## A Catch-Up Merge Can Silently Revert a Prior PR's Wiring

A conflict resolution that keeps "our" side can restore a call site that a
prior PR moved elsewhere, and every test still passes when both shapes produce
the same effect (ISSUE-2789).

- **Review a catch-up merge by diffing the resolved file against both
  parents**, not only by running the suite.
- **When a refactor's point is *where* a side effect happens**, assert the
  structure, not only the effect: spy the tree factory, and
  `assert not hasattr(module, "<retired helper>")`. Grep for callers of a new
  factory before closing the issue; one with only test callers is a red flag.

## An Issue That Names a Missing File Is Making a Claim About the Path

An issue written before a feature landed can name a plausible but wrong path.
The file is genuinely absent while the behaviour already ships elsewhere, and
creating it duplicates the feature. Grep the bare filename repo-wide and check
`notes/` cross-references for the real path before creating the file
(ISSUE-2789).

## Multiple Related Fix PRs Targeting a Shared CI Suite Must Use an Integration Branch

When three or more related fix PRs affect the same CI suite (for example Demo
Integration), open one `fix/<area>` integration branch off `main`, target every
child PR at it, and run the full suite after each child merges. Merge the
integration branch to `main` only when the suite is green. Parallel PRs to
`main` can each confirm only their own scenario (CONCERN-2137).

`create-pr` always targets `main`; open a child PR with
`gh pr create --base <integration-branch>` directly.

## Re-Check the ADR Number Immediately Before the Commit That Adds an ADR

A parallel PR can claim the same ADR number between your check and your merge,
and `adr-index` refuses to write an index with a duplicate number. Re-read
`docs/adr/index.md` just before committing a new ADR; if the number is taken,
rename the file to the next free number and re-run `uv run adr-index`
(CONCERN-2321).

## Verify Every Acceptance Criterion Against `origin/main`, and Always Add `Closes #N`

The `Closes #N` footer is the only thing that closes an issue automatically. A
PR that omits it leaves delivered work OPEN, and the next agent re-implements it
(#1907).

- **Before claiming**, verify each acceptance criterion against `origin/main`
  (`git log -S "<string>" -- <file>`) and implement only what is still unmet.
  `build` Phase 2 § "Pre-claim AC verification gate" and `bugfix` § "Pre-claim
  defect verification" enforce this.
- **The `build` gate only sees `- [ ] AC-N:` lines.** Prose or unnumbered
  criteria skip it, so check those issues by hand before claiming.
- **When opening the PR**, put `- Closes #N` at the top of the body, one per
  line, on docs and `learn` PRs too.
- **An existing task branch for the issue** may mean another PR already did the
  work; check `origin/main` before assuming nothing was done.

## Fix One, Miss the Siblings: Scan Peer Files Before Closing a Bug

Search sibling files and scenarios for the same structural pattern before
closing a bug; an unscanned peer becomes its own backlog issue and its own
investigation. `bugfix` mandates the scan; see
`.agents/skills/bugfix/REFERENCE.md` § "Sibling Scan Pattern" (CONCERN-2413).

## Never Merge on Red; a Red `main` Gets One Fix PR

A PR with any failing check is not mergeable. "Pre-existing", "unrelated",
"flaky" and "passed on rerun" are claims, not evidence
(`.agents/skills/shared/completeness-doctrine.md` § "Never Merge on Red";
ISSUE-4189).

- **A red `main` gets exactly one fix PR.** Every other PR waits for it to
  land, then re-runs CI against the fixed base; none merges past the red and
  none opens a second fix for the same failure. Never rebase an open PR onto it
  (PAD-11-001).
- **A flaky check may be re-run once, and only when it is already tracked**:
  an open `flaky-test` issue holds a reproduction (see
  [flaky-tests](flaky-tests.md)) and the PR body names it. Without one, file it
  first; the PR stays held until the check is green on its own or the cause is
  fixed.
- **Hooks are not skipped** (`--no-verify`, `SKIP=`). The one exception is the
  devcontainer `actionlint` hang ([devcontainer-tooling](devcontainer-tooling.md)).
