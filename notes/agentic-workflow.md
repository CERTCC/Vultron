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
related_specs:
  - specs/build-workflow.yaml
  - specs/history-management.yaml
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
| **Trigger** | `plan/BUILD_LEARNINGS.md` has unprocessed insights |
| **Input** | `plan/BUILD_LEARNINGS.md` |
| **Process** | Load context → analyze gaps → grill-me interview → write |
| **Output** | `specs/` (refined), `notes/` (promoted), `AGENTS.md` (updated) |
| **Side effects** | Processed entries archived via `uv run append-history learning`, then deleted from `BUILD_LEARNINGS.md` |

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
| **Process** | Load context → gap analysis → rewrite plan → write observations to `notes/` |
| **Output** | `plan/IMPLEMENTATION_PLAN.md` (rewritten) |
| **Side effects** | Completed tasks moved to `plan/history/` via `uv run append-history implementation` |

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
| **Side effects** | Task removed from plan, summary archived via `uv run append-history implementation`; observations and open questions appended to `plan/BUILD_LEARNINGS.md` (triggering `learn` on the next loop) |

`build` is the **lowest-priority** skill — it only runs when no higher-level
skill is triggered. Its side effects (new `plan/BUILD_LEARNINGS.md` entries)
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

    CHK_IDEAS -->|No| CHK_NOTES{BUILD_LEARNINGS.md\nhas unprocessed\ninsights?}

    CHK_NOTES -->|Yes| LEARN["🧠 learn\nBUILD_LEARNINGS.md → specs/ + notes/ + AGENTS.md"]
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
| `plan/history/` | Archive of processed ideas, tasks, learnings | Permanent (append-only, chunked) |
| `specs/*.yaml` | Authoritative requirements | Permanent |
| `notes/*.md` | Durable design insights | Permanent |
| `AGENTS.md` | Agent conventions and patterns | Permanent |
| `plan/PRIORITIES.md` | Authoritative priority ordering | Permanent |
| `plan/IMPLEMENTATION_PLAN.md` | Pending + in-progress tasks | Living document |
| `plan/BUILD_LEARNINGS.md` | Ephemeral build/bugfix observations | Yes — processed and archived by `learn` |
| `plan/BUGS.md` | Open bugs | Living document |
| `vultron/`, `test/` | Implementation | Permanent |

---

## BUILD_LEARNINGS.md Content Policy

`plan/BUILD_LEARNINGS.md` is the **exclusive upstream channel** from
code-executing skills (`build`, `bugfix`) to the `learn` skill.

### What belongs here

- Observations about unclear or missing spec requirements discovered during
  implementation (e.g., "The specs don't say what to do when X")
- Constraints or invariants discovered in the code that aren't documented
- Open questions raised during implementation that need a decision
- Patterns that keep recurring and should become `AGENTS.md` guidance
- Gotchas or pitfalls encountered that should be preserved for future runs

### What does NOT belong here

- Completion summaries ("Task X is done") → use `uv run append-history implementation`
- Status updates ("I completed Y and Z") → use `uv run append-history implementation`
- Documentation of finished work → use `append-history` or `notes/`
- `update-plan` gap-analysis observations → write directly to `notes/*.md`

### Lifecycle

```text
build/bugfix run
  → observations appended to plan/BUILD_LEARNINGS.md

learn run
  → each entry promoted to specs/*.yaml, notes/*.md, or AGENTS.md
  → each entry archived: uv run append-history learning
  → each entry deleted from plan/BUILD_LEARNINGS.md

After learn completes:
  plan/BUILD_LEARNINGS.md contains only unprocessed entries (ideally empty)
  plan/history/YYMM/learning/*.md contains the archived originals
```

See `specs/build-workflow.yaml` (BW-01 through BW-04) for the normative
requirements.

---

## Feedback Loops

The pipeline has two natural feedback loops:

1. **Build → Learn**: `build` and `bugfix` write observations to
   `BUILD_LEARNINGS.md`. On the next loop, `learn` promotes those observations
   to specs, notes, and `AGENTS.md`, archives each entry via
   `uv run append-history learning`, then deletes the entry from
   `BUILD_LEARNINGS.md`. This ensures what the codebase teaches us is
   captured durably before the plan is next updated.

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
| Why rename `IMPLEMENTATION_NOTES.md` to `BUILD_LEARNINGS.md`? | The old name implied general design notes; the new name signals a specific, focused role: a queue of code-execution observations for `learn` to promote | See `specs/build-workflow.yaml` BW-01-001 |
| Why not let `build` write directly to `notes/`? | `build`'s job is coding; documentation curation is `learn`'s domain. `BUILD_LEARNINGS.md` is the upstream channel for `build` to communicate observations; `learn` decides what to do with them | BW-01-001, BW-01-002 |
| Why delete (not strike-through) processed learnings? | `BUILD_LEARNINGS.md` is a queue, not an archive. Processed entries live in `plan/history/` via `append-history learning`. Keeping the queue clean prevents accumulation of stale noise | BW-02-002 |

---

## Future Automation

The trigger conditions in the loop are based on observable file-change
signals, making the entire pipeline amenable to a behavior tree (BT)
implementation:

```text
Selector (priority order)
├── Sequence: IDEAS.md changed? → ingest-idea
├── Sequence: BUILD_LEARNINGS.md changed? → learn
├── Sequence: specs/ or notes/ changed? → update-plan
└── Sequence: IMPLEMENTATION_PLAN.md has tasks? → build
```

Each condition node checks a file-system signal; each action node invokes
the corresponding skill. The BT's selector ensures the highest-priority
condition is always serviced first.
