---
title: "Parallel Agentic Development: GitHub Issue-Based Coordination"
status: active
description: >
  Design decisions and implementation guidance for coordinating multiple
  parallel AI agents and human developers via GitHub Issues. Covers the
  issue hierarchy, label taxonomy, task claiming protocol, size labeling,
  orphan recovery, and skill updates.
related_specs:
  - specs/parallel-development.yaml
---

# Parallel Agentic Development: GitHub Issue-Based Coordination

## Overview

The project has shifted from a single-developer, file-based task list
(`IMPLEMENTATION_PLAN.md`) to a GitHub Issue-based coordination model that
supports multiple parallel AI agents and human developers.

**Formal requirements**: `specs/parallel-development.yaml` PAD-01 through
PAD-15.

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
| What is the authoritative priority ordering? | PRIORITIES.md | Human-readable, freely reorderable without touching GitHub API |
| How are tasks claimed? | Branch creation (`task/<N>-slug`) | Git branch creation is atomic — ideal distributed lock |
| Should there be a `claimed` label? | No | Adds a second source of truth that can drift from branch state |
| Stale-claim threshold | 3 days since last branch commit | Short enough to keep the queue clean; tune if agent sessions are longer |
| Diff-size thresholds | ≤50 lines = S, 51–300 = M, 301+ = L | Common open-source convention; aligns with maintainability expectations |
| Two-pass code review? | Single-pass with [BLOCKING]/[ADVISORY] tags | Same signal, less process theater; build agent acts on tags |
| Where do `update-plan` gap findings go? | GitHub Issues (group:unscheduled) | Consistent with the new model; no new tasks in IMPLEMENTATION_PLAN.md |

---

## Issue Hierarchy

```text
Epic Issue (group:<name>)        ← maps to a PRIORITIES.md group
  └── Task Issue                 ← coherent unit of work
        └── Subtask Issue        ← atomic PR-sized chunk (leaf = claimable)
```

Use minimum depth. Many Epics will have leaf Tasks with no Subtasks.

---

## Label Taxonomy

| Label | Applied by | Meaning |
|---|---|---|
| `group:<name>` | ingest-idea, update-plan, agents | Priority group membership |
| `group:unscheduled` | ingest-idea, update-plan, agents | Not yet in PRIORITIES.md |
| `size:S` | Agent at issue creation + PR open | ≤2 ACs or ≤50 diff lines |
| `size:M` | Agent at issue creation + PR open | 3–6 ACs or 51–300 diff lines |
| `size:L` | Agent at issue creation + PR open | 7+ ACs or 301+ diff lines |
| `stale-claim` | Stale-claim sweeper (GH Actions) | Orphaned claim; skip until human clears |
| `needs-rebase` | Build agent | PR has unresolvable merge conflicts |
| `specs-notes` | ingest-idea, learn | Docs-only PR containing only specs/ and notes/ changes |

---

## Task Claiming Protocol

```text
1. Read PRIORITIES.md → identify top-priority group name
2. Query GitHub: open leaf Issues with that group: label,
   no stale-claim, unassigned
3. Pick the highest-priority unblocked leaf Issue
4. git switch -c task/<issue-number>-<slug>
   → if branch already exists: abort (task is taken)
5. gh issue edit <N> --add-assignee @me
6. gh issue comment <N> --body "Claimed by <agent-session> on branch task/<N>-<slug>"
7. Implement, validate, code-review (address [BLOCKING] findings)
8. Compute diff size → update size label on Issue and future PR
9. git push -u origin task/<N>-<slug>
10. gh pr create --title "..." --body "Closes #<N>\n\n..." --label size:X
```

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
    - task/<N>-slug branch exists
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

## Skill Updates Summary

| Skill | Change |
|---|---|
| `build` | Phase 2: select from GitHub Issues (not IMPLEMENTATION_PLAN.md); add claiming, pre-PR code review ([BLOCKING]/[ADVISORY]), size labeling, PR creation, auto-rebase |
| `ingest-idea` | Add: open docs-only PR with `specs-notes` label; create GitHub Issue with `group:unscheduled` |
| `review-priorities` | Add Phase 2.5: fetch `group:unscheduled` Issues, interview user for placement |
| `study-project-docs` | Step 2: downgrade IMPLEMENTATION_PLAN.md to secondary/archive; note task source is GitHub Issues |
| `update-plan` | Rewrite: create GitHub Issues for gaps (not IMPLEMENTATION_PLAN.md entries) |

---

## IMPLEMENTATION_PLAN.md Post-Migration

After migration, `plan/IMPLEMENTATION_PLAN.md` becomes a read-only index:

```markdown
# Implementation Plan — Read-Only Index

Tasks have moved to GitHub Issues. See:

- [CERTCC/Vultron Issues](https://github.com/CERTCC/Vultron/issues)
- [PRIORITIES.md](PRIORITIES.md) for priority ordering
```

Do not add tasks to this file. Any previously deferred items are tracked as
GitHub Issues with appropriate labels.

---

## Group Label Conventions (gap-analysis finding, 2026-05-05)

A `group:<name>` label MUST correspond to exactly one priority group in
`PRIORITIES.md`. Labels MUST use descriptive names only — **never embed a
priority number** in the label name or description. Priority ordering lives
in `PRIORITIES.md` and can change without touching issue labels.

### Implications

- Each `group:*` label maps to one entry in `PRIORITIES.md`. If two priority
  entries need separate work-streams, create two labels.
- The label description should name the work-stream (e.g.,
  "Re-implement fuzzer nodes from original simulator"), not the priority
  number. This was corrected for `group:fuzzer-nodes` in May 2026.
- `group:unscheduled` is the holding label for Issues not yet slotted into
  `PRIORITIES.md`. Use `review-priorities` to assign them.

### Label compliance for older issues

Issues predating the PAD label requirements (opened before Priority 473
work began) may lack `group:*` and/or `size:*` labels. These are not
retroactively wrong — they should be updated when touched. Issues #5, #6,
and #294 were missing labels and were updated in May 2026.

---

## Open Questions / Future Work

- **Diff-size threshold tuning**: The 50/300 line thresholds are a starting
  point. Revisit after the first 20–30 PRs to calibrate against observed
  complexity.
- **GitHub Projects v2**: If the team grows beyond 4 developers or
  PRIORITIES.md + labels become unwieldy, consider migrating to a Projects
  v2 board with custom fields for roadmap ordering.
- **Loop-agent construction**: The revised `build` skill (issue selection +
  PR creation) is the foundation for a fully autonomous learn/plan/build loop
  agent. Design of that agent is deferred.

---

## Load When

Load this file when:

- Adding or modifying skill SKILL.md files (`build`, `ingest-idea`,
  `review-priorities`, `update-plan`, `study-project-docs`)
- Creating GitHub Issues for new work items
- Implementing or modifying the stale-claim sweeper GitHub Actions workflow
- Debugging task-selection or claiming behavior in the `build` skill
- Reviewing why IMPLEMENTATION_PLAN.md is now a read-only index
