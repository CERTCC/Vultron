---
title: Agentic Development Workflow
status: active
description: >
  Documents the skill-based agentic development pipeline used in this project:
  ingest-idea, learn, update-plan, and build. Explains the inputs, outputs,
  and priority-interrupt loop that governs when each skill runs.
related_notes:
  - notes/append-only-file-handling.md
  - notes/bugfix-workflow.md
---

# Agentic Development Workflow

This project uses a four-skill pipeline for AI-assisted development. Each
skill has a clearly bounded scope, well-defined inputs and outputs, and a
defined place in a **priority-interrupt loop** that governs execution order.

The pipeline is designed to be automatable: an orchestrating agent can inspect
file-change signals to decide which skill to run next, always resolving
higher-priority steps before lower-priority ones.

---

## The Four Skills

### 1. `ingest-idea` — Design

**Purpose**: Convert raw human ideas into durable specifications and design
notes.

| | |
|---|---|
| **Trigger** | `plan/IDEAS.md` has new or unprocessed entries |
| **Input** | `plan/IDEAS.md` (one idea per run) |
| **Process** | Select idea → explore codebase → grill-me interview → write |
| **Output** | `specs/<topic>.yaml` (new/updated), `notes/<topic>.md` |
| **Side effects** | Idea archived to `plan/IDEA-HISTORY.md`, removed from `plan/IDEAS.md`; `specs/README.md` updated |

This is the **highest-priority** skill because new ideas may invalidate
in-progress plans or render planned tasks obsolete. Unprocessed ideas in
`IDEAS.md` should always be ingested before any other work proceeds.

---

### 2. `learn` — Integrate Build Lessons

**Purpose**: Promote lessons learned during build execution into durable
specifications, design notes, and agent guidance.

| | |
|---|---|
| **Trigger** | `plan/IMPLEMENTATION_NOTES.md` has unprocessed insights |
| **Input** | `plan/IMPLEMENTATION_NOTES.md`, `plan/IMPLEMENTATION_HISTORY.md` |
| **Process** | Load context → analyze gaps → grill-me interview → write |
| **Output** | `specs/` (refined), `notes/` (promoted), `AGENTS.md` (updated) |
| **Side effects** | `IMPLEMENTATION_NOTES.md` entries struck-through once captured |

`learn` is the **second-priority** skill. Build execution produces insights
that should be reflected in specs before the plan is updated. Running
`update-plan` on stale specs would produce a plan misaligned with what the
codebase actually needs.

> For ideas originating outside the build process (human brainstorming,
> external research), use `ingest-idea` instead.

---

### 3. `update-plan` — Plan Maintenance

**Purpose**: Perform a gap analysis between current specs/notes and the
codebase, then rewrite `IMPLEMENTATION_PLAN.md` with an ordered, actionable
task list.

| | |
|---|---|
| **Trigger** | `specs/` or `notes/` have changed since the last plan update |
| **Input** | `specs/`, `notes/`, `vultron/`, `test/`, `plan/PRIORITIES.md` |
| **Process** | Load context → gap analysis → rewrite plan → tidy notes |
| **Output** | `plan/IMPLEMENTATION_PLAN.md` (rewritten), `plan/IMPLEMENTATION_NOTES.md` (tidied) |
| **Side effects** | Completed tasks moved to `plan/IMPLEMENTATION_HISTORY.md` |

`update-plan` is the **third-priority** skill. It translates the current
specs and notes into concrete tasks. Running `build` on a stale plan risks
implementing the wrong things or duplicating already-completed work.

---

### 4. `build` — Execute

**Purpose**: Complete the highest-priority pending task from the
implementation plan.

| | |
|---|---|
| **Trigger** | `IMPLEMENTATION_PLAN.md` has pending tasks and no higher-priority skill is triggered |
| **Input** | `plan/IMPLEMENTATION_PLAN.md` (one task), `specs/`, `notes/` |
| **Process** | Select task → verify → implement → validate → finalize |
| **Output** | `vultron/` (code), `test/` (tests) |
| **Side effects** | Task removed from plan, summary appended to `IMPLEMENTATION_HISTORY.md`; lessons added to `IMPLEMENTATION_NOTES.md` (triggering `learn` on the next loop) |

`build` is the **lowest-priority** skill — it only runs when no higher-level
skill is triggered. Its side effects (new `IMPLEMENTATION_NOTES.md` entries)
naturally trigger `learn` on the next loop iteration.

---

## Priority-Interrupt Loop

The pipeline runs as a loop. On each iteration, the agent checks trigger
conditions in priority order and runs the first matching skill. After the
skill completes, the loop restarts — higher-priority skills always preempt
lower-priority ones.

```mermaid
flowchart TD
    START([🔄 Loop start]) --> CHK_IDEAS{IDEAS.md has\nnew entries?}

    CHK_IDEAS -->|Yes| INGEST["🌱 ingest-idea\nIDEAS.md → specs/ + notes/"]
    INGEST --> START

    CHK_IDEAS -->|No| CHK_NOTES{IMPLEMENTATION_NOTES\nhas unprocessed\ninsights?}

    CHK_NOTES -->|Yes| LEARN["🧠 learn\nNOTES/HISTORY → specs/ + notes/ + AGENTS.md"]
    LEARN --> START

    CHK_NOTES -->|No| CHK_SPECS{specs/ or notes/\nchanged since last\nplan update?}

    CHK_SPECS -->|Yes| UPDATE["📋 update-plan\nspecs/notes/code → IMPLEMENTATION_PLAN.md"]
    UPDATE --> START

    CHK_SPECS -->|No| CHK_TASKS{IMPLEMENTATION_PLAN.md\nhas pending tasks?}

    CHK_TASKS -->|Yes| BUILD["🔨 build\ntask → code + tests"]
    BUILD --> START

    CHK_TASKS -->|No| DONE([✅ Done])
```

---

## File Roles in the Pipeline

| File | Role | Ephemeral? |
|---|---|---|
| `plan/IDEAS.md` | Raw human ideas awaiting ingestion | Yes — processed by `ingest-idea` |
| `plan/IDEA-HISTORY.md` | Archive of processed ideas | Permanent (append-only) |
| `specs/*.yaml` | Authoritative requirements | Permanent |
| `notes/*.md` | Durable design insights | Permanent |
| `AGENTS.md` | Agent conventions and patterns | Permanent |
| `plan/PRIORITIES.md` | Authoritative priority ordering | Permanent |
| `plan/IMPLEMENTATION_PLAN.md` | Pending + in-progress tasks | Living document |
| `plan/IMPLEMENTATION_NOTES.md` | Ephemeral build observations | Yes — promoted by `learn` |
| `plan/IMPLEMENTATION_HISTORY.md` | Completed-task archive | Permanent (append-only) |
| `plan/BUGS.md` | Open bugs | Living document |
| `vultron/`, `test/` | Implementation | Permanent |

---

## Feedback Loops

The pipeline has two natural feedback loops:

1. **Build → Learn**: `build` writes lessons to `IMPLEMENTATION_NOTES.md`.
   On the next loop, `learn` promotes those lessons to specs and notes.
   This ensures that what the codebase teaches us is captured before
   the plan is next updated.

2. **Learn/Ingest → Update-plan**: After `learn` or `ingest-idea` refines
   specs and notes, `update-plan` picks up the changes and translates them
   into concrete tasks. This keeps the plan aligned with the current
   specification reality.

---

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Why separate `ingest-idea` from `learn`? | External ideas and internal build lessons are different sources with different quality gates | Ideas need a grill-me interview; build lessons are already structured enough to promote directly |
| Why is `update-plan` distinct from `build`? | Plan maintenance is a research task; execution is a coding task | Mixing them produces plans that drift from specs |
| Why restart the loop after each skill? | Higher-priority skills may be triggered by a lower-priority skill's outputs | Ensures design always precedes planning, planning always precedes building |
| Why no branching inside skills? | Clean boundaries enable future automation of the loop | A BT or script can inspect file-change signals to trigger the right skill |

---

## Future Automation

The trigger conditions in the loop are based on observable file-change
signals, making the entire pipeline amenable to a behavior tree (BT)
implementation:

```text
Selector (priority order)
├── Sequence: IDEAS.md changed? → ingest-idea
├── Sequence: IMPLEMENTATION_NOTES.md changed? → learn
├── Sequence: specs/ or notes/ changed? → update-plan
└── Sequence: IMPLEMENTATION_PLAN.md has tasks? → build
```

Each condition node checks a file-system signal; each action node invokes
the corresponding skill. The BT's selector ensures the highest-priority
condition is always serviced first.
