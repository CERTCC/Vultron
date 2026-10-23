---
title: "P360-SPEC \u2014 BT Node Design Spec"
type: implementation
timestamp: '2026-04-23T00:00:00+00:00'
source: P360-SPEC
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7872
legacy_heading: "P360-SPEC \u2014 BT Node Design Spec (COMPLETE 2026-04-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-23'
---

## P360-SPEC — BT Node Design Spec

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7872`
**Canonical date**: 2026-04-23 (git blame)
**Legacy heading**

```text
P360-SPEC — BT Node Design Spec (COMPLETE 2026-04-23)
```

**Legacy heading dates**: 2026-04-23

**Task**: Create `specs/behavior-tree-node-design.yaml` (formal requirements for
BT node parameterization and composability) and register `notes/bt-reusability.md`
in relevant index files.

**Changes**:

- Created `specs/behavior-tree-node-design.yaml` with formal requirements
  BTND-01 through BTND-04 covering node parameterization, composability and
  reuse, blackboard interface contracts, and module ownership.
- Updated `specs/README.md`: registered `behavior-tree-node-design.md` in the
  BT section, contextual load table, and `BTND` prefix registry.
- Updated `notes/bt-reusability.md`: replaced "(TBD via P360-SPEC)" references
  with the actual spec file and requirement IDs.
- Updated `notes/README.md`: added `bt-reusability.md` entry to the BT section.
