---
name: orient-agent
description: >
  Load the always-required baseline context before any implementation,
  planning, or documentation work. Reads the glossary term index, loads the
  spec map (topic/group index, not the requirements), reads AGENTS.md, the
  completeness doctrine, and the incoming-learnings index, and queries Project
  #24 for Schedule=Now items. Run this at the start of every workflow skill
  before selecting or reading a specific issue. Task-specific context —
  requirements, notes, ADRs, glossary sections, code — is loaded afterwards
  by deepen-context. Replaces study-project-docs Phase A.
---

# Skill: Orient Agent

Orientation loads **maps and rules**, not content. Everything here is small
enough to read whole; the content the maps point to is loaded by
`deepen-context` once the task is known.

## Procedure

### Step 1 — Read the glossary term index

Run `PYTHONPATH= uv run glossary-index`. It lists every glossary term with the
aliases to avoid for it, grouped by section with line ranges. Use the
glossary's terms, not the aliases, when naming anything. `deepen-context`
reads the full sections (definitions, Flagged Ambiguities) the task needs.

### Step 2 — Load the spec map

Run `PYTHONPATH= uv run spec-dump --index`. The output is a **map, not the
requirements**: topic headers plus one line per requirement group with counts.
Use it to see which topics and groups exist; do not treat it as having read any
requirement. `deepen-context` loads the actual requirements once the task is
known, using this map to select topics and groups.

Do **not** run `spec-dump` with no filters here — the full dump is far larger
than an agent reads end to end, so only a truncated prefix is ever seen. Do
**not** read raw `specs/*.yaml` files directly.

### Step 3 — Read agent rules and completeness doctrine

Read in parallel:

- `AGENTS.md` — agent rules, conventions, and pitfalls
- `.agents/skills/shared/completeness-doctrine.md` — quality standard; governs what "done" means

### Step 4 — Read the build-observation index

```bash
PYTHONPATH= uv run learnings-index
```

Each incoming learning's title states the lesson in full, so the index
carries what the directory says at ~5% of the bytes. Read
`plan/incoming/learnings/<file>` for the evidence behind any title that bears
on your task. Do not read `plan/history/`.

### Step 5 — Query current priorities

```bash
bash .agents/skills/shared/query-now-epics.sh
```

Do not skip this skill even for small tasks. Once the target issue is known,
invoke `deepen-context` with focus hints and the issue's spec floor (its
`Governing specs:` line and any spec IDs it cites).
