---
source: ISSUE-1901
timestamp: '2026-08-03T17:45:14.552794+00:00'
title: Leave(VulnerabilityCase) receiver-side role semantics
type: implementation
---

## Issue #1901 — feat: receiver-side role semantics for Leave(VulnerabilityCase)

Implemented CM-23-002 (owner Leave) and CM-23-003 (non-owner Leave) in the CaseActor receive path.

Key additions:

- `vultron/core/behaviors/case/nodes/leave.py`: `AdvanceParticipantToRMClosedNode`, `AdvanceCaseActorToRMClosedNode`
- `vultron/core/behaviors/case/receive_close_case_tree.py`: role-branching BT using `CheckIsCaseOwnerNode` as tree-level condition (BTND-08-001/002)
- `vultron/core/behaviors/sync/nodes/conditions.py`: `IsCloseCaseEventNode`
- `vultron/core/behaviors/sync/nodes/effects.py`: `ApplyCloseCaseFromLedgerNode` for fan-out path
- `vultron/core/behaviors/sync/announce_tree.py`: `CloseCaseEffects` slot
- Trigger side: `SvcLeaveCaseUseCase`, `LeaveCaseTriggerRequest`, `leave_case()` service method
- `demo_close_case` now uses canonical `leave_case()` path (ADR-0050) instead of direct `add_participant_status`
- 8 new tests covering all paths (receive + fan-out, owner + non-owner)

PR: <https://github.com/CERTCC/Vultron/pull/1929>
