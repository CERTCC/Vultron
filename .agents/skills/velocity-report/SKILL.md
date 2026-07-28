---
name: velocity-report
description: Run the development velocity script and interpret the resulting data to find the story the data is telling. Produces a narrative analysis of issue flow, type composition shifts, discovery vs. delivery balance, and cycle time patterns — suited for sponsor reporting, process retrospectives, or internal review. Use when the user asks for a velocity report, development tempo analysis, project health summary, or "what's the data saying about our progress".
---

# Velocity Report

## Quick start

```bash
uv run python scripts/velocity.py
```

Output lands at `plan/data/velocity.json`. Then interpret it (see below).

## Interpretation workflow

After running the script, load `plan/data/velocity.json` and work through these analytical lenses in order. Each lens produces one or two observations. Collect all observations, then synthesize into a narrative.

### 1. Discovery tempo (Idea + Concern creation rate)

- Are Idea and Concern issues being created at a steady rate, accelerating, or declining?
- A *rising* rate = active discovery phase, team is finding new unknowns
- A *declining* rate = discovery is maturing, specs are hardening
- A *flat* rate = steady-state exploration
- Flag any months where creation rate spikes — what was happening?

### 2. Discovery resolution ratio (closed / created per type)

- For Ideas: ratio < 1.0 means backlog is growing (more discovered than resolved)
- For Concerns: ratio < 1.0 means technical debt is accumulating faster than it's addressed
- Compare Idea vs. Concern ratios — are they in sync or diverging?
- Idea resolution is intentionally slower (Ideas → planning → Tasks); Concern resolution should be faster

### 3. Type composition shift over time

Look at `created_by_month` as a stacked view across all types:

- Is the Bug share *rising* over time? That signals implementation work has started and is producing breakage — a healthy sign for a project transitioning from discovery to execution
- Is the Task share *rising*? Requirements are being converted to concrete work items
- Is Untyped share *falling*? Workflow discipline is improving
- The narrative arc to look for: **Idea/Concern-heavy early → Task/Bug-heavy later**

### 4. Backlog pressure by type (`open_backlog_by_month`)

- Which types are accumulating open issues vs. staying clear?
- A growing Idea backlog = healthy (discovery outpacing planning capacity) OR concerning (ideas never get planned) — context determines which
- A growing Bug backlog = implementation quality pressure
- A growing Epic backlog = structural work is outpacing capacity to decompose

### 5. Cycle time interpretation (`cycle_time_by_type`)

Compare median days to close across types:

- **Bugs** should be fast (same-day to 2 days) — if median > 5 days, implementation is getting stuck
- **Tasks** should be 3–10 days — longer suggests over-scoping
- **Concerns** should be faster than **Ideas** — Concerns are addressed; Ideas need planning cycles
- **Ideas** with long cycle time (>10 days) = healthy planning depth; very short = Ideas being closed without full planning
- **Epics** cycle time reflects decomposition cadence, not implementation

### 6. Throughput balance (`created_by_month` vs `closed_by_month`)

- For each type: is monthly closed ≥ monthly created? If not, what's accumulating?
- Sustained deficit on any type for 2+ months = a process signal worth naming
- Bugs: should roughly balance (bugs fixed ≈ bugs found in a mature phase)
- Ideas: expect deficit during active discovery; surplus signals planning is processing faster than discovering

## Synthesis

After working through the lenses, write a narrative with:

1. **Phase characterization** — where is the project in its arc right now? (active discovery / transitioning / execution-heavy)
2. **Healthy signals** — 2–3 specific data points that show the process is working
3. **Tension points** — 1–2 patterns that deserve attention (not necessarily problems)
4. **One sentence for sponsors** — what does this data say about the nature and pace of the work?

## Example observations from 2026-05 to 2026-07 data

- Idea creation: 14 → 34 → 45/month — accelerating discovery, not converging
- Concern creation: 22 → 28 → 41/month — technical debt awareness growing in parallel
- Bug creation: 34 (May spike) → 7 → 17 — May spike likely from initial implementation; stabilizing
- Idea cycle time median 10 days vs. Concern 1 day — Ideas are going through planning cycles; Concerns are quick-resolving
- Task creation 16 → 38 → 55/month — delivery work is ramping up alongside discovery (healthy dual-track)
- Concern resolution ratio June: 40 closed / 28 created = 1.43 — team caught up with Concern backlog in June

These are examples; run the script fresh and re-analyze — the data changes weekly.
