---
title: "P360-NOTES \u2014 BT Reusability and Composability Design Notes (2026-04-23)"
type: implementation
timestamp: '2026-04-23T00:00:00+00:00'
source: P360-NOTES
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7799
legacy_heading: "P360-NOTES \u2014 BT Reusability and Composability Design\
  \ Notes (2026-04-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-23'
---

## P360-NOTES — BT Reusability and Composability Design Notes (2026-04-23)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7799`
**Canonical date**: 2026-04-23 (git blame)
**Legacy heading**

```text
P360-NOTES — BT Reusability and Composability Design Notes (2026-04-23)
```

**Legacy heading dates**: 2026-04-23

**Task**: Create `notes/bt-reusability.md` capturing the fractal composability
pattern from `vultron/bt/`, the "trunkless branch" intent, and anti-patterns
(one-off nodes, hard-coded actor roles, demo-specific subtrees).

**Deliverable**: `notes/bt-reusability.md` (556 lines)

**Content**:

1. **Foundational Concepts** — Trunk-Removed Branches Model: the event-driven
   prototype maps incoming activities to focused BT subtrees extracted from
   the canonical simulation BT structure.

2. **Fractal Composability Pattern** — Definition and example (parameterized
   participant creation): BT nodes are self-contained, parameterized
   components that nest at multiple levels without losing coherence.

3. **Anti-Patterns to Avoid**:
   - Hard-coded actor roles
   - Demo-specific logic in reusable nodes
   - One-off subtrees coupled to specific workflows
   - Duplicate subtrees with slight variations

4. **Node Design Guidelines** — Parameterization, blackboard key naming,
   isolation from demo context.

5. **Composability Patterns** — Subtree composition, Selector for alternatives,
   Sequence for ordered steps.

6. **Testing Composability** — How to test reusable BT nodes in isolation,
   with parameterization, and within parent trees.

7. **Anti-Pattern Reference (Quick Checklist)** — Verification before adding
   new BT code.

**Validation**:

- `./mdlint.sh notes/bt-reusability.md` → 0 errors
- File references canonical structure in `notes/vultron-bt.txt` and formal
  requirements in `specs/behavior-tree-integration.yaml`
- Ready for use in P360-SPEC (spec writing) and P360-AUDIT (node auditing)
