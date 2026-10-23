---
source: NOTES-agentic-workflow--feedback-loops
timestamp: '2026-09-17T17:13:36.731116+00:00'
title: Feedback Loops (agentic workflow)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,e) references retired pipeline
**Superseded by:** specs/build-workflow.yaml

---

## Feedback Loops

The pipeline has two natural feedback loops:

1. **Build → Learn**: `build` and `bugfix` create individual learning files in
   `plan/incoming/learnings/`. On the next loop, `learn` promotes each file's
   observations to specs, notes, and `AGENTS.md`, archives each entry via
   `uv run append-history --from-file`, and the file moves to history.
   This ensures what the codebase teaches us is captured durably before the
   plan is next updated.

2. **Learn/Ingest → Update-plan**: After `learn` or `ingest-idea` refines
   specs and notes, `update-plan` picks up the changes and translates them
   into concrete tasks. This keeps the plan aligned with the current
   specification reality.

---
