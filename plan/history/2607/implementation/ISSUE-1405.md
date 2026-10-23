---
source: ISSUE-1405
timestamp: '2026-07-14T18:31:03.598582+00:00'
title: 'Verify roles-threading end-to-end: InviteActorToCaseTriggerRequest → CaseParticipant.case_roles'
type: implementation
---

## Issue #1405 — Verify roles-threading end-to-end: InviteActorToCaseTriggerRequest → CaseParticipant.case_roles

Added three acceptance-criteria tests for the roles-threading path:

- AC-1/AC-2: integration round-trip in TestRolesThreadingIntegration (test_actor_triggers.py)
- AC-3: unit test for EmitInviteActorToCaseNode._read_suggested_roles() KeyError path (test_actor_and_announce_nodes.py)

PR: <https://github.com/CERTCC/Vultron/pull/1420>
