---
source: ISSUE-1383
timestamp: '2026-07-14T17:44:53.215675+00:00'
title: 'fix: enforce non-empty invariant in EvaluateDefaultRolesNode'
type: implementation
---

## Issue #1383 — fix: enforce non-empty invariant in EvaluateDefaultRolesNode; remove silent-override bypass in _read_suggested_roles()

Added `_compute_roles()` hook to `EvaluateDefaultRolesNode` so `update()` returns `FAILURE` when the computed role list is empty (AC-1, CM-16-003). Removed `and roles` bypass from `EmitOfferCaseParticipantToOwnerNode._read_suggested_roles()` (AC-2). Added fail-fast empty-roles guard in `EmitOfferCaseParticipantToOwnerNode.update()` to prevent a `CaseParticipant` with zero roles reaching the DataLayer. Documented AC-3: `EmitInviteActorToCaseNode` passing `roles=None` correctly triggers `[CVDRole.VENDOR]` fallback in the adapter. Added 3 new tests. PR: <https://github.com/CERTCC/Vultron/pull/1416>
