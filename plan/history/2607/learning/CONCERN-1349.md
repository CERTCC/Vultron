---
source: CONCERN-1349
timestamp: '2026-07-13T20:23:40.599054+00:00'
title: 'concern: new_case_participant / participant_case / new_participant_id blackboard
  keys are un-namespaced in participant_add/owner nodes'
type: learning
---

## Summary

`vultron/core/behaviors/case/nodes/participant/participant_add.py` and
`owner.py` use flat blackboard keys `new_case_participant`, `participant_case`,
and `new_participant_id` as inter-node handoffs within the participant-add
subtree. These keys are not namespaced by an execution-scoped ID.

Like `suggested_roles` (CONCERN-1335), these keys would collide if two
`create_receive_report_case_tree` executions ran concurrently — e.g., if two
`Offer(VulnerabilityReport)` messages arrived simultaneously. This tree fires
on every incoming report submission, making the collision frequency higher
than for the suggest-actor workflow.

## Current status

Latent today — the BTBridge `RLock` serializes all BT executions within a
single process. Becomes a live data-corruption hazard if:

- Actor-level parallelism or async delivery is introduced
- Multiple parallel report submissions are processed concurrently

## Proposed resolution

Namespace the three keys by `report_id` segment (already available in the
blackboard and as a constructor arg for most nodes in this subtree).

**Resolved**: 2026-07-13 — implementation tracked in #1397.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1396>.
Notes: `notes/bt-integration.md` § "Namespaced Inter-Node Handoff Keys".
