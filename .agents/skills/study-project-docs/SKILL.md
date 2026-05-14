---
name: study-project-docs
description: >
  Load all specs and read key project context files so the agent has a
  complete picture before doing any implementation, design, or documentation
  work. Invokes load-specs and reads plan/, docs/adr/, notes/, AGENTS.md,
  docs/reference/codebase/, and docs/reference/glossary.md.
  Run this at the start of every workflow skill.
---

# Skill: Study Project Docs

Load the full specification set and read key project context so the agent can
work accurately without guessing. This is the standard "orient yourself" step
that all workflow skills (`build`, `bugfix`, `learn`, `ingest-idea`) run
before doing anything else.

## Procedure

### Step 0 — Read the ubiquitous language glossary

Read `docs/reference/glossary.md` **before** loading specs. This establishes
the domain vocabulary used throughout all requirements, notes, and ADRs.

### Step 1 — Load specs

Invoke the `load-specs` skill (run `uv run spec-dump`). Capture the JSON
output. Do **not** read raw `specs/*.yaml` files directly.

### Step 2 — Read plan context

Read all of the following in parallel (do **not** recurse into `plan/history/`):

- `plan/PRIORITIES.md` — authoritative priority ordering
- `plan/BUILD_LEARNINGS.md` — ephemeral build/bugfix observations (queue for `learn`)
- `plan/IMPLEMENTATION_PLAN.md` — read-only index; tasks have moved to GitHub
  Issues. Read only for historical context or to check deferred items; do not
  treat it as the task source.

> **Tasks live in GitHub Issues.** The `build` skill selects work by querying
> GitHub for open leaf Issues in the top-priority group from PRIORITIES.md.
> IMPLEMENTATION_PLAN.md is a read-only index, not the authoritative task list.
>
> **`plan/history/` is excluded from this step.** It is an archive of
> completed work, not active planning context. Read it only when specifically
> investigating historical changes or extracting lessons from prior
> implementation phases (e.g., during the `learn` skill).

### Step 3 — Read design documentation

Read in parallel:

- `docs/adr/` directory listing, then each relevant ADR
- `notes/README.md`, then any `notes/*.md` files relevant to the current task
- `AGENTS.md` — agent rules and conventions
- `docs/reference/codebase/index.md` — codebase reference overview
- `docs/reference/codebase/ARCHITECTURE.md` — system flow and layer rules
- `docs/reference/codebase/STRUCTURE.md` — top-level module map and entry points
- `docs/reference/codebase/CONVENTIONS.md` — naming, formatting, import rules

Read the following codebase reference files **only when relevant to the task**:

- `docs/reference/codebase/STACK.md` — when adding or evaluating dependencies
- `docs/reference/codebase/TESTING.md` — when writing or reviewing tests
- `docs/reference/codebase/CONCERNS.md` — when assessing risk or technical debt
- `docs/reference/codebase/INTEGRATIONS.md` — when working on external integrations

### Step 4 — Scan the codebase

Search `vultron/` and `test/` to verify assumptions about what is currently
implemented. Do not assert missing functionality without evidence from code
search.

## Notes

- `BUILD_LEARNINGS.md` is an ephemeral queue. Any critical insight
  in it **must be preserved elsewhere** before the session ends. Ideas are
  tracked as GitHub Idea-type issues — query them with `gh issue list` when
  needed.
- Do not skip this skill for "small" tasks — it ensures constraints from
  cross-cutting specs (`ARCH`, `CS`, `TB`, `HP`, `SL`, `EH`) are always in
  context.
- If the task is narrowly scoped, you may skip the ADR deep-read, but always
  run Steps 0, 1, and 2.
