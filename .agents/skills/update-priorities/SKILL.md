---
name: update-priorities
description: Interactively update PRIORITIES.md by adding, removing, or refining priority groups. Gathers user input about new work, priorities, dependencies, and links to GitHub issues. Use when you want to add new priorities, reorganize existing groups, or update priority descriptions based on findings from check-priority-status.
---

# Update Priorities

Interactively update `plan/PRIORITIES.md` by adding, removing, or refining priority groups. Designed as a companion to `check-priority-status`—run the status check first to understand gaps and uncovered work, then use this skill to modify the priority list.

## Quick start

Run the update-priorities skill.

The skill will:

1. Load current `plan/PRIORITIES.md`
2. Present options:
   - **Add a new priority group** (for uncovered issues or new work)
   - **Refine an existing group** (update description, add/remove issues, adjust priority number)
   - **Remove a priority** (archive completed work via `append-history`)
   - **View current state** (quick reference before editing)
3. For each action, gather details:
   - Priority number (or suggest auto-assigned number)
   - Title and description
   - Root issue/epic link
   - Sub-issues and related work
   - Dependencies and prerequisites
4. Validate updates (check links are live, epic relationships exist)
5. Preview changes before writing
6. Stage and commit (or save draft for manual review)

## Workflows

### Add a New Priority Group

When you have uncovered work that should be tracked:

1. Identify the root issue (epic or feature request)
2. List sub-issues/related work
3. Clarify dependencies (does it block or depend on other priorities?)
4. Choose or auto-assign a priority number
5. Write a clear title and description
6. Validate that all linked issues exist and are open
7. Insert into `plan/PRIORITIES.md` (maintain ascending priority numbers)

### Refine an Existing Group

When a priority needs updates (status change, new linked issues, dependency shifts):

1. Select the priority from list
2. Choose what to update: title, description, linked issues, dependencies
3. Make changes interactively
4. Validate links and relationships
5. Preview diff before writing

### Remove a Priority (Archive)

When a priority group is fully completed:

1. Select the priority to archive
2. Confirm all linked issues are closed
3. Run `uv run append-history priority` (auto-generates history entry with timestamp)
4. Remove from `plan/PRIORITIES.md`
5. Commit

### View Current State

Quick reference table of all priorities (like the start of `check-priority-status` summary):

```text
Priority | Title                          | Issues | Status
---------|--------------------------------|--------|--------
470      | Two-Actor Demo Redesign        | 5      | 🟡 In Progress
475      | Participant Case Replica Safety| 1      | 🟡 In Progress
476      | Bug Fixes and Demo Polish      | 7      | 🟢 On Track
```

## Priority Number Assignment

**Rules** (from `plan/PRIORITIES.md` header):

- Ascending numbers = higher priority
- Scale is not linear (allows gaps for future insertion)
- When adding a new priority:
  - Choose a number between two existing numbers, or
  - Choose a new number higher than the max if it's lower priority
  - Example: if current max is 476, a new lower-priority item could be 480 or 500

Skill will suggest placements based on your answer: "Higher or lower priority than [group X]?"

## Validation

Before writing `plan/PRIORITIES.md`, validate:

- ✓ All issue links are valid (GitHub API check: issue exists, is open)
- ✓ Epic links have actual sub-issues (for epics, show issue count)
- ✓ Priority numbers are unique and ascending
- ✓ No duplicate issue links across groups
- ✓ Prerequisite issues exist and are open
- ✓ Text formatting (relative links, markdown syntax)

If any validation fails, report it and offer to fix or skip.

## Preview & Commit

Before writing to disk:

1. Show a **diff preview** (additions, removals, changes highlighted)
2. Ask for confirmation: "Write these changes?"
3. If yes:
   - Stage `plan/PRIORITIES.md`
   - Prompt user for commit message (or auto-generate one)
   - Add co-author trailer and commit
4. If no:
   - Save draft to session workspace (e.g., `updates.md`)
   - Prompt to review and re-run skill later

## Advanced Features

See [REFERENCE.md](REFERENCE.md) for:

- Batch import (add multiple priorities from a CSV or structured list)
- Priority renumbering (if gaps have accumulated)
- Report generation (export current state as JSON/CSV)
- Integration with GitHub project boards
- History query (view archived priorities)

## Notes

- **No deletion without archiving**: Completed priorities must be archived to `plan/history/` via `append-history` before removal from `PRIORITIES.md`
- **Validation is strict**: Bad links or formatting issues block writes; fix or skip before proceeding
- **Preview before commit**: Always show a diff; never write silently
- **Skill is independent**: Does not automatically run `check-priority-status`; user should run status check *first* to identify gaps
- **Undo via git**: If changes are committed incorrectly, undo with `git revert` or `git reset --soft`
