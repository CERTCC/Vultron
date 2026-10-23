# Parallel Agentic Development — Design Notes

## Context

This document captures a design session on migrating the Vultron project's
development workflow from a single-developer, skills-based model
(learn → plan → build) toward a parallel agentic model that supports
multiple AI agents and human developers working independently while
maintaining a PR-based integration workflow.

---

## Problem Statement

The current `IMPLEMENTATION_PLAN.md`-centred workflow is a personal todo list
scaled up. It works well for one developer or agent but breaks down under
parallel use because:

- There is no distributed task-claiming mechanism.
- Dependencies are expressed as prose, not a queryable graph.
- The `build` skill commits locally without opening a PR.
- Almost no tasks have corresponding GitHub Issues, so there are no native
  assignment or lock primitives.
- Two systems (plan file + GitHub Issues) are partially in use with no clear
  authority boundary.

---

## Target Model

### Participants

The workflow must support:

- Multiple AI agents (e.g., Copilot cloud agent sessions) running in parallel.
- Human developers working alongside agents.
- The existing skills (`learn`, `plan`, `build`, `ingest-idea`,
  `review-priorities`) reused and extended — not replaced.
- A future "learn/plan/build loop" composed from existing skills into
  autonomous custom agents.

### Core Principle

**GitHub Issues are the coordination primitive.** The Issue tracker provides
native assignment, labels, PR linking, and dependency notation — all the
primitives needed for distributed task coordination without introducing new
infrastructure.

---

## Issue Hierarchy

Tasks are organized in up to three levels. Not every level is always needed;
use the minimum depth that results in "right-sized" leaf items.

| Level | GitHub role | Naming | When used |
|---|---|---|---|
| Priority Group (Epic) | Parent issue | Maps to a roadmap group in PRIORITIES.md | Always |
| Task | Child of Epic | Represents a coherent unit of work | When Epic is too large for one PR |
| Subtask | Child of Task | Atomic PR-sized chunk | When Task needs further decomposition |

Leaf issues (those with no children) are the claimable work units.

---

## Priority and Ordering

**`PRIORITIES.md` remains the authoritative ordering document.** It is
human-readable, carries rationale, and is freely reorderable without
touching the GitHub API.

- Each Issue carries a `group:<name>` label matching its group name in
  PRIORITIES.md.
- The `build` skill reads PRIORITIES.md once at task-selection time to
  determine the current top priority group, then queries GitHub for open,
  unblocked Issues with that `group:` label.
- Reprioritization = one edit to PRIORITIES.md (reorder group names) + a
  label change on any affected Issues.
- **Agents MUST NOT write to PRIORITIES.md.** Only humans (and the
  `review-priorities` skill) may modify it.

### Unscheduled Issues

Issues created by `ingest-idea` or by agents during development are tagged
`group:unscheduled`. They are not claimable until a human runs
`review-priorities`, slots them into PRIORITIES.md, and updates their `group:`
label.

---

## Task Claiming Protocol

When an agent selects a task to work on:

1. **Create a branch** named `task/<issue-number>-<slug>`. Branch existence
   is the hard distributed lock — if the branch already exists, the task is
   already claimed.
2. **Assign the Issue** to the triggering user (the agent's operator).
3. **Post a comment** on the Issue identifying the agent session and branch.

No named bot accounts are required. The branch is the authoritative claim
signal; assignment and the comment are for human visibility.

---

## Build Skill — Revised Flow

```text
study-project-docs
  → select unblocked leaf Issue (PRIORITIES.md group order, no stale-claim label)
  → claim: create branch + assign Issue + post comment
  → implement
  → format / lint / test
  → pre-PR code review (two-pass, see below)
  → compute diff stats → update size: label
  → open PR with "Closes #N"
  → if size:S and CI green → auto-merge eligible
```text

### Pre-PR Code Review (Two-Pass)

The `code-review` agent runs before the PR is opened:

- **Pass 1 — Blocking**: bugs and security issues. The agent MUST fix all
  findings before continuing.
- **Pass 2 — Advisory**: style and quality findings. Logged in a PR comment;
  do not block.

---

## Size Labeling

Size is computed in two phases:

1. **At issue creation**: AC (acceptance criteria) checkbox count sets the
   initial label.
   - 1–2 ACs → `size:S`
   - 3–6 ACs → `size:M`
   - 7+ ACs → `size:L`

2. **At PR open**: the agent measures the actual diff (files changed, lines
   added/removed) and updates the label — including downgrading if the work
   was smaller than anticipated. The final label at PR-open time governs
   auto-merge eligibility.

### Auto-Merge Rules

| Size | Condition for auto-merge |
|---|---|
| `size:S` | All CI checks green + pre-PR code review passed |
| `size:M` | Human review required |
| `size:L` | Human review required |

Auto-merge for `size:S` is implemented as a GitHub Actions workflow that
checks the label, CI status, and (for docs-only PRs) CODEOWNERS authorship,
then calls `gh pr merge --auto`.

---

## Docs-Only PRs (specs/ and notes/)

`ingest-idea` creates a docs-only PR containing only `specs/` and `notes/`
changes. This PR auto-merges when:

- It carries the `specs-notes` label.
- No `.py` files are changed.
- The PR author is listed in CODEOWNERS for `specs/` and `notes/`.
- All linters pass.

This ensures spec and notes files are on `main` (and referenceable from
GitHub Issues) before any implementation work begins.

---

## `ingest-idea` — Revised Flow

```text
interview (grill-me)
  → write specs/ and notes/ files
  → open docs-only PR with specs-notes label  (auto-merges on green linters)
  → gh issue create with:
      - title and description from spec
      - group:unscheduled label
      - size: label from AC count
      - link to spec file
```text

The new Issue sits in `group:unscheduled` until a human runs
`review-priorities` to slot it into the roadmap.

---

## Orphan Recovery

### Stale-Claim Sweeper

A scheduled GitHub Actions job (weekly, or on-demand) scans for Issues that
are:

- Assigned (claimed)
- Have a `task/<N>-slug` branch
- Have no open PR
- Last commit on the branch is older than N days (suggested: 7 days)

The sweeper:

1. Adds a `stale-claim` label to the Issue.
2. Posts a comment identifying the orphaned branch and asking for human
   review.

**The `build` skill skips Issues with the `stale-claim` label.** A human
must review, clean up the branch, unassign the Issue, and remove the label
before the task becomes claimable again.

---

## Merge Conflict Recovery

When a PR has merge conflicts (e.g., two PRs landed on overlapping files):

1. The agent attempts an automatic rebase onto `main`.
2. If the rebase succeeds, the agent force-pushes the branch and CI re-runs.
3. If the rebase fails, the agent posts a comment explaining the conflict,
   adds a `needs-rebase` label, and waits for human intervention.

No proactive conflict detection (area-overlap checking) is implemented at
this stage. At 2–4 developers, merge conflicts are infrequent enough that
PR-time detection is sufficient. Revisit if hot-spot conflicts become a
recurring problem.

---

## Migration Plan

### Phase 0 — Prerequisite

Run `review-priorities` to triage and clean up `PRIORITIES.md` before
migrating tasks. Ensures no stale or mis-ordered tasks are promoted to Issues.

### Phase 1 — Hard Cutover

Use the `create-github-issues-feature-from-implementation-plan` skill (or a
bulk script) to migrate all tasks in `IMPLEMENTATION_PLAN.md` to GitHub
Issues in a single pass:

- Each task group → an Epic Issue tagged with a new or existing `group:`
  label.
- Each task → a child Issue.
- Each subtask → a grandchild Issue (where applicable).
- Dependency prose (`Blocked by TASK-X`) → `Blocked by #N` notation in
  Issue bodies.
- `size:` label from AC count.

After migration, `IMPLEMENTATION_PLAN.md` is converted to a read-only index:
a short header note that tasks have moved to GitHub Issues, with links to the
relevant Epic Issues and to `PRIORITIES.md`.

### Phase 2 — Skill Updates

Update or create the following:

| Skill / Workflow | Change |
|---|---|
| `build` | Add issue selection, claiming, PR open, size-label update, auto-rebase |
| `ingest-idea` | Add docs-only PR + Issue creation with `group:unscheduled` |
| `review-priorities` | Surface `group:unscheduled` Issues for slotting |
| `code-review` (pre-PR) | Two-pass: bugs block, style advises |
| New: stale-claim sweeper | Scheduled GH Actions job |
| New: auto-merge workflow | GH Actions: size:S + CI green → auto-merge |
| New: docs-only auto-merge | GH Actions: specs-notes label + CODEOWNERS + linters |

---

## Open Questions / Future Work

- **Threshold for stale-claim sweeper**: 7 days is a starting point; tune
  based on observed agent session lengths.
- **Diff-size thresholds for size labeling**: Define exact line-count
  boundaries (e.g., <50 lines = S, 50–300 = M, 300+ = L) and document them
  in AGENTS.md.
- **CODEOWNERS file**: Does not currently exist in the repository. Needs to
  be created before docs-only auto-merge can be enforced.
- **GitHub Projects v2**: If the team grows beyond 4 developers or
  PRIORITIES.md + labels become unwieldy, consider migrating to a Projects
  v2 board with custom fields for roadmap ordering.
- **Loop-agent construction**: The revised `build` skill (with issue
  selection + PR creation) is the foundation for a fully autonomous
  learn/plan/build loop agent. Design of that agent is deferred.
