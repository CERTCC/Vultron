---
source: MODULE-IDEM-SET
timestamp: '2026-06-22T19:35:39.817071+00:00'
title: 'Idempotency set pairing: always write and read the same blackboard key'
type: learning
---

BT nodes that implement idempotency guards via a blackboard set (e.g.,
`processed_activity_ids`) MUST use exactly the same key for both the read
(membership check) and the write (set insertion). A mismatch where the
check reads from key A but the insertion writes to key B means every
re-tick re-enters the protected subtree, silently duplicating protocol
effects. Tests must explicitly verify the set contains the expected ID
after the first successful tick, and verify the node returns a no-op
result on repeat ticks.

**Promoted**: 2026-06-22 — captured in `specs/behavior-tree-integration.yaml`
(BT-17-002: idempotency set pairing) and `notes/bt-integration.md`
(Role Guard for All CASE_MANAGER-Only Subtrees section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
