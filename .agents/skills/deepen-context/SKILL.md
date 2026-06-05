---
name: deepen-context
description: >
  Load task-specific context after the target issue is known. The caller
  passes focus hints (e.g., "wire layer", "BT integration", "embargo
  lifecycle") and this skill reads the relevant notes files, ADRs, and
  codebase reference files. Run after orient-agent, once the issue to be
  worked has been selected and read. Replaces study-project-docs Phase B.
---

# Skill: Deepen Context

Load task-specific context after the target issue is known. The caller
provides focus hints; this skill reads only what is relevant.

## Inputs

The calling skill passes one or more focus hints describing what area of
the codebase or design the task touches. Examples:

- `"wire layer"` — AS2 parsing, extraction, activity patterns
- `"BT integration"` — behavior tree nodes, blackboard, py_trees
- `"embargo lifecycle"` — EM state machine, PEC transitions
- `"case state model"` — RM/CS/EM state machines, CaseStatus
- `"adapter layer"` — FastAPI inbox, SQLite data layer, emitters
- `"testing"` — pytest fixtures, test data quality, integration tests

## Procedure

### Step 1 — Read relevant notes

Based on the focus hints, read the relevant `notes/*.md` files. Check
`notes/README.md` (already loaded by `orient-agent`) for the index.

Always-relevant notes for implementation work:

- `notes/architecture-hexagonal.md` — layer rules and import constraints
- `notes/codebase-structure.md` — common pitfalls and file organization

Read additional notes files based on focus hints. When in doubt, read
rather than skip — missing context causes incorrect implementation.

### Step 2 — Read relevant ADRs

Using the ADR index loaded by `orient-agent` (`docs/adr/index.md`),
identify and read any ADRs relevant to the current task. Focus on ADRs
whose titles match the task's domain (e.g., behavior trees, hexagonal
architecture, ActivityStreams, DataLayer). Read the full ADR file for
any decision that is in scope — ADR context prevents re-litigating
settled choices.

### Step 3 — Read relevant codebase reference files

Read from `docs/reference/codebase/` based on task scope:

| File | Read when |
|---|---|
| `ARCHITECTURE.md` | Always for implementation tasks |
| `STRUCTURE.md` | When navigating unfamiliar modules |
| `CONVENTIONS.md` | When writing new code |
| `STACK.md` | When adding or evaluating dependencies |
| `TESTING.md` | When writing or reviewing tests |
| `CONCERNS.md` | When assessing risk or technical debt |
| `INTEGRATIONS.md` | When working on external integrations |

### Step 4 — Scan the codebase

Search `vultron/` and `test/` to verify assumptions about what is currently
implemented. Do not assert missing functionality without evidence from code
search.

## Notes

- Focus hints come from the calling skill after it has selected and read
  the target issue. For `build` and `bugfix`, the issue body describes
  what is needed; use that as the basis for hints.
- For `plan-issue`, grill-me Phase 3 surfaces the relevant areas; pass
  those as hints when invoking `deepen-context` in Phase 4.
