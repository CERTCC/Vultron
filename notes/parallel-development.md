---
title: "Parallel Agentic Development: GitHub Issue-Based Coordination"
status: active
description: >
  Design decisions and implementation guidance for coordinating multiple
  parallel AI agents and human developers via GitHub Issues. Covers the
  issue hierarchy, label taxonomy, task claiming protocol, size labeling,
  orphan recovery, skill updates, and the two paths through GitHub Project #24
  (Schedule on Epics; Status and PR ship stage mirrored from facts).
related_specs:
  - specs/parallel-development.yaml
related_notes:
  - notes/agentic-workflow.md
  - notes/agents-md-structure.md
  - notes/devcontainer-tooling.md
  - notes/git-workflow-pitfalls.md
---

# Parallel Agentic Development: GitHub Issue-Based Coordination

## Overview

The project has shifted from a single-developer, file-based task list
to a GitHub Issue-based coordination model that
supports multiple parallel AI agents and human developers.

**Formal requirements**: `specs/parallel-development.yaml` (PAD groups).

**Distinct from agentic readiness** (`specs/agentic-readiness.yaml`):
`agentic-readiness.yaml` is about making the Vultron *protocol code itself*
integrable with external agentic tools (MCP adapter, OpenAPI, CLI). This file
is about the *development workflow* — how multiple agents coordinate while
building Vultron.

---

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| What is the task coordination primitive? | GitHub Issues | Native assignment, labels, PR linking, dependency notation — no new infra |
| What is the authoritative priority ordering? | GitHub Project #24 Schedule field, **on Epics only** | Live board in the browser; single source of truth; no file to maintain. Priority is decided per body of work: a child's own value could only restate its Epic's or silently differ, and skills could not tell deliberate from drifted (PAD-02-001) |
| What gives a non-Epic issue its priority? | Its nearest Epic ancestor's tier; every non-Epic issue has one | An issue with no Epic ancestor has no priority signal at all, so "no Epic ancestor" *is* untriaged. Small unrelated work goes under long-lived catch-all Epics (PAD-01-007) |
| How are tasks claimed? | GitHub creates a branch linked to the issue (`<prefix>/<N>-slug`); the agent checks it out | A branch created only in a local clone locked nothing across machines and was invisible to the sweeper until PR time. Creating the branch on GitHub fails if it exists, so the lock is real everywhere (PAD-04-001) |
| Should there be a `claimed` label? | No — and the board `Status` is a **mirror**, not a second source | A hand-kept copy drifts from branch state. `Status` is recomputed from facts, and no agent decides claimability from it, so drift is cosmetic and self-healing (PAD-16-002/003) |
| Does an Epic's tier affect an issue's `Status`? | No — the tier orders selection among `Ready` issues only | "Could this be started?" and "should it be started now?" are different questions. Retiering an Epic changes no child's Status (PAD-16-006) |
| What does `In Review` mean? | An open, non-draft PR closes the issue: OK to run `pr-ship` | Review is agent-driven. A draft PR keeps the issue `In Progress`, and marking it ready is the author's "done" signal (PAD-16-008/009) |
| Where does ship-pipeline progress live? | On the PR, as a `Ship stage` board field set by `pr-ship` | One bundle PR closes several issues, so copying stages onto issues multiplies writes. `pr-ship` progress was in gitignored local files no other session could see (PAD-17) |
| When does an Epic close? | Automatically, when its last sub-issue closes | "All children closed" is reached only when the work and its planning are done; later work belongs to a new Epic. The `Completed` Schedule value is retired (PAD-01-008) |
| Stale-claim threshold | 3 days since last branch commit | Short enough to keep the queue clean; tune if agent sessions are longer. No claim went stale in the four months to 2026-09, so recovery stays manual and nothing more is built for it |
| Diff-size thresholds | Calibrated to this repo's own merged-PR distribution, not convention — see `pr-size --table` | Measured over the 692 PRs merged 2026-07-22..2026-09-22 (the window every figure on this page refers to): the borrowed ≤50/51–300/301+ convention put 46% of them in `size:L` across two orders of magnitude, and `size:S` was correct 24% of the time. Merged diff size here is lognormal, median 258 lines, **no natural clusters** — so the cuts are a review-budget policy, not a discovered boundary |
| Why a fourth band? | `size:XL` above 1200 lines | Review findings hold at ~4.5 per 1000 diff lines from 200 through 1000, then fall to 3.5 / 2.7 / 1.5. Defect density does not drop threefold in big PRs, so the falling detection rate is **review saturation** — XL means "review probably did not cover this" |
| Does `size:XL` exist as an AC estimate? | No — measurement only | An issue predicted bigger than L is a decomposition signal. XL is a retrospective finding, and "estimated L, landed XL" is the signal worth keeping |
| Who applies the measured label? | The `pr-size-label` workflow, not an agent | The rule lived in skill prose alone and 40% of merged PRs carried no `size:` label. A prose-only rule degrades at that rate |
| Where do the band values live? | One table in `vultron/metadata/planning/size_bands.py` | They were restated in prose in eight places and computed in none. A threshold a reader can retype is a threshold that drifts |
| Two-pass code review? | Single-pass with [BLOCKING]/[ADVISORY] tags | Same signal, less process theater; build agent acts on tags |
| Where do `update-plan` gap findings go? | GitHub Issues (added to Project #24) | Consistent with the GitHub Issues model |
| Is a bundle one PR or several? | One PR closing every member | Getting more than one issue done per PR *is* the point of bundling; amortizes one context load, one branch, one review |
| How are bundle members chosen? | Eligibility, then fit: `issueType`, `Schedule` tier, `size:` budget | Eligibility answers "can this be worked at all", not "does it belong with these" (PAD-15) |
| Is thematic coherence scored? | No — stated as one sentence by the agent; the tool emits hints only | Cutting by superficial theme rather than design grain produces plausible-but-wrong work units (`calve-epics`) |

---

## Issue Hierarchy

```text
Epic Issue                           ← carries Schedule; no Status
  └── Task Issue                     ← carries Status; no Schedule
        └── Subtask Issue            ← atomic PR-sized chunk (leaf = claimable)
```

Ideas, Concerns and Bugs sit under an Epic the same way a Task does. An Epic
nested under another Epic keeps its own Schedule, and its children take the
nearest Epic's tier.

Use minimum depth. Many Epics will have leaf Tasks with no Subtasks.

---

## Label Taxonomy

| Label | Applied by | Meaning |
|---|---|---|
| `size:S` / `size:M` / `size:L` | Agent at issue creation (AC estimate); `pr-size-label` CI at PR open (measured diff) | Bands live in one table — `pr-size --table`; semantics in `.agents/skills/shared/sizing.md` |
| `size:XL` | `pr-size-label` CI only | **Measurement-only.** Review findings per 1000 diff lines halve above this floor, so it marks a PR review could not cover, not merely a big one. No AC count reaches it — an issue that large is decomposed (PAD-05-012) |
| *(no `size:` label)* | — | **Unmeasured, not small.** Bundle selection weights it as the largest *bundlable* size, so guessing small cannot fail open (PAD-15-005). `size:XL` is refused outright instead of weighted (PAD-15-011) |
| `stale-claim` | Stale-claim sweeper (GH Actions) | Orphaned claim; skip until human clears |
| `needs-info` | Anyone | **The only hold**: waiting on a person or decision. Keeps the issue out of `Ready` (PAD-16-004/005) |
| `ready-for-human` | Anyone | `Ready`, but a human does it: agent selection skips it (PAD-16-007) |
| `needs-decomposition` | `create-epic` | Epic with no sub-issues yet; input to `plan-issue` |
| `needs-rebase` | Build agent | PR or task branch has merge conflicts that must be rebased |
| `specs-notes` | ingest-idea, learn | Docs-only PR containing only specs/ and notes/ changes |
| `concern` | process-concerns, new-item, ingest-concern | Technical risk, debt, or fragile area |

**Note**: `group:<name>` and `group:unscheduled` labels were retired in June
2026. Priority grouping is now tracked via GitHub Project #24 Schedule field
and Epic sub-issue relationships instead of labels.

`docs/agents/triage-labels.md` also lists `needs-triage`, `ready-for-agent`
and `wontfix`, which came with an imported skill set. None is used: untriaged
means "no Epic ancestor", `Ready` is computed, and "will not be actioned" is
GitHub's "not planned" close reason (PAD-16-010). Their retirement is tracked
in #3717.

---

## Bundle Selection and Execution

A **bundle** is 1–5 issues worked in one PR that closes every member. The
normative contract — the two selection stages, the three fit signals and their
authorities, and the execution rules — lives in
[`.agents/skills/shared/bundling.md`](../.agents/skills/shared/bundling.md), and
the requirements are PAD-15. Mechanics are in `vultron/metadata/planning/`
(`uv run bundle-fit`), so no skill re-derives the rules in prose.

The trap this replaced (ISSUE-3482): eligibility filters answer *can this issue
be worked at all*, which is a different question from *does it belong with these
four*. Selecting on eligibility alone proposed an `Idea`, a `Someday` `Concern`
and two `size:L` Tasks as one bundle, because all four were open, unassigned,
unblocked leaves. Two of the three missing signals were already spec-mandated
authorities — `issueType` and the Project #24 `Schedule` field — and the third
(`size:`) was on 91% of open Tasks. **A selector that reads only its filter
predicates ignores the authorities its own project already established.**

Sub-issue list order is manual drag-order. It is a tie-breaker, never a
priority signal — PAD-03-001 puts priority on the Epic's `Schedule` field, and
a leaf's tier is its nearest Epic ancestor's (PAD-15-003). A leaf's own
`Schedule` value is drift by definition and is never read. Holding back one
member of an active Epic is done by moving it to a separate Epic (as #3689
does for deferred infrastructure work) or with `needs-info`, not with a
per-leaf tier. Until #3710 and #3711 land, selectors still read a leaf's own
value and `sync-epic-schedules.sh` still raises leaves to their Epic's tier.

## Task Claiming Protocol

```text
1. Query Project #24 → identify first Epic in the Focus tier, else the Now tier
2. Query GitHub: open leaf Issues that are sub-issues of that Epic,
   no stale-claim, no needs-info, no ready-for-human, unassigned
3. Apply fit (type / Epic's Schedule tier / size budget) → pick the member or bundle
4. Have GitHub create <prefix>/<issue-number>-<slug> linked to the issue
   (what the issue's "Create a branch" button does), then check it out
   → if the branch already exists on GitHub: abort (issue is taken)
5. gh issue edit <N> --add-assignee @me; set Status = In Progress
6. gh issue comment <N> --body "Claimed by <agent-session> on branch <branch>"
7. Implement, validate, code-review (address [BLOCKING] findings),
   pushing the branch at each checkpoint (PAD-04-004)
8. git fetch origin main && git rebase origin/main
9. git push
10. gh pr create --title "..." --body "Closes #<N>\n\n..."
    → a draft PR keeps the issue In Progress; a ready PR moves it to In Review
    → the pr-size-label workflow measures the diff and labels the PR
```

Steps 4, 5 and 7 describe the target (PAD-04 as amended). Today
`claim-issue.sh` still creates the branch locally and sets no `Status`; #3714
tracks the change.

---

## Pre-PR Code Review

The `code-review` agent runs once before the PR is opened. It tags every
finding:

- `[BLOCKING]` — bugs and security issues. The `build` agent MUST fix all
  of these before opening the PR, then re-run the review to confirm.
- `[ADVISORY]` — style and quality. Logged in a PR comment after the PR
  is opened; do not block.

This is a single review pass, not two sequential passes. The tag is the
signal; the build agent acts on it.

---

## Stale Claim Recovery

```text
Sweeper (weekly or on-demand):
  For each Issue where:
    - assigned (claimed)
    - claim branch exists on GitHub (any claim prefix: task/, bug/, plan/, …)
    - no open PR for that branch
    - last branch commit > 3 days ago
  → add stale-claim label
  → post comment: "Orphaned claim on branch <branch>. Human review needed."

Human remediation:
  1. Review / delete orphaned branch
  2. Unassign the Issue
  3. Remove stale-claim label
  → Issue is claimable again
```

A stale claim stays `In Progress` with the `stale-claim` marker. The human
chooses whether to resume it (an agent checks out the existing branch and
continues) or release it (steps above). Stale claims have been rare, so this is
deliberately left manual. Today the sweeper scans only `task/*` branches and
cannot see a claim that was never pushed; #3714 widens it to every prefix.

---

## Merge Conflict Recovery

```text
PR has conflicts:
  1. git fetch origin main && git rebase origin/main
     ├── Rebase succeeds → git push --force-with-lease; CI re-runs
     └── Rebase fails
           → gh pr comment: explain conflict
           → gh pr edit --add-label needs-rebase
           → Stop; wait for human to resolve
```

No proactive area-overlap detection at this stage. At 2–4 developers,
PR-time detection is sufficient.

---

## Shared `.git` and Worktree Pruning (Danger)

In this setup the `.git` **common directory is shared across multiple
environments** — host macOS checkouts and one or more dev-container checkouts
mount the same `.git`. Each worktree checkout may live at a path that only
*one* of those environments can resolve (e.g. `/workspaces/vultron_clyde`
exists only inside a container; `/Users/adh/dev/vultron_blinky` exists only on
the host).

**Never run `git worktree prune`, `git gc`, or any pruning command.** `prune`
walks `.git/worktrees/*` and deletes the admin metadata for any worktree whose
checkout path is not resolvable *from the current environment*. Because sibling
environments' paths never resolve locally, prune silently destroys the admin
dirs (`gitdir`, `commondir`, `HEAD`, `index`) of **live** worktrees owned by
other containers or the host — not just genuinely stale ones. From the host,
container worktrees always appear `prunable`; from a container, host worktrees
always appear `prunable`. **`prunable` here means "path not visible from here,"
not "safe to delete."** Leave such entries alone and confirm with the human
before removing any worktree.

### Recovery after an erroneous prune

Refs and objects are never touched by prune, so no commits are lost — only the
per-worktree admin metadata. `git worktree repair` **cannot** recreate a fully
deleted admin dir; rebuild each one by hand, run **from the environment that
can see that checkout**:

```bash
# For each affected worktree <path> that was on branch <branch>:
#   (find the authoritative admin path from the worktree's own .git file)
admin=$(sed -n 's/^gitdir: //p' "<path>/.git")   # e.g. .../.git/worktrees/<id>
mkdir -p "$admin"
printf '%s/.git\n' "<path>"              > "$admin/gitdir"
printf '../..\n'                         > "$admin/commondir"
printf 'ref: refs/heads/%s\n' "<branch>" > "$admin/HEAD"   # or a 40-char SHA if detached
git -C "<path>" reset --mixed            # rebuilds the index only; leaves working-tree edits intact
```

Then `git worktree repair` (now that admin dirs exist) and `git worktree list`
to confirm. Recover the branch mapping from `git worktree list` output captured
*before* the prune, or from open PRs; if a worktree had moved branches,
`git -C <path> checkout <correct-branch>` afterward — no data is lost either way.

---

## Project #24: Two Paths

GitHub Project #24 ("Vultron Planning") carries two independent paths. Each
field has one owner, and no item carries both.

| | Schedule | Status |
|---|---|---|
| Answers | Which body of work matters now | Where this piece of work stands |
| Lives on | Epics only (PAD-02-001) | Every non-Epic issue (PAD-16-001, PAD-16-012) |
| Values | Someday → Later → Next → Now → Focus | Backlog → Ready → In Progress → In Review → Done |
| Set by | A human (or `review-priorities`), deliberately | Mirrored from facts; never set to a value the facts don't produce (PAD-16-002) |

Open non-draft PRs are also board items, with a third field, `Ship stage` (PAD-17).

### Status is a mirror

Each `Status` value restates a fact that lives elsewhere, and the first rule
that matches wins:

| Status | Fact | Spec |
|---|---|---|
| Done | The issue is closed, for any reason | PAD-16-010 |
| In Review | An open, **non-draft** PR closes it: OK to run `pr-ship` | PAD-16-009 |
| In Progress | Claimed (assignee plus its own linked branch, or its bundle's), with no ready PR | PAD-16-008 |
| Ready | The conditions below hold | PAD-16-004/005 |
| Backlog | Anything else | PAD-16-011 |

`Ready` means *could be started*, judged from the issue's own facts. The
meaning depends on the type, and a board view grouped by type keeps the two
apart:

- **Ready to build** (Task, Feature, Bug): open, unassigned, a leaf, no claim
  branch, has an Epic ancestor, carries `- [ ] AC-N:` lines, every blocker
  closed, no `needs-info`.
- **Ready to plan** (Idea, Concern): open, unassigned, no claim branch, has an
  Epic ancestor, no `needs-info`.

The Epic's tier is deliberately absent. It decides the order in which skills
pick among `Ready` issues and which tiers they consider, so planning a
`Next`-tier Idea early, or fixing a Bug under a `Later` Epic, is an ordinary
choice and not a rule violation (PAD-16-006). The cost is that the board cannot
filter on "Ready under a Now Epic", because Projects cannot filter on a
parent's field. Grouping the `Ready` column by parent Epic recovers most of it.

A mirror can drift. Because skills decide claimability from the underlying
facts and never from `Status` (PAD-16-003), a drifted value misleads only a
human reading the board, and recomputing repairs it. Writing `In Progress` at
claim time is fine, since it is the value the facts produce.

### PR ship stage

`pr-ship` progress is otherwise kept in gitignored `.claude/pr-*.json` files
that no other session can see. The `Ship stage` field (`Awaiting ship`,
`Triage`, `Execute`, `Verify`, `Needs you`, `Ready to merge`) starts at
`Awaiting ship` when a non-draft PR is opened or marked ready (PAD-17-003),
then is set by `pr-ship` as it enters each phase or pauses at a gate
(PAD-17-002). It is cleared when the PR returns to draft, closes, or merges
(PAD-17-004). The issue stays `In Review` for the whole pipeline: pipeline detail belongs to the PR,
because one bundle PR closes several issues.

### Epics

An Epic has a Schedule tier and no Status. Its progress is GitHub's sub-issue
progress field, and a `needs-decomposition` label marks one that still needs
planning. It closes automatically when its last sub-issue closes (PAD-01-008).
New work that arrives afterwards goes into a new Epic.

### Triage

Triage has two inputs: Epics at `Someday` (or with no Schedule), which need a
tier, and non-Epic issues with no Epic ancestor, which need a parent
(PAD-12). A new non-Epic issue gets no Schedule value (#3711 removes today's
`Someday` default), and `manage_github_issue.sh` already refuses to create one
without `--parent`.

### Views

Views are board settings, not process. Their target set is tracked in #3718:

- **Schedule**: Epics by tier, with sub-issue progress.
- **Issues**: `Status` columns, grouped by issue type (plan vs. build).
- **PRs**: grouped by `Ship stage`.
- **Needs you**: PRs at `Needs you` or `Ready to merge`, `needs-info` issues,
  `Ready` issues with `ready-for-human`, and `stale-claim` issues.

### Current state

The process above was settled on 2026-09-25. Epic #3708 tracks its
implementation, and until its children land, the board still differs from the
target in these ways:

- Non-Epic issues carry Schedule values, and `bundle-fit` (with
  `.agents/skills/shared/bundling.md`, which documents it) still lets an
  explicit leaf tier beat its Epic's (#3710).
- Nothing writes `Status`.
- PRs are not board items.
- Claims are created locally.

### Previous conventions (archived)

Before June 2026, issues used `group:<slug>` labels to mark priority group
membership and `group:unscheduled` to mark items not yet in `PRIORITIES.md`.
These labels have been deleted. Do not recreate them. Until 2026-09, every
issue carried its own Schedule value and new issues defaulted to `Someday`.

---

## Open Questions / Future Work

- **Diff-size threshold tuning**: The 50/300 line thresholds are a starting
  point. Revisit after the first 20–30 PRs to calibrate against observed
  complexity.
- **Mirror mechanics**: which `Status` transitions GitHub Projects' built-in
  workflows can own (for example, "item closed → Done") and which need the
  reconcile job is decided in #3713.
- **Loop-agent construction**: The revised `build` skill (issue selection +
  PR creation) is the foundation for a fully autonomous learn/plan/build loop
  agent. Design of that agent is deferred.

---

## Load When

Load this file when:

- Adding or modifying skill SKILL.md files (`build`, `ingest-idea`,
  `review-priorities`, `update-plan`, `study-project-docs`)
- Changing how work is selected or bundled (`propose-bundle`, `bundle-fit`,
  `.agents/skills/shared/bundling.md`)
- Creating GitHub Issues for new work items
- Recalibrating the `size:` bands, or touching anything that reads them
  (`vultron/metadata/planning/size_bands.py`,
  `.agents/skills/shared/sizing.md`, `.github/workflows/pr-size-label.yml`)
- Implementing or modifying the stale-claim sweeper GitHub Actions workflow
- Debugging task-selection or claiming behavior in the `build` skill
- Changing anything that reads or writes Project #24 fields (`Schedule`,
  `Status`, `Ship stage`), or adding a board view
