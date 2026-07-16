---
source: CONCERN-1335
timestamp: '2026-07-10T19:57:34.629377+00:00'
title: 'concern: EvaluateDefaultRolesNode uses global blackboard namespace — key collision
  under concurrent BT execution'
type: learning
---

`EvaluateDefaultRolesNode.setup()` registers `suggested_roles` in the global
py_trees blackboard namespace (no `namespace=` argument). If two
`RecommendActorToCaseBT` trees are instantiated and ticked in the same
py_trees session simultaneously — e.g., two concurrent
`Offer(Actor, Case)` inbox messages — the second write to `suggested_roles`
silently overwrites the first, causing the first tree's
`EmitOfferCaseParticipantToOwnerNode` to read the wrong role list.

Latent today — inbox processing is sequential per-actor, so two simultaneous
`RecommendActorToCaseBT` executions cannot race under the current delivery
model. Becomes a live data-corruption hazard if concurrent BT execution is
introduced (e.g., async inbox with parallel delivery) or a future Evaluator
replacement (e.g., #1142) is wired without fixing the namespace first.

**Resolved**: 2026-07-10 — implementation tracked in #1348. Follow-up concern
for participant_add/owner cluster filed in #1349.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1347>.
Spec: `specs/behavior-tree-node-design.yaml` BTND-03-004.
Notes: `notes/bt-integration.md` § "Namespaced Inter-Node Handoff Keys".
