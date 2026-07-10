---
source: ISSUE-1300
timestamp: '2026-07-10T19:39:26.498841+00:00'
title: Enrich EmitInviteActorToCaseNode — roles + embargo stub
type: implementation
---

## Issue #1300 — Enrich EmitInviteActorToCaseNode

Implemented all 6 acceptance criteria (CM-17-002/003):

- **AC-1/2**: `_build_enriched_case_stub()` in `_ActorsMixin` (adapter layer) enriches `Invite.target` with `activeEmbargo.endTime` + `caseStatus.emState=ACTIVE` when embargo is active; no embargo fields otherwise
- **AC-3**: `as_Invite` base class gains `roles: list[str] | None = None`; factory forwards it; DataLayer roundtrip preserved
- **AC-4**: `CreateInviteeParticipantAtAcceptedNode._read_invite_roles()` reads `event.object_id` → stored Invite → `roles` → sets on `VultronParticipant.case_roles` via constructor (respects mutation guard)
- **AC-5**: FVV demo passes `roles=["vendor"]` for Vendor2 invite
- **AC-6**: `InviteActorToCaseTriggerRequest` gains `roles: list[CVDRole] | None = None`; wired through FastAPI model and router

Key architectural decisions:

- Embargo enrichment delegated to adapter to avoid core→wire import violation (ARCH-01-001)
- `suggested_roles` injected into BT blackboard via `_extra_execute_kwargs()` hook

PR: <https://github.com/CERTCC/Vultron/pull/1346>
