---
title: "AGENTS.md Structure: Routing Policy and Per-Directory Files"
status: active
kind: guidance
description: >
  Where new agent guidance goes: root AGENTS.md, a per-directory AGENTS.md, or
  a notes/ file. Sets the size budgets the ratchet test enforces and the
  trim-as-you-add rule for the root pitfall index.
related_notes:
  - notes/agentic-workflow.md
  - notes/parallel-development.md
  - notes/site-information-architecture.md
related_specs:
  - specs/project-documentation.yaml
  - specs/meta-specifications.yaml
---

# AGENTS.md Structure: Routing Policy and Per-Directory Files

Root `AGENTS.md` is loaded by `orient-agent` at the start of every workflow
skill. Past the point where an agent reliably reads it end to end, extra
pitfalls stop protecting against the mistakes they describe. Keep root a
navigation hub and push domain guidance next to the code it governs.

---

## Routing Decision Tree

```text
Is this guidance about a specific subdirectory of the codebase?
  YES → that directory's AGENTS.md
  NO  → Is it a rule for changing the project, with a reason?
          YES → notes/<topic>.md, linked from the nearest AGENTS.md
          NO  → Is it a project-wide convention or commit-workflow rule?
                  YES → root AGENTS.md (keep it short)
                  NO  → it probably belongs in a spec or ADR
```

### Root AGENTS.md — project-wide, cross-cutting content

Technology stack and setup commands, cross-cutting naming conventions, the
commit workflow, skill interaction rules, the governance note, and the pitfall
index: one row per symptom area, pointing at the note that holds the write-up.

### Size budgets

Root is budgeted at **400 lines** and each per-directory `AGENTS.md` at **200**.
`test/metadata/test_agents_md_size_ratchet.py` enforces both. Files that
predate the ratchet carry a ceiling in its `KNOWN_OVERAGE` map; a ceiling may
only be lowered. Condense the file with the `condense-agents-md` skill rather
than raising a ceiling (ISSUE-2954).

**Root runs close to its budget, so assume no headroom.** Adding to the root
pitfall index means trimming as you add: extend an existing row's cell or fold
two rows together. A new symptom area that needs its own row pays for it by
condensing another. Read the current count from the file, not from a note
(MS-16-001).

### Per-directory AGENTS.md — subsystem-specific rules

Create an `AGENTS.md` in any directory whose conventions or pitfalls are
specific enough that agents working elsewhere would never need them. Start it
with a back-reference to root:

```markdown
# AGENTS.md — <Directory Name>

> For project-wide conventions, see the root [AGENTS.md](../../AGENTS.md).
```

### notes/<topic>.md — rules with their reasons

A note holds guidance too long for an index row, or a plan for work not yet
done. Write it per
[`notes-writing-guide.md`](../.agents/skills/shared/notes-writing-guide.md):
one `kind`, each item a rule, its reason and one citation. Link it from the
nearest `AGENTS.md` with a one-line summary.

---

## Moving Content Out of Root

When root nears its budget, or a pitfall clearly belongs to one directory, run
the `condense-agents-md` skill. Leave a one-line stub where the content was:

```markdown
> **Topic** has moved to [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
```
