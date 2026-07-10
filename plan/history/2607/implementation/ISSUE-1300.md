---
source: ISSUE-1300
timestamp: '2026-07-10T20:51:13.456093+00:00'
title: enrich EmitInviteActorToCaseNode — embargo stub and roles in Invite
type: implementation
---

## Issue #1300 — enrich EmitInviteActorToCaseNode — embargo stub and roles in Invite

Implemented CM-16-002 (embed active embargo details in VulnerabilityCaseStub) and CM-16-003 (embed intended CVD roles in Invite activity). CreateInviteeParticipantAtAcceptedNode reads roles from the stored Invite at accept time and sets case_roles via constructor form (PRM-05-004). Fixed a DataLayer coercion regression where semantic-subclass-only fields were lost during the as_Invite → _RmInviteToCaseActivity round-trip.

PR: <https://github.com/CERTCC/Vultron/pull/1354>
