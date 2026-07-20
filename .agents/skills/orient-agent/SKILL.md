---
name: orient-agent
description: >
  Load the always-required baseline context before any implementation,
  planning, or documentation work. Reads the glossary, loads all specs,
  reads AGENTS.md, the completeness doctrine, notes/README.md, and
  docs/adr/index.md, reads plan/incoming/learnings/, and queries Project
  #24 for Schedule=Now items. Run this at the start of every workflow
  skill before selecting or reading a specific issue. Replaces
  study-project-docs Phase A.
---

# Skill: Orient Agent

## Procedure

### Step 1 — Read the ubiquitous language glossary

Read `docs/reference/glossary.md`.

### Step 2 — Load specs

Run `uv run spec-dump 2>&1`. Capture the output. Do **not** read raw
`specs/*.yaml` files directly.

### Step 3 — Read agent rules, completeness doctrine, active notes index, and ADR index

Read in parallel:

- `AGENTS.md` — agent rules, conventions, and pitfalls
- `.claude/skills/shared/completeness-doctrine.md` — quality standard; governs what "done" means
- `notes/README.md` — index of active design notes (do not read individual notes files here; use `deepen-context`)
- `docs/adr/index.md` — overview of all ADRs; used by `deepen-context` to decide which ADRs to load

### Step 4 — Read build observations

Read all files in `plan/incoming/learnings/`. Do not read `plan/history/`.

### Step 5 — Query current priorities

```bash
bash .agents/skills/shared/query-now-epics.sh
```

Do not skip this skill even for small tasks. After orient-agent, invoke `deepen-context` with task-specific hints once the target issue is known.
