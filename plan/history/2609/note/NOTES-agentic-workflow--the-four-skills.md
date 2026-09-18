---
source: NOTES-agentic-workflow--the-four-skills
timestamp: '2026-09-17T17:13:36.083623+00:00'
title: The Four Skills (agentic workflow)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,e) ingest-idea retired (now plan-issue/new-item); pipeline framing superseded
**Superseded by:** specs/build-workflow.yaml BW-01..BW-07; skill SKILL.md files

---

## The Four Skills

### 1. `ingest-idea` — Design

**Purpose**: Convert raw human ideas into durable specifications and design
notes.

| | |
|---|---|
| **Trigger** | Open Idea-type GitHub issues exist (unprocessed) |
| **Input** | GitHub Idea-type issue (one idea per run) |
| **Process** | Select idea → explore codebase → grill-me interview → write |
| **Output** | `specs/<topic>.yaml` (new/updated), `notes/<topic>.md` |
| **Side effects** | Idea archived via `uv run append-history idea`; idea issue closed with links to PR and implementation issue; `specs/README.md` updated |

This is the **highest-priority** skill because new ideas may invalidate
in-progress plans or render planned tasks obsolete. Unprocessed Idea-type
issues should always be ingested before any other work proceeds.

---

### 2. `learn` — Integrate Build Lessons

**Purpose**: Promote lessons learned during build execution into durable
specifications, design notes, and agent guidance.

| | |
|---|---|
| **Trigger** | `plan/incoming/learnings/` has unprocessed files |
| **Input** | `plan/incoming/learnings/` (individual per-entry files) |
| **Process** | Load context → analyze gaps → grill-me interview → write |
| **Output** | `specs/` (refined), `notes/` (promoted), `AGENTS.md` (updated) |
| **Side effects** | Processed files moved to `plan/history/YYMM/learning/` via `uv run append-history --from-file` |

`learn` is the **second-priority** skill. Build execution produces insights
that should be reflected in specs before the plan is updated. Running
`update-plan` on stale specs would produce a plan misaligned with what the
codebase actually needs.

> For ideas originating outside the build process (human brainstorming,
> external research), use `ingest-idea` instead.

---

### 3. `update-plan` — Plan Maintenance

**Purpose**: Perform a gap analysis between current specs/notes and the
codebase, then create GitHub Issues for any untracked gaps.

| | |
|---|---|
| **Trigger** | `specs/` or `notes/` have changed since the last plan update |
| **Input** | `specs/`, `notes/`, `vultron/`, `test/`, Project #24 board, open GitHub Issues |
| **Process** | Load context → gap analysis → create GitHub Issues → add to board → write observations to `notes/` |
| **Output** | New GitHub Issues (added to Project #24 with Schedule=Someday), updated `notes/` |
| **Side effects** | None — does not commit code or close issues |

`update-plan` is the **third-priority** skill. It translates the current
specs and notes into concrete GitHub Issues. Running `build` without a
gap analysis risks implementing the wrong things or duplicating
already-completed work.

---

### 4. `build` — Execute

**Purpose**: Complete the highest-priority pending task from GitHub Issues.

| | |
|---|---|
| **Trigger** | Open GitHub Issues exist in the top-priority group and no higher-priority skill is triggered |
| **Input** | Top-priority open GitHub Issue, `specs/`, `notes/` |
| **Process** | Select task → claim branch → implement → validate → open PR |
| **Output** | `vultron/` (code), `test/` (tests), GitHub PR |
| **Side effects** | Summary archived via `uv run append-history implementation`; observations recorded as individual files in `plan/incoming/learnings/` (triggering `learn` on the next loop) |

`build` is the **lowest-priority** skill — it only runs when no higher-level
skill is triggered. Its side effects (new files in `plan/incoming/learnings/`)
naturally trigger `learn` on the next loop iteration.

---
