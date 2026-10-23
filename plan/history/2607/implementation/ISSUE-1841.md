---
source: ISSUE-1841
timestamp: '2026-07-30T20:58:02.755073+00:00'
title: 'feat: add StatusUpdateGuard and EmitAddCaseStatusToSelfNode to add_participant_status_tree'
type: implementation
---

## Issue #1841 — feat: add StatusUpdateGuard and EmitAddCaseStatusToSelfNode to add_participant_status_tree

Implemented Seam 1 of the two-seam authorization model (ADR-0046) for received-side CaseStatus canonicalization.

- Added `StatusUpdateGuard` (Selector/Fallback) to `add_participant_status_tree` with `CheckIsCaseOwnerNode` hard bypass + `CaseOwnerApprovesStatusUpdate` call-out (RSH-01-002)
- Added `EmitAddCaseStatusToSelfNode` to emit self-addressed `Add(CaseStatus)` after guard passes (RSH-01-003)
- Removed `PublicDisclosureBranchNode` from `add_participant_status_tree` (RSH-01-004)
- Created `StatusAuthorizationCallOutBundle` + `STATUS_AUTHORIZATION_DETERMINISTIC` singleton
- Moved `CheckIsCaseOwnerNode` to `vfd_role_guards.py` to satisfy BTND-07-004 line limit
- Added `add_case_status_to_case` to `TriggerActivityPort` Protocol and adapter

PR: <https://github.com/CERTCC/Vultron/pull/1850>
