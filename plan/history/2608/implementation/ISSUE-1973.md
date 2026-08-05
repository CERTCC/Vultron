---
source: ISSUE-1973
timestamp: '2026-08-05T17:51:42.373539+00:00'
title: 'fix: RejectInviteActorToCase — resolve case_id from inner_target_id'
type: implementation
---

## Issue #1973 — fix: RejectInviteActorToCase — resolve case_id from inner_target_id

Fixed a silent bug where `RejectInviteActorToCaseReceivedUseCase.execute()` was reading `request.target_id` (always `None` for `Reject(Invite(actor, case))`) instead of `request.inner_target_id`. The use case was early-returning without committing the canonical `Reject(Invite)` ledger entry.

Changes:

- Added `case_id` property to `RejectInviteActorToCaseReceivedEvent` returning `self.inner_target_id`
- Fixed `execute()` to use `request.case_id` instead of `request.target_id`
- Added `include_activity=True` to the semantic registry entry so the wire activity is populated (required for `payloadSnapshot.actor` validation)
- Narrowed `activity` field to required on the event class
- Replaced "skips ledger" test with real integration test confirming CaseLedgerEntry is committed

PR: <https://github.com/CERTCC/Vultron/pull/1998>
