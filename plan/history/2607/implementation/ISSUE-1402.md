---
source: ISSUE-1402
timestamp: '2026-07-17T15:12:30.058138+00:00'
title: split suggest_actor_tree.py into nodes/suggest_actor/ subpackage
type: implementation
---

## Issue #1402 — refactor: split suggest_actor_tree.py (778 lines) into suggest_actor/ subpackage

suggest_actor_tree.py grew to 802 lines (threshold: 500 per BTND-07-004/CS-18-002). Split into nodes/suggest_actor/ subpackage following the nodes/participant/ pattern.

New files:

- nodes/suggest_actor/emit.py (401 lines): EmitOfferCaseParticipantToOwnerNode, EmitAcceptActorRecommendationNode, EmitRejectActorRecommendationNode, EmitNoteDuplicateRecommendationToOwnerNode
- nodes/suggest_actor/conditions.py (168 lines): ActorAlreadyParticipantNode, InviteInFlightNode, PendingOfferCaseParticipantNode
- nodes/suggest_actor/**init**.py: re-export facade

suggest_actor_tree.py reduced to 308 lines (factory functions only). case/nodes/**init**.py updated with 7 new re-exports.

All 4834 tests pass. BTND07 structural ratchet: 68/68. All linters clean. Backward compat maintained.

PR: <https://github.com/CERTCC/Vultron/pull/1481>
