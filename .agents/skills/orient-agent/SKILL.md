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

### Step 0 — Graph orientation (if graph exists)

If `graphify-out/graph.json` exists, sync the graph with any code changes that
landed since the last commit (fast-forward merges and cherry-picks don't fire the
post-commit hook, so the graph can be stale after a `git pull`):

```bash
graphify update . 2>/dev/null || true
```

This is AST-only — no LLM, no API key, typically a few seconds. Run it
unconditionally when the graph is present; skip silently if the file is absent.

Then read `graphify-out/GRAPH_REPORT.md`. It contains god nodes
(highest-connectivity files), surprising cross-community connections, and community
labels — the structural map of the codebase. This primes the agent with topology
context before reading docs or selecting an issue.

Skip this step silently if the file is absent.

### Step 1 — Read the ubiquitous language glossary

Read `docs/reference/glossary.md`.

### Step 2 — Load specs

Run `PYTHONPATH= uv run spec-dump 2>&1`. Capture the output. Do **not** read raw
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

If `graphify-out/graph.json` exists, run a graph query for each Now-priority
item returned. Use the issue title or affected area as the question:

```bash
graphify query "<issue title or affected area>"
```

This surfaces which graph communities each priority touches and identifies any
god nodes or surprising connections in the blast radius. Run at most one query
per Now-priority item; skip if there are no Now items.

Do not skip this skill even for small tasks. After orient-agent, invoke `deepen-context` with task-specific hints once the target issue is known.
