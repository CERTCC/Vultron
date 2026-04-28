---
name: study-project-docs
description: >
  Load all specs and read key project context files so the agent has a
  complete picture before doing any implementation, design, or documentation
  work. Invokes load-specs and reads plan/, docs/adr/, notes/, and AGENTS.md.
  Run this at the start of every workflow skill.
---

# Skill: Study Project Docs

Load the full specification set and read key project context so the agent can
work accurately without guessing. This is the standard "orient yourself" step
that all workflow skills (`build`, `bugfix`, `learn`, `ingest-idea`) run
before doing anything else.

## Procedure

### Step 1 — Load specs

Invoke the `load-specs` skill (run `uv run spec-dump`). Capture the JSON
output. Do **not** read raw `specs/*.yaml` files directly.

### Step 2 — Read plan context

Read all of the following in parallel (do **not** recurse into `plan/history/`):

- `plan/PRIORITIES.md` — authoritative priority ordering
- `plan/IMPLEMENTATION_PLAN.md` — current task status
- `plan/IMPLEMENTATION_NOTES.md` — design notes and constraints (ephemeral)
- `plan/IDEAS.md` — raw ideas (ephemeral)
- `plan/BUGS.md` — open bugs (if it exists)

> **`plan/history/` is excluded from this step.** It is an archive of
> completed work, not active planning context. Read it only when specifically
> investigating historical changes or extracting lessons from prior
> implementation phases (e.g., during the `learn` skill).

### Step 3 — Read design documentation

Read in parallel:

- `docs/adr/` directory listing, then each relevant ADR
- `notes/README.md`, then any `notes/*.md` files relevant to the current task
- `AGENTS.md` — agent rules and conventions

### Step 4 — Scan the codebase

Search `vultron/` and `test/` to verify assumptions about what is currently
implemented. Do not assert missing functionality without evidence from code
search.

## Notes

- `IDEAS.md` and `IMPLEMENTATION_NOTES.md` are ephemeral. Any critical insight
  in them **must be preserved elsewhere** before the session ends.
- Do not skip this skill for "small" tasks — it ensures constraints from
  cross-cutting specs (`ARCH`, `CS`, `TB`, `HP`, `SL`, `EH`) are always in
  context.
- If the task is narrowly scoped, you may skip `plan/BUGS.md` and the ADR
  deep-read, but always run Step 1 and Step 2.
