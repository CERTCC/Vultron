---
title: "AGENTS.md Structure: Routing Policy and Per-Directory Files"
status: active
description: >
  Policy for deciding what belongs in root AGENTS.md vs. per-directory
  AGENTS.md files vs. notes/ files. Establishes the routing decision tree
  that keeps root AGENTS.md under 400 lines and agent guidance close to
  where it is needed.
related_notes:
  - notes/agentic-workflow.md
  - notes/spec-registry.md
  - notes/parallel-development.md
related_specs:
  - specs/project-documentation.yaml
---

# AGENTS.md Structure: Routing Policy and Per-Directory Files

## Why This Matters

`AGENTS.md` at the repository root is the entry point for every AI coding
agent. It is also the highest-churn guidance file (87+ changes in 90 days at
the time this note was written). When AGENTS.md grows without bound it:

1. Takes longer to load into agent context windows.
2. Gets outdated faster because every subsystem's changes accumulate in one
   file.
3. Buries the most relevant guidance under unrelated content.

The fix is to keep root AGENTS.md as a **navigation hub** and push
domain-specific guidance into per-directory `AGENTS.md` files or into
`notes/` design notes.

---

## Routing Decision Tree

Use the following decision tree to decide where new content belongs:

```text
Is this guidance about a specific subdirectory of the codebase?
  YES → Per-directory AGENTS.md (see below)
  NO  → Is this a durable design decision or architectural rationale?
          YES → notes/<topic>.md  (referenced from AGENTS.md)
          NO  → Is this a project-wide convention or commit-workflow rule?
                  YES → Root AGENTS.md (keep it short)
                  NO  → It probably belongs in a spec or ADR
```

### Root AGENTS.md — keep to project-wide, cross-cutting content

- Technology stack constraints and setup commands
- Cross-cutting naming conventions (not layer-specific ones)
- The commit workflow (format → lint → test → commit)
- Skill interaction rules (ask\_user policy)
- Governance note
- **Short pitfall entries** that apply everywhere, with `see notes/X.md`
  pointers for the full write-up
- A `> **Topic** has moved to <dir>/AGENTS.md` stub when content migrates

Target: **≤ 400 lines**. If root AGENTS.md exceeds 400 lines, run the
`condense-agents-md` skill.

### Per-directory AGENTS.md — subsystem-specific rules

Create an `AGENTS.md` in any directory whose conventions, pitfalls, or
patterns are specific enough that agents working elsewhere would never need
them. Canonical locations and the content they own:

| Directory | Content it owns |
|-----------|-----------------|
| `vultron/core/` | Domain model invariants, BT integration rules, use-case protocol |
| `vultron/wire/as2/` | ActivityStreams wire conventions, extractor ordering, pattern naming |
| `vultron/adapters/` | Hexagonal-layer boundary rules, FastAPI adapter conventions |
| `test/` | Test data quality rules, fixture isolation, parallelism notes |

Each per-directory file SHOULD start with:

```markdown
# AGENTS.md — <Directory Name>

> For project-wide conventions, see the root [AGENTS.md](../../AGENTS.md).

## <Subsystem> Conventions

...
```

### notes/<topic>.md — durable design decisions

Use `notes/` for content that explains **why** a decision was made, not just
**what** the rule is. Notes files are the right home for:

- Pitfall write-ups with context, root cause, and example code
- Architecture decision rationales that didn't warrant a full ADR
- Design patterns and their tradeoffs

Every note must have valid YAML frontmatter (`title`, `status`). Reference
the note from the nearest AGENTS.md with a one-line summary and a link.

---

## Migration Pattern

When root AGENTS.md exceeds 400 lines or when a pitfall clearly belongs in
a per-directory file:

1. Run the `condense-agents-md` skill — it automates the extraction.
2. Replace the moved content with a stub:

   ```markdown
   > **Topic** has moved to [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
   ```

3. Ensure the per-directory file is created with proper headings and a
   back-reference to root AGENTS.md.

---

## Related notes

- `notes/agentic-workflow.md` — the four-skill pipeline (ingest-idea, learn,
  update-plan, build)
- `notes/parallel-development.md` — worktree slots and concurrent agent work
- `notes/spec-registry.md` — how spec prefixes are registered and discovered
