---
title: "Parallel Agentic Development: GitHub Issue-Based Coordination"
status: active
kind: guidance
description: >
  How multiple AI agents and human developers coordinate through GitHub Issues:
  the issue hierarchy, label taxonomy, bundle selection, task claiming, the
  Epic claim an epic run holds, stale-claim and merge-conflict recovery, the
  shared-`.git` pruning danger, and the two paths through GitHub Project #24
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

GitHub Issues are the task coordination primitive: assignment, labels, PR
linking and blocker links need no new infrastructure. The requirements are
`specs/parallel-development.yaml` (PAD); this note gives the reasons and the
procedures.

This is the *development workflow*. Making the protocol code itself usable by
external agentic tools is `specs/agentic-readiness.yaml`, a different topic.

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| What is the authoritative priority ordering? | Project #24 `Schedule`, **on Epics only** | Priority is decided per body of work; a child's own value could only restate its Epic's or silently differ (PAD-02-001) |
| What gives a non-Epic issue its priority? | Its nearest Epic ancestor's tier | An issue with no Epic ancestor *is* untriaged; small unrelated work goes under long-lived catch-all Epics (PAD-01-007) |
| How are tasks claimed? | A branch `<prefix>/<N>-slug` that GitHub creates with `createLinkedBranch`, linked to the issue | A null `linkedBranch` means the name exists, so the lock holds across machines. `gh issue develop` exits 0 there and is no lock (PAD-04-001) |
| Is there a `claimed` label? | No; claims are facts GitHub keeps (claim branch, assignee), and board `Status` **mirrors** them | A hand-kept copy drifts; no agent decides claimability from `Status` (PAD-16-002/003) |
| How does an epic run claim its Epic? | It assigns the Epic and comments; its Tasks and Features are held until it releases | Tasks in a later wave otherwise look free; Bugs, Ideas and Concerns stay open on purpose (PAD-19) |
| Does an Epic's tier affect a child's `Status`? | No; the tier orders selection among `Ready` issues only | "Could this start?" and "should it start now?" are different questions (PAD-16-006) |
| Where does ship-pipeline progress live? | On the PR, as the `Ship stage` field | One bundle PR closes several issues (PAD-17) |
| When does an Epic close? | Automatically, when its last sub-issue closes | Later work belongs to a new Epic (PAD-01-008) |
| Stale-claim threshold | 3 days since the last branch commit | Recovery stays manual: stale claims are rare |
| Where do the `size:` bands live? | One table in `vultron/metadata/planning/size_bands.py` (`pr-size --table`) | A threshold restated in prose drifts; the module docstring gives the calibration rationale |
| Who applies the measured `size:` label? | The `pr-size-label` workflow, not an agent | A rule kept only in skill prose was skipped on a large share of PRs (PAD-05-002) |
| Is a bundle one PR or several? | One PR closing every member | One context load, one branch, one review (PAD-15) |
| Is thematic coherence scored? | No; the agent states it in one sentence | Cutting by surface theme rather than design grain produces wrong work units (`calve-epics`) |

## Issue Hierarchy

```text
Epic Issue                           ← carries Schedule; no Status
  └── Task Issue                     ← carries Status; no Schedule
        └── Subtask Issue            ← atomic PR-sized chunk (leaf = claimable)
```

Ideas, Concerns and Bugs sit under an Epic the same way a Task does. An Epic
nested under another Epic keeps its own Schedule, and its children take the
nearest Epic's tier. Use minimum depth: many Epics have leaf Tasks and no
Subtasks.

## Label Taxonomy

| Label | Applied by | Meaning |
|---|---|---|
| `size:S` / `size:M` / `size:L` | Agent at issue creation (AC estimate); `pr-size-label` CI on the PR (measured diff) | Bands: `pr-size --table`; semantics: `.agents/skills/shared/sizing.md` |
| `size:XL` | `pr-size-label` CI only | **Measurement-only**: a PR too big for review to cover. An issue that large is decomposed instead (PAD-05-012) |
| *(no `size:` label)* | — | **Unmeasured, not small.** Bundle selection weights it as the largest bundlable size (PAD-15-005); `size:XL` is refused outright (PAD-15-011) |
| `stale-claim` | Stale-claim sweeper (GH Actions) | Orphaned claim; skip until a human clears it |
| `needs-info` | Anyone | **The only hold**: waiting on a person or decision; keeps the issue out of `Ready` (PAD-16-004/005) |
| `ready-for-human` | Anyone | `Ready`, but a human does it: agent selection skips it (PAD-16-007) |
| `needs-decomposition` | `build`, `create-epic`, `calve-epics` | Epic with no sub-issues yet; input to `plan-issue` |
| `needs-rebase` | `create-pr`, `pr-execute` | PR conflicts an agent could not resolve; a human must (PAD-11-004) |
| `specs-notes` | `learn`, `plan-issue`, `decision-audit` | Docs-only PR touching only `specs/` and `notes/` |

Do not create `group:` labels: priority grouping is the Epic's `Schedule` and
its sub-issue tree. `docs/agents/triage-labels.md` also lists `needs-triage`,
`ready-for-agent` and `wontfix`; none is used (untriaged means "no Epic
ancestor", `Ready` is computed, "will not be actioned" is GitHub's "not planned"
close reason; PAD-16-010). Their retirement is #3717.

## Bundle Selection

A **bundle** is 1–5 issues worked in one PR that closes every member. The
contract (two selection stages, three fit signals, execution rules) is
[`.agents/skills/shared/bundling.md`](../.agents/skills/shared/bundling.md); the
mechanics are `uv run bundle-fit`, so no skill re-derives them in prose (PAD-15).

- **Eligibility is not fit.** Open, unassigned, unblocked leaves can still be an
  `Idea`, a `Someday` item and two `size:L` Tasks. Fit reads the authorities the
  project already has: `issueType`, the Epic's `Schedule`, and `size:`.
- **Sub-issue list order is a tie-breaker, never priority.** A leaf's tier is its
  nearest Epic's (PAD-03-001, PAD-15-003). Hold back one member of an active Epic
  by moving it to another Epic or with `needs-info`, not with a leaf tier.

## Task Claiming Protocol

```text
1. Query Project #24 → first Epic in the Focus tier, else the Now tier
2. Query its open leaf sub-issues: unassigned, no stale-claim, no needs-info,
   no ready-for-human; a Task or Feature under an assigned Epic is held by an
   epic run (PAD-19-002)
3. Apply fit (type / Epic's Schedule tier / size budget) → member or bundle
4. createLinkedBranch <prefix>/<issue-number>-<slug> from main
   → null linkedBranch: it already exists, abort (taken)
5. Assign @me; set Status = In Progress
6. Comment "Claimed on branch <branch>"
7. Implement and self-check, validate, fresh-agent pre-push review; push the
   branch at each checkpoint (PAD-04-004)
8. create-pr: cherry-pick onto a fresh origin/main (freshen-branch.sh), push
9. gh pr create with "- Closes #<N>"
   → a draft PR keeps the issue In Progress; a ready PR moves it to In Review
   → the pr-size-label workflow measures the diff and labels the PR
```

`claim-issue.sh` performs steps 4–6, with `announce-claim.sh` doing 5–6, and
refuses a held Task or Feature (exit 3) unless `--epic-run` names its Epic.
Because every agent is the same GitHub user, only that flag tells the run from a
stray session (PAD-19-003). An Epic claimed to plan it is commented on, never
assigned: an Epic's assignee means an epic run (PAD-04-002).

Pre-push review findings are FAIL, IMPROVE or DEFER
(`.agents/skills/shared/completeness-doctrine.md`): FAIL and IMPROVE are fixed
before the PR opens; there is no advisory category to log and forget. The
reviewer is a fresh subagent, because an author reviewing its own change shares
the blind spots it wrote with; the post-push triage then reviews only the
live-PR phases and the delta (PAD-07-007, ADR-0139).

## Stale Claim Recovery

```text
Sweeper (stale_claim_sweeper.yml, weekly or on demand):
  For each Issue that is assigned, has a claim branch on GitHub (any prefix),
  no open PR for that branch, and neither a branch commit nor its claim
  in the last 3 days:
  → add stale-claim label
  → comment: "Orphaned claim on branch <branch>. Human review needed."
  For each Epic that is assigned (an epic run), was claimed > 3 days ago, and
  none of whose held issues (descendants down to a nested Epic) has an open
  PR or claim-branch activity in 3 days:
  → add stale-claim label, comment
  (logic and tests: .github/scripts/stale_claim_sweeper.py)

Human remediation: review or delete the branch, unassign the Issue, remove
stale-claim → the Issue is claimable again
```

A stale claim stays `In Progress` with the `stale-claim` marker. The human
decides whether to resume it (an agent checks out the existing branch) or release
it. The claim time counts as activity because GitHub creates the branch at the
`main` tip, whose commit can already be days old. After that, the sweeper sees
only pushed commits, which is why PAD-04-004 asks for a push at each checkpoint.

## Merge Conflict Recovery

```text
Pushed PR, in pr-execute:
  1. git fetch origin <base>
     merge-state.sh <pr>                              → CONFLICTING/DIRTY? BEHIND?
     git merge-tree --write-tree HEAD origin/<base>   → would conflict?
     ├── no conflict, not BEHIND → do nothing, even if files overlap (PAD-18-004)
     ├── BEHIND, no conflict     → gh pr update-branch; no local gate; CI re-runs
     └── conflict → sync-with-main.sh <base>  (merge, never rebase: PAD-11-001)
           ├── conflicts resolved
           │     → linters + targeted-tests --paths <conflicted files>
           │     → git push (never --force: PAD-11-002); CI runs the full suite
           └── conflict cannot be resolved safely
                 → sync-with-main.sh --abort
                 → gh pr comment: explain the conflict  (PAD-11-003)
                 → gh pr edit --add-label needs-rebase  (PAD-11-004)
                 → stop; a human resolves it            (PAD-11-005)

The merger, right before merging one PR (work-epic-tasks; PAD-18-009):
  conflict                → re-run pr-ship
  BEHIND, or files overlap → gh pr update-branch, wait-for-ci.sh, merge on green
  neither                 → merge
```

Only a conflict costs an agent and a local run; every clean merge is GitHub's,
tested by CI (ADR-0138). Check only the PR about to merge, never every open PR
after a merge, and update it at most once: re-syncing on every movement of
`main` is the loop ADR-0138 removed. A semantic conflict between files neither
side shares is caught by CI on `main` after merge (ADR-0126). Before the first
push there is nothing published to rewrite, so `create-pr` cherry-picks
instead.

## Shared `.git` and Worktree Pruning (Danger)

The `.git` **common directory is shared across environments**: host checkouts and
dev-container checkouts mount the same `.git`, and each worktree may live at a
path only one environment can resolve.

**Never run `git worktree prune`, `git gc`, or any pruning command.** `prune`
deletes the admin metadata of every worktree whose path is not resolvable *from
the current environment*, which includes **live** worktrees owned by other
containers or the host. **`prunable` means "path not visible from here," not
"safe to delete."** Leave such entries alone and confirm with a human before
removing any worktree.

### Recovery after an erroneous prune

Prune never touches refs or objects, so no commits are lost, only per-worktree
admin metadata. `git worktree repair` **cannot** recreate a deleted admin dir;
rebuild each by hand, **from the environment that can see that checkout**:

```bash
# For each affected worktree <path> that was on branch <branch>:
admin=$(sed -n 's/^gitdir: //p' "<path>/.git")   # e.g. .../.git/worktrees/<id>
mkdir -p "$admin"
printf '%s/.git\n' "<path>"              > "$admin/gitdir"
printf '../..\n'                         > "$admin/commondir"
printf 'ref: refs/heads/%s\n' "<branch>" > "$admin/HEAD"   # or a 40-char SHA if detached
git -C "<path>" reset --mixed            # rebuilds the index only; keeps working-tree edits
```

Then run `git worktree repair` and `git worktree list` to confirm. Recover the
branch mapping from `git worktree list` output captured before the prune, or from
open PRs; `git -C <path> checkout <branch>` fixes a wrong mapping.

## Project #24: Two Paths

GitHub Project #24 ("Vultron Planning") carries two independent paths. Each
field has one owner, and no item carries both.

| | Schedule | Status |
|---|---|---|
| Answers | Which body of work matters now | Where this piece of work stands |
| Lives on | Epics only (PAD-02-001) | Every non-Epic issue (PAD-16-001, PAD-16-012) |
| Values | Someday → Later → Next → Now → Focus | Backlog → Ready → In Progress → In Review → Done |
| Set by | A human (or `review-priorities`), deliberately | Mirrored from facts; never a value the facts don't produce (PAD-16-002) |

Open non-draft PRs are also board items, with a third field, `Ship stage` (PAD-17).

### Status is a mirror

Each `Status` value restates a fact that lives elsewhere; the first rule that
matches wins:

| Status | Fact | Spec |
|---|---|---|
| Done | The issue is closed, for any reason | PAD-16-010 |
| In Review | An open, **non-draft** PR closes it: OK to run `pr-ship` | PAD-16-009 |
| In Progress | Claimed (assignee plus its own or its bundle's branch), no ready PR | PAD-16-008 |
| Ready | The conditions below hold | PAD-16-004/005 |
| Backlog | Anything else | PAD-16-011 |

`Ready` means *could be started*, judged from the issue's own facts:

- **Ready to build** (Task, Feature, Bug): open, unassigned, a leaf, no claim
  branch, has an Epic ancestor, carries `- [ ] AC-N:` lines, every blocker
  closed, no `needs-info`.
- **Ready to plan** (Idea, Concern): open, unassigned, no claim branch, has an
  Epic ancestor, no `needs-info`.

The Epic's tier is deliberately absent: it orders the pick among `Ready` issues,
so planning a `Next`-tier Idea early is a choice, not a violation (PAD-16-006).
Projects cannot filter on a parent's field, so group the `Ready` column by parent
Epic to approximate "Ready under a Now Epic".

A drifted `Status` misleads only a human reading the board, because skills read
the underlying facts (PAD-16-003); recomputing repairs it.

### PR ship stage

`Ship stage` (`Awaiting ship`, `Triage`, `Execute`, `Verify`, `Needs you`,
`Ready to merge`) starts at `Awaiting ship` when a non-draft PR is opened or
marked ready (PAD-17-003), is set by `pr-ship` as it enters each phase or pauses
at a gate (PAD-17-002), and is cleared when the PR returns to draft, closes, or
merges (PAD-17-004). The issue stays `In Review` throughout: pipeline detail
belongs to the PR, because one bundle PR closes several issues. Without it,
progress sits in gitignored `.claude/pr-*.json` files no other session can see.

### Epics

An Epic has a Schedule tier and no Status. Its progress is GitHub's sub-issue
progress, and `needs-decomposition` marks one that still needs planning. It
closes when its last sub-issue closes (PAD-01-008).

An assigned Epic is claimed by an epic run (`work-epic-tasks`, PAD-19):
`claim-epic.sh` after plan approval, `release-epic.sh` with the summary at every
stop. The run's plan stays in its gitignored status file; the assignee is the
only part other sessions need to see.

### Triage

Triage has two inputs: Epics at `Someday` (or with no Schedule), which need a
tier, and non-Epic issues with no Epic ancestor, which need a parent (PAD-12).
`manage_github_issue.sh` refuses to create an issue without `--parent`.

### Views

Views are board settings, not process: Schedule (Epics by tier, with progress),
Issues (`Status` columns grouped by type), PRs (by `Ship stage`), and Needs you
(PRs at `Needs you` or `Ready to merge`, `needs-info`, `ready-for-human` and
`stale-claim` issues).

## Load When

- Adding or modifying workflow skills that select, claim or bundle work
  (`build`, `propose-bundle`, `bundle-fit`, `bundling.md`, `review-priorities`,
  `update-plan`)
- Creating GitHub Issues for new work items
- Recalibrating the `size:` bands, or touching anything that reads them
  (`size_bands.py`, `sizing.md`, `.github/workflows/pr-size-label.yml`)
- Changing the stale-claim sweeper workflow
- Changing anything that reads or writes Project #24 fields (`Schedule`,
  `Status`, `Ship stage`), or adding a board view
- Working with git worktrees
