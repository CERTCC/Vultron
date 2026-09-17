---
source: NOTES-agentic-workflow--priority-interrupt-loop
timestamp: '2026-09-17T17:13:36.385252+00:00'
title: Priority-Interrupt Loop
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,e) keyed on retired BUILD_LEARNINGS.md / ingest-idea
**Superseded by:** specs/build-workflow.yaml

---

## Priority-Interrupt Loop

The pipeline runs as a loop. On each iteration, the agent checks trigger
conditions in priority order and runs the first matching skill. After the
skill completes, the loop restarts — higher-priority skills always preempt
lower-priority ones.

```mermaid
flowchart TD
    START([🔄 Loop start]) --> CHK_IDEAS{Open Idea-type\nGitHub issues?}

    CHK_IDEAS -->|Yes| INGEST["🌱 ingest-idea\nGitHub idea → specs/ + notes/"]
    INGEST --> START

    CHK_IDEAS -->|No| CHK_NOTES{plan/incoming/learnings/\nhas unprocessed\nfiles?}

    CHK_NOTES -->|Yes| LEARN["🧠 learn\nplan/incoming/learnings/ → specs/ + notes/ + AGENTS.md"]
    LEARN --> START

    CHK_NOTES -->|No| CHK_SPECS{specs/ or notes/\nchanged since last\nplan update?}

    CHK_SPECS -->|Yes| UPDATE["📋 update-plan\nspecs/notes/code → GitHub Issues"]
    UPDATE --> START

    CHK_SPECS -->|No| CHK_TASKS{Open GitHub Issues\nin top-priority group?}

    CHK_TASKS -->|Yes| BUILD["🔨 build\ntask → code + tests"]
    BUILD --> START

    CHK_TASKS -->|No| DONE([✅ Done])
```

---
