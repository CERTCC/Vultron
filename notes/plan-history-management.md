---
title: Plan / History Management Contract
status: active
description: >
  Authoritative rules for managing IMPLEMENTATION_PLAN.md (forward roadmap)
  and IMPLEMENTATION_HISTORY.md (append-only log).
related_specs:
  - specs/project-documentation.md
---

# Plan / History Management Contract

This document defines the authoritative rules for managing
`plan/IMPLEMENTATION_PLAN.md` (PLAN) and `plan/IMPLEMENTATION_HISTORY.md`
(HISTORY) in the Vultron project.

Formal requirements are in `specs/project-documentation.md` (PD-02-001
through PD-02-006). This file explains the **rationale**, provides the
**operational rules**, and documents the **failure modes to avoid**.

---

## Artifact Roles

### Implementation Plan (PLAN)

- Represents the *active working set* of tasks.
- Contains only tasks that are not yet complete: `{PENDING, IN_PROGRESS,
  BLOCKED}`.
- Bounded in size (≤ 20 tasks) and continuously pruned.
- Optimized for decision-making and agent orientation — not for auditability.

### Implementation History (HISTORY)

- Represents the *authoritative event log* of completed work.
- Append-only: entries are never edited, mutated, or deleted once written.
- Stores the full record of what was done, when, and with what outcome.

---

## Core Invariant

> A task in DONE state MUST NOT exist in PLAN.

Corollary:

- PLAN contains only tasks in `{PENDING, IN_PROGRESS, BLOCKED}`.
- HISTORY is the only location where completed tasks persist.

---

## Task State Model

```text
PENDING → IN_PROGRESS → DONE ──→ (deleted from PLAN; appended to HISTORY)
                      ↗
BLOCKED ─────────────
```

Completion is not a state that PLAN tracks — it is the condition that removes
a task from PLAN entirely.

---

## Atomic Completion Protocol

Completing a task is a **two-phase atomic operation**:

```text
PRECONDITION:
  task exists in PLAN
  task.state ∈ {IN_PROGRESS, BLOCKED}

TRANSITION:
  1. Append completion record to HISTORY
  2. Remove task from PLAN

POSTCONDITION:
  task_id exists in HISTORY
  task_id does NOT exist in PLAN
```

Both steps MUST happen together. A completion is invalid unless both steps
occur. Deferred cleanup is not permitted.

---

## No Tombstones Rule

Completed tasks MUST be removed entirely from PLAN. The following are **all
prohibited**:

- `[x]` checkboxes
- ~~Strikethrough~~ task titles
- Tombstone one-liners (`**ID** — Brief (date) → see HISTORY`)
- "Completed Phases" sections listing finished work
- Any reference to a task's outcome within PLAN

**Rationale**: Tombstones re-introduce the problem they purport to solve.
They keep completed tasks visible in PLAN, increasing its length and cognitive
load. Over time, PLAN accumulates hundreds of lines of historical cruft that
obscures the active working set. The only safe invariant is: if it is in PLAN,
it is not done.

---

## HISTORY Entry Format

Each completion record appended to HISTORY SHOULD include:

```markdown
## <date> — <task_id>: <title>

- **Outcome**: SUCCESS | PARTIAL | FAILED
- **Summary**: What was done.
- **Artifacts**: Files changed, commits, tests added.
- **Notes**: Deviations from plan, follow-up items (optional).
```

HISTORY entries are ordered chronologically (oldest first, newest last).
New entries are appended at the end of the file.

---

## PLAN Task Format

Each task in PLAN SHOULD include:

```markdown
## <task_id>: <title>

**State**: PENDING | IN_PROGRESS | BLOCKED
**Acceptance criteria**: Concise, testable definition of done.
**Dependencies**: Other task IDs that must complete first (optional).
**Blockers**: Current blocking issue (required if BLOCKED).
```

Avoid embedding verbose execution logs, debugging notes, or historical
commentary in PLAN. That material belongs in HISTORY or
`plan/IMPLEMENTATION_NOTES.md`.

---

## Bounded Plan Size

PLAN SHOULD contain no more than 20 active tasks at any time.

When new work is identified that would push the count above 20:

1. Complete or close lower-priority tasks first, OR
2. Queue the new work externally (in a note, issue, or future PLAN entry)
   rather than adding it immediately.

**Rationale**: A PLAN with 20+ tasks provides no prioritization signal.
Bounded size forces explicit priority decisions and keeps PLAN readable in a
single agent context window.

---

## Failure Modes to Avoid

| Failure Mode | Description | Prevention |
|---|---|---|
| **Plan Bloat** | Completed tasks retained in PLAN | Apply atomic completion |
| **Split-Brain** | Task marked complete in PLAN but missing from HISTORY | Always append HISTORY first |
| **Orphaned Completion** | Task removed from PLAN without HISTORY record | Always append HISTORY as part of completion |
| **Narrative Creep** | Execution detail embedded in PLAN instead of HISTORY | Move notes to HISTORY or IMPL_NOTES |
| **Deferred Cleanup** | "I'll delete the tombstone later" | Enforce immediate atomic deletion |

---

## Summary Rule

> The PLAN is a live working set. The moment a task is completed, it is
> migrated to HISTORY and deleted from PLAN in the same atomic operation.
> No task in DONE state survives in PLAN in any form.
