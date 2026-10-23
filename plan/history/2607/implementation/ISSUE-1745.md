---
source: ISSUE-1745
timestamp: '2026-07-28T14:48:59.687511+00:00'
title: suggest-actor roles read from stored Offer, not blackboard
type: implementation
---

## Issue #1745 — Bug: suggest-actor ADR-0026 path assigns CVDRole.COORDINATOR instead of CVDRole.VENDOR

Root cause: EmitInviteActorToCaseNode._read_suggested_roles() read from the py_trees blackboard, which is empty in BT execution 2 (separate BTBridge call). The suggested_roles key is only written in BT execution 1.

Fix: AcceptOfferCaseParticipantReceivedUseCase.execute() now reads the stored Offer from DataLayer by ID, extracts stored_participant.roles, serializes the roles, and threads them through create_accept_actor_recommendation_received_tree() → EmitInviteActorToCaseNode as a constructor injection. The received Accept is untrusted (acceptor may modify contents or send a bare ID).

Two regression tests in TestRolesFromStoredOffer cover Invite.roles and full round-trip participant.case_roles.

PR: <https://github.com/CERTCC/Vultron/pull/1750>
