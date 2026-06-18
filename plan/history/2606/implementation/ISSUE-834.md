---
source: ISSUE-834
timestamp: '2026-06-18T16:19:13.499032+00:00'
title: Shared fail-fast peer broadcast BT helper
type: implementation
---

## Issue #834 — Implement shared fail-fast peer broadcast helper for BT fan-out

Introduced `vultron/core/behaviors/broadcast/` — a new package providing
reusable, fail-fast BT leaf nodes and a `peer_broadcast_bt()` factory for all
protocol-visible peer fan-out subtrees (BT-14-001, BT-14-002).

### What was built

- `FindCaseManagerNode`, `FilterPeerRecipientsNode`,
  `CreateBroadcastActivityNode`, `BroadcastQueueToOutboxNode` leaf nodes
  with a documented blackboard contract
- `peer_broadcast_bt()` factory — builds a plain `memory=False` Sequence
  with no guaranteed-SUCCESS fallback; FAILURE propagates on broadcast
  preparation or outbox enqueue errors
- `BroadcastStatusToPeersNode` refactored to delegate to the shared nodes,
  replacing the old `Selector+Success` anti-pattern
- `CreateStatusBroadcastActivityNode` fixed with missing empty-list guard
  (previously called factory with `to=[]` when no peers remained)
- Stale-blackboard regression fix: `CreateBroadcastActivityNode` now writes
  `None` sentinel on the no-op path so `BroadcastQueueToOutboxNode` does not
  re-enqueue a previous execution's activity

### Tests

3 new regression tests added; all 3519 unit tests pass.

### PR

[PR #1040](https://github.com/CERTCC/Vultron/pull/1040)
