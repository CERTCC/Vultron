---
source: BROADCAST-834-STALE-BLACKBOARD
timestamp: '2026-06-22T19:36:10.212950+00:00'
title: Stale blackboard keys cause incorrect broadcast recipient resolution
type: learning
---

When a broadcast subtree writes `recipient_ids` to the blackboard before
iterating participants, a re-tick from a previous FAILURE can use a stale
`recipient_ids` value if the key is not cleaned up on Sequence exit. Always
clear transient broadcast keys (`recipient_ids`, `current_recipient`, etc.)
in the Sequence teardown or in a dedicated `CleanupBroadcastBlackboardNode`
leaf. This is a concrete case of the `memory=False` partial-write hazard:
the iteration state is written before fan-out, so idempotency must be
enforced both for the set insertion and the cleanup path.

**Promoted**: 2026-06-22 — captured in `specs/behavior-tree-integration.yaml`
(BT-17-003: no-op blackboard cleanup; BT-17-004: consumer sentinel handling)
and `notes/bt-integration.md` (Stale Blackboard Keys in Broadcast Subtrees section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
