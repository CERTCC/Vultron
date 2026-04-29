---
title: Work Granularity and GitHub Issues Coordination
status: active
related_specs:
- specs/project-documentation.yaml
---

# Work Granularity and GitHub Issues Coordination

**Source**: IDEA-26042701 — *Implementation plan groups should be approximately
Issue or PR sized.*

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Where does this guidance live? | Extend `specs/project-documentation.yaml` (PD-09 group) | Related planning requirements already live in PD; adding a new file would fragment the spec space |
| Is PR-sizing a MUST or SHOULD? | SHOULD — a sizing recommendation, not a hard gate | Forcing strict sizing increases process viscosity; the goal is ergonomics, not enforcement |
| Should TASK-FOO sections reference GitHub issue numbers? | SHOULD when an issue exists; never block on the absence of one | Traceability is a courtesy; requiring an issue before implementation adds friction |
| What mechanism for linking Issues to sub-tasks? | GitHub sub-issues (preferred over markdown checklists) | Sub-issues provide granular tracking in the GitHub UI; checklists are invisible to search and dashboards |
| Should the spec cover the current transitional state? | Yes — explicitly permit the current monolithic IMPLEMENTATION_PLAN.md approach | Agents and contributors need to know the current state is acceptable, not a violation |

---

## The Three-Tier Model

The target state is a three-tier hierarchy for tracking work:

```text
GitHub Issue (chunky, multi-step, externally visible)
  └── TASK-FOO section in IMPLEMENTATION_PLAN.md (PR-sized, tactical)
        └── FOO.1, FOO.2, ... individual checklist items (atomic steps)
```

### Tier 1 — GitHub Issues

Large work items that:

- Require multiple PRs or multiple days of effort
- Need external visibility (collaborators, release planning)
- Benefit from discussion, labels, milestones

A parent Issue SHOULD use GitHub sub-issues to link to each child TASK-FOO
section. Markdown checklists within the Issue body are a fallback when
sub-issues aren't needed.

### Tier 2 — TASK-FOO sections

Each section in `plan/IMPLEMENTATION_PLAN.md` represents approximately one
PR worth of work:

- Reviewable and mergeable in a single PR
- Contains a clear acceptance-criteria block
- References the parent GitHub Issue number when one exists

**Sizing heuristic**: If a section would take more than one PR to complete,
split it or elevate it to a GitHub Issue with sub-issues.

### Tier 3 — Individual checklist items

The `- [ ] FOO.1` items within a TASK-FOO section. These are:

- Atomic implementation steps (single function, single file, single test)
- Not individually tracked in GitHub
- Used for day-to-day progress tracking by the developer

---

## Transition Guidance

The project is currently in transition from a monolithic
`IMPLEMENTATION_PLAN.md` (all identified tasks in one file, topic-oriented
sections) toward the three-tier model.

**Current acceptable state**:

- `IMPLEMENTATION_PLAN.md` serves as the full task registry
- GitHub Issues are used opportunistically, not systematically
- Not every TASK-FOO section has a corresponding Issue

**Target state**:

- A developer picks up a GitHub Issue
- Creates or refines the TASK-FOO section locally
- Executes the build steps
- Opens a PR that closes the Issue

Migration toward the target state should be gradual — as new significant work
is identified, create a GitHub Issue first, then plan locally. Do not
retroactively create Issues for every existing TASK-FOO section.

---

## Cross-References

- `specs/project-documentation.yaml` PD-09-001 through PD-09-005 — normative
  requirements
- `specs/project-documentation.yaml` PD-06-001 through PD-06-006 — TASK-FOO
  section format rules (headings, dot-notation IDs)
- `plan/PRIORITIES.md` — authoritative priority ordering; GitHub Issues SHOULD
  be created for items at high-priority levels (< 500) once stable
