---
title: "Plan Organization: Topic-Based Sections with Decoupled Priorities"
status: active
description: >
  Topic-based plan organization with decoupled priorities;
  IMPLEMENTATION_PLAN.md vs PRIORITIES.md separation rationale.
related_specs:
  - specs/project-documentation.md
---

# Plan Organization: Topic-Based Sections with Decoupled Priorities

## Overview

`plan/IMPLEMENTATION_PLAN.md` organizes work by topic. `plan/PRIORITIES.md`
controls ordering. The two files are kept deliberately separate so that
reprioritization does not require renaming tasks or sections.

**Formal requirements**: `specs/project-documentation.md` PD-06-001 through
PD-06-006.

---

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Where does priority live? | `plan/PRIORITIES.md` only | Priority changes frequently; topic IDs are stable references |
| What goes in PLAN headings? | `## TASK-FOO — Description` | Topic-scoped, human-readable, no priority coupling |
| How are subtasks identified? | Dot notation: `FOO.1`, `FOO.2.3a` | Structurally distinct from spec IDs (`PREFIX-NN-NNN` dashes) |
| How to avoid spec/plan ID collisions? | `TASK-` namespace for section IDs | No registry lookup needed; prefix alone disambiguates |
| Does PRIORITIES.md format change? | Section headings stay `## Priority NNN:`; body loosely references TASK-FOO | Humans edit PRIORITIES.md; rigid format adds friction |
| Migration scope | All existing sections migrated immediately | Full benefit from day one; no hybrid state |

---

## Naming Convention

### Section headings

```markdown
## TASK-FOO — Short description of the work area
```

- `FOO` is a short, uppercase, topic-specific identifier (e.g., `EMDEFAULT`,
  `BTND5`, `CC`, `AF`, `ARCHVIO`).
- `TASK-` prefix is mandatory — it prevents collisions with spec prefixes
  (e.g., `AF`, `ARCH`, `CM`) without consulting the registry.
- The `—` em-dash separator matches the existing section-heading convention.

### Task items within a section

```markdown
- [ ] FOO.1 Short task description
- [ ] FOO.2 Another task
- [ ] FOO.2.3a Sub-step within FOO.2 for complex tasks
```

- Dots only — no dashes. `FOO.1` is a plan task; `FOO-01-001` would be a
  spec ID (structurally distinct).
- Depth is unrestricted: `FOO.1`, `FOO.2.3`, `FOO.2.3.1a` are all valid.

### Section subsection headings

Use `###` for named subsections within a `TASK-FOO` section:

```markdown
### FOO.1 — Subsection name

- [ ] FOO.1a First task
- [ ] FOO.1b Second task
```

---

## PRIORITIES.md Conventions

PRIORITIES.md keeps its current `## Priority NNN: Description` heading
format. The body SHOULD name the relevant `TASK-FOO` section(s):

```markdown
## Priority 300: Default Embargo State

Correct the false EM.PROPOSED limbo state. See `TASK-EMDEFAULT` in
`plan/IMPLEMENTATION_PLAN.md`.
```

No table, no rigid structure. The reference is for humans and agents scanning
priorities — it just needs to point to the right section.

---

## Migration Examples

### Before (priority-coupled)

```markdown
## Priority 300: Protocol Correctness — Default Embargo State

### EMDEFAULT-1 — Update InitializeDefaultEmbargoNode

- [ ] EMDEFAULT-1: Update node + tests (EP-04-001)
```

### After (topic-based)

```markdown
## TASK-EMDEFAULT — Default Embargo State

### EMDEFAULT.1 — Update InitializeDefaultEmbargoNode

- [ ] EMDEFAULT.1: Update node + tests (EP-04-001)
```

### Before (section missing a heading — CC tasks)

```markdown
---

`flake8-mccabe` is already bundled...

### CC-1 — Phase 1: ...

- [ ] CC-1.1 Reduce `extract_intent` to CC≤10
```

### After

```markdown
## TASK-CC — Cyclomatic Complexity Enforcement

`flake8-mccabe` is already bundled...

### CC.1 — Phase 1: ...

- [ ] CC.1.1 Reduce `extract_intent` to CC≤10
```

---

## Choosing a TASK-FOO Identifier

1. Pick a short uppercase abbreviation that describes the topic (3–10 chars).
2. Verify it does **not** match any prefix in the `specs/README.md` prefix
   registry (e.g., `AF`, `ARCH`, `CM`, `BTND` are reserved for specs).
3. If in doubt, add a distinguishing suffix: `ARCHVIO` instead of `ARCH`,
   `BTND5` instead of `BTND`, `AFIMPL` instead of `AF`.

---

## Why Not Use the Spec Prefix?

Spec prefixes like `AF-01-001` (dash-separated) and plan task IDs like
`AF.0.1` (dot-separated) might look similar enough to cause confusion.
With `TASK-AF` as the section heading and `AF.1`, `AF.2` as task IDs, the
dot-only convention provides one layer of disambiguation. But when the
topic-FOO happens to match a spec prefix exactly (as `AF` does), an agent
scanning `AF.1` could still misread it as a spec variant.

The `TASK-` prefix on section headings makes the section itself unambiguous.
Task IDs derived from the topic are naturally scoped to that section by
context (they appear under `## TASK-FOO`), so the dot notation is sufficient
for task items.

---

## Load When

Load this file when:

- Adding a new section to `plan/IMPLEMENTATION_PLAN.md`
- Assigning or changing a priority for a plan section
- Reviewing or updating `plan/PRIORITIES.md`
- Auditing the plan for sections that still use old priority-heading or
  dash-notation task IDs
