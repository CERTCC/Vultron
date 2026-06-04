---
source: ISSUE-749
timestamp: '2026-06-04T17:15:31.024518+00:00'
title: 'God node decomposition: split BroadcastStatusToPeersNode into composed subtree'
type: implementation
---

## Issue #749 — God node decomposition: split BroadcastStatusToPeersNode into composed subtree

Decomposed the 84-line monolithic `BroadcastStatusToPeersNode.update()` god node
into four named leaf BT nodes composed via a `py_trees.composites.Selector`,
following the `PublicDisclosureBranchNode` pattern already established in the
codebase. Implements BTND-07-001 (decompose god BT nodes) per issue #749, child
of Epic #764 (BT Deepening).

**New leaf nodes added to `vultron/core/behaviors/status/nodes.py`:**

- `FindCaseManagerNode` — resolves CASE_MANAGER actor ID to `broadcast_case_manager_id` blackboard key
- `FilterPeerRecipientsNode` — filters eligible peer recipients to `broadcast_peer_recipient_ids` blackboard key
- `CreateStatusBroadcastActivityNode` — calls `trigger_activity_factory` to `broadcast_activity_id` blackboard key
- `BroadcastQueueToOutboxNode` — queues activity to Case Manager outbox

**`BroadcastStatusToPeersNode` refactored** from `DataLayerAction` to
`py_trees.composites.Selector(memory=False)`:

- BroadcastWorkSequence (Sequence) with 4 leaf nodes
- py_trees.behaviours.Success non-fatal fallback

Behavioral contract preserved: always returns SUCCESS; only `VultronError`
caught; non-`VultronError` exceptions propagate normally. Blackboard keys
namespaced with `broadcast_` prefix to avoid conflicts with sender layer.

Added 18 new unit tests across 4 new test classes. All 4 existing
`TestBroadcastStatusToPeersNode` tests continue to pass. All 2804 tests pass.

PR: [#778](https://github.com/CERTCC/Vultron/pull/778)
