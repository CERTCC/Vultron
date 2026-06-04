---
name: orient-agent
description: >
  Load the always-required baseline context before any implementation,
  planning, or documentation work. Reads the glossary, loads all specs,
  reads AGENTS.md and notes/README.md, reads BUILD_LEARNINGS.md, and
  queries Project #24 for Schedule=Now items. Run this at the start of
  every workflow skill before selecting or reading a specific issue.
  Replaces study-project-docs Phase A.
---

# Skill: Orient Agent

Load the universal baseline context every workflow skill needs. Run this
before any implementation, planning, or documentation work.

## Procedure

### Step 1 — Read the ubiquitous language glossary

Read `docs/reference/glossary.md` first to establish domain vocabulary.

### Step 2 — Load specs

Run `uv run spec-dump`. Capture the JSON output. Do **not** read raw
`specs/*.yaml` files directly.

### Step 3 — Read agent rules and active notes index

Read in parallel:

- `AGENTS.md` — agent rules, conventions, and pitfalls
- `notes/README.md` — index of active design notes (do not read individual
  notes files here; use `deepen-context` for task-specific notes)

### Step 4 — Read build observations

Read `plan/BUILD_LEARNINGS.md` for ephemeral build/bugfix observations
queued for the `learn` skill.

> **`plan/history/` is excluded.** Read it only when investigating
> completed work (e.g., during the `learn` skill).

### Step 5 — Query current priorities

```bash
bash .agents/skills/shared/query-now-epics.sh
```

This shows open Epics with `Schedule=Now` so you know what work is
currently in progress.

## Notes

- Do not skip this skill even for "small" tasks — it ensures cross-cutting
  specs (`ARCH`, `CS`, `TB`, `HP`, `SL`, `EH`) and agent rules are always
  in context.
- After orient-agent, invoke `deepen-context` with task-specific hints
  once the target issue is known.
