---
title: "P360-AUDIT \u2014 BT Composability Audit"
type: implementation
timestamp: '2026-04-23T00:00:00+00:00'
source: P360-AUDIT
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7891
legacy_heading: "P360-AUDIT \u2014 BT Composability Audit (COMPLETE 2026-04-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-23'
---

## P360-AUDIT — BT Composability Audit

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7891`
**Canonical date**: 2026-04-23 (git blame)
**Legacy heading**

```text
P360-AUDIT — BT Composability Audit (COMPLETE 2026-04-23)
```

**Legacy heading dates**: 2026-04-23

**Task**: Audit existing BT nodes in `vultron/core/behaviors/` against
`specs/behavior-tree-node-design.yaml`; produce a task list of refactoring work.

**Findings**:

Three composability violations were identified and added to
`plan/IMPLEMENTATION_PLAN.md` as P360-FIX-1 through P360-FIX-3:

1. **P360-FIX-1** — `UpdateActorOutbox` duplicated in `report/nodes.py` and
   `case/nodes.py` (BTND-04-001, BTND-02-001); extract to `helpers.py`.

2. **P360-FIX-2** — `CreateInitialVendorParticipant` and
   `CreateCaseParticipantNode` share overlapping DataLayer write logic with
   different (non-identical) semantics (BTND-02-001); extract a shared
   `_create_and_attach_participant()` helper function; keep thin wrappers.

3. **P360-FIX-3** — `RecordCaseCreationEvents` (and possibly other nodes)
   read blackboard keys without declaring them in `setup()` (BTND-03-001,
   BTND-03-002); audit all nodes and add `register_key()` calls.
