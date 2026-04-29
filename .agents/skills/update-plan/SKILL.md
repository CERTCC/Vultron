---
name: update-plan
description: >
  Update the implementation plan by performing a gap analysis between current
  specs/notes and the codebase, then rewriting IMPLEMENTATION_PLAN.md with an
  ordered, actionable task list. Observations and open questions go directly to
  notes/ files. Use after learn or ingest-idea has updated specs/notes, and
  before running build. Modifies plan files only — does not change code,
  specs, or notes.
---

# Skill: Update Plan

Perform a gap analysis between the current specifications, design notes, and
the actual codebase, then update `plan/IMPLEMENTATION_PLAN.md` with a
prioritized, actionable task list.

**Constraint**: Modify **plan files only** (`plan/IMPLEMENTATION_PLAN.md`).
Do not change code, tests, `specs/`, or `notes/`. Do **not** write to
`plan/BUILD_LEARNINGS.md` — that file is reserved for `build` and `bugfix`.
Write gap-analysis observations directly to the appropriate `notes/*.md` file.

**Trigger**: Use after `learn` or `ingest-idea` has updated specs or notes,
to translate those changes into concrete implementation tasks. Also run
periodically to keep the plan aligned with the codebase.

## Quick Start

1. Invoke `study-project-docs` to load all specs and context.
2. Run a gap analysis: compare `specs/` + `notes/` against `vultron/` and
   `test/`.
3. Update `plan/IMPLEMENTATION_PLAN.md` — add, reorder, and prune tasks.
4. Write any significant observations or open questions directly to the
   appropriate `notes/*.md` file (not to `BUILD_LEARNINGS.md`).
5. Invoke `commit`.

## Workflow

### Phase 1 — Load Context

Invoke the `study-project-docs` skill. It loads all specs, reads all plan/,
docs/adr/, notes/, AGENTS.md, and scans vultron/ and test/.

To understand what has recently been completed and avoid re-adding finished
work, read the current month's index at `plan/history/YYMM/README.md` (where
`YYMM` is the current year-month, e.g. `2604`). Open individual entry files
only when their titles suggest they contain relevant context.

### Phase 2 — Gap Analysis

Compare the current `specs/` + `notes/` against `vultron/` and `test/`:

- **Missing implementations**: a spec or note says X should exist, but code
  search finds no implementation.
- **Partial implementations**: code exists but tests or edge cases are
  missing.
- **Untested behaviors**: implementation exists but no test covers it.
- **Stale tasks**: `IMPLEMENTATION_PLAN.md` has tasks for things already
  implemented — these should be archived via `uv run append-history implementation`
  and removed from `IMPLEMENTATION_PLAN.md`.
- **Known bugs**: open entries in `plan/BUGS.md` that block or relate to
  planned work.

> Do not assume missing functionality; confirm via code search first.

### Phase 3 — Update `plan/IMPLEMENTATION_PLAN.md`

Rewrite the plan based on the gap analysis:

- Tasks must be **atomic, actionable, testable, and unambiguous**.
- Size tasks as "meaningful chunks": large enough to produce measurable
  progress (e.g., implement a feature + tests + minimal docs), small enough
  to complete in a single agent run.
- Group closely related technical-debt items into a single task when they
  share the same implementation context.
- Order tasks using `plan/PRIORITIES.md` as authoritative plus dependency
  analysis. Do **not** include explicit priority labels in task descriptions.
- **Completed tasks MUST be archived** via `uv run append-history implementation`
  and then deleted from `IMPLEMENTATION_PLAN.md`. Do not leave tombstones,
  `[x]` checkboxes, or one-line summaries.

### Phase 4 — Write Observations to notes/

- Any gap-analysis observations, open questions, clarified assumptions, or
  architectural risks discovered during gap analysis SHOULD be written
  directly to the appropriate `notes/*.md` file.
- Do **not** write these observations to `plan/BUILD_LEARNINGS.md`.
  That file is reserved for `build` and `bugfix` outputs.

### Phase 5 — Commit

Invoke the `commit` skill. Commit only modified plan files with a clear,
specific message (e.g., `plan: gap analysis, add N tasks, move M completed`).

## Constraints

- Do not modify code, tests, or `notes/` except when writing gap-analysis
  observations (Phase 4).
- Do not write to `plan/BUILD_LEARNINGS.md`.
- Do not speculate about missing functionality; verify with code search first.
- Do not implement anything — that is `build`'s domain.
- Use `uv run append-history implementation` to archive completed tasks — do
  not write directly to any file in `plan/history/`.
