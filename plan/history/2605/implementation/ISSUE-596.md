---
source: ISSUE-596
timestamp: '2026-05-21T20:57:52.314809+00:00'
title: Refactor sender-side trigger use cases into SenderSideBT
type: implementation
---

## Issue #596 — Refactor sender-side trigger use cases into SenderSideBT

Moved the routing/construction/queueing pattern out of procedural `execute()`
methods and into a reusable `SenderSideBT` — a `memory=False` py_trees
Sequence — used by all participant-originated trigger use cases.

### New package: `vultron/core/behaviors/sender/`

Three BT nodes:

- `ResolveCaseManagerNode` — reads the case from the DataLayer, finds the
  `CVDRole.CASE_MANAGER` participant, and writes `case_manager_id` to the
  blackboard.
- `ConstructActivitiesNode` — calls an `activity_builder` closure supplied by
  the use case, writes returned activity IDs to the blackboard.
- `QueueToOutboxNode` — reads `activity_ids` from the blackboard, calls
  `add_activity_to_outbox` for each.

Factory function `sender_side_bt(case_id, activity_builder)` composes the
three nodes.

### Refactored use cases

- `SvcAddNoteToCaseUseCase`
- `SvcEngageCaseUseCase`, `SvcDeferCaseUseCase`
- `SvcProposeEmbargoUseCase`, `SvcAcceptEmbargoUseCase`,
  `SvcRejectEmbargoUseCase`, `SvcTerminateEmbargoUseCase`,
  `SvcProposeEmbargoRevisionUseCase`

Direct `_resolve_case_manager_id()` + `add_activity_to_outbox()` calls
removed from all nine use cases.

### Tests

11 new unit tests in `test/core/behaviors/sender/test_sender_side_bt.py`
covering success/failure paths for each node and the full tree.

Full suite: 2478 passed, 0 failures.

PR: [#619](https://github.com/CERTCC/Vultron/pull/619)
