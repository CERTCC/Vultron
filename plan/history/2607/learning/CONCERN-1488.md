---
source: CONCERN-1488
timestamp: '2026-07-17T18:56:00.086972+00:00'
title: inline factory calls in update() methods exceed BTND-07-003 god-node limit
type: learning
---

## Concern

During the review of PR #1481 (split `suggest_actor_tree.py`), god-node decomposition was applied to `emit.py`'s four `update()` methods. The `_emit()` helper pattern used there has broad applicability: at least 9 other `update()` methods across 5 files follow the same inline factory call pattern and several already exceed the ~20–30 line BTND-07-003 limit.

## Affected files and approximate update() line counts

| File | Class | Lines |
|---|---|---|
| `case/nodes/actor.py` | `EmitInviteActorToCaseNode` | ~80 |
| `status/nodes/lifecycle.py` | `AutoCloseBranchNode` | ~73 |
| `case/nodes/delegation.py` | `AutoAcceptCaseManagerRoleNode` | ~67 |
| `case/nodes/delegation.py` | `CreateOfferCaseManagerActivityNode` | ~66 |
| `case/nodes/delegation.py` | `EmitRejectCaseManagerRoleNode` | ~54 |
| `case/nodes/actor.py` | `ProposeCaseToActorNode` | ~45 |
| `embargo/nodes/lifecycle.py` | `SendTerminateEmbargoActivityNode` | ~40 |
| `report/nodes/emit.py` | `EmitSubmitReportActivity` | ~39 |
| `note/nodes/creation.py` | `CreateNoteNode` | ~35 |

## Pattern

Each `update()` method assigns `factory = self.trigger_activity_factory`, then
calls `factory.some_method(...)` inline along with pre/post-condition logic,
logging, and outbox writes. The fix is mechanical: extract the factory call into
`_emit()` (or `_build_*()` for content construction) so `update()` only
orchestrates.

`report/nodes/emit.py` already has a good model: a `_call_factory()` hook in a
base class that subclasses override. `EmitSubmitReportActivity` is the one
outlier that missed that pattern.

## Root cause

Both: no generalized base class existed AND code was copied from early procedural
implementations. The `_EmitCaseActorReportActivityBase` pattern existed only in
`report/nodes/emit.py` and was never generalized or documented as the expected
approach for all emit nodes.

## Spec/notes gaps identified

- `BTND-07-005` added to `specs/behavior-tree-node-design.yaml`: MUST search for
  existing base classes before reimplementing guard/factory boilerplate.
- AGENTS.md pitfall added: "BT Emit Nodes: Inherit Base Classes, Never Reimplement
  Guard Boilerplate" — names `DataLayerAction` and `_EmitCaseActorReportActivityBase`
  explicitly.

**Resolved**: 2026-07-17 — implementation tracked in #1499.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1498>.
Spec: `specs/behavior-tree-node-design.yaml` BTND-07-005.
