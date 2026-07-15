---
source: ISSUE-1406
timestamp: '2026-07-14T19:31:25.529920+00:00'
title: verify suggest-actor roles threading
type: implementation
---

## Issue #1406 — Verify/document suggest-actor received path roles threading

Added integration and unit tests to document and verify that roles from `Accept(Offer(CaseParticipant))` are NOT propagated into the Invite in the `create_accept_actor_recommendation_received_tree` path (because `suggested_roles` is absent from the blackboard), and that `VultronParticipant.case_roles` is therefore `[]`.

PR: <https://github.com/CERTCC/Vultron/pull/1427>

AC-1: `TestAcceptOfferCaseParticipantRolesThreading.test_participant_case_roles_empty_after_full_round_trip` — full round-trip integration test
AC-2: `TestEmitInviteActorToCaseNodePassesRolesNoneToFactory.test_invite_actor_to_case_called_with_roles_none` + `TestAcceptOfferCaseParticipantRolesThreading.test_invite_roles_none_when_no_blackboard_key` — factory receives roles=None when suggested_roles absent (ADR-0032, BT-HELPER-01)
