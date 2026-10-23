---
source: ISSUE-595
timestamp: '2026-05-21T21:04:35.246076+00:00'
title: Cascade CaseLogEntry + Announce to all Case Actor received handlers
type: implementation
---

## Issue #595 — Implement automatic CaseLogEntry + Announce(CaseLogEntry) broadcast cascade in all Case Actor received handlers

Wired the CaseLogEntry commit-and-fan-out cascade into all Case Actor
received-side handlers that were missing it. Previously, only the
SYNC-2/SYNC-3 handlers produced log entries; note, status, and embargo
handlers silently accepted messages without broadcasting state changes
to participants.

### Handlers updated

- **AC-1 — Note**: `AddNoteToCaseReceivedUseCase` — commits a
  `CaseLogEntry` (event_type `add_note_to_case`) after the note is
  accepted and saved.
- **AC-2 — Status**: `AddParticipantStatusToParticipantReceivedUseCase`
  — commits on BT SUCCESS only; returns early on BT FAILURE (rejected
  update must not be broadcast to peers as an accepted state change).
- **AC-3 — Embargo** (all 5 handlers via shared
  `_commit_embargo_log_cascade()` helper):
  - `AddEmbargoEventToCaseReceivedUseCase`
  - `RemoveEmbargoEventFromCaseReceivedUseCase` — cascades on both
    SUCCESS and FAILURE (FAILURE = embargo already cleared = idempotent
    non-error)
  - `InviteToEmbargoOnCaseReceivedUseCase`
  - `AcceptInviteToEmbargoOnCaseReceivedUseCase`
  - `RejectInviteToEmbargoOnCaseReceivedUseCase`
- **AC-4 — Demo endpoint**: `demo_sync_log_entry` docstring updated
  with `TEST SCAFFOLD ONLY` note.

### Bugfixes discovered during testing

Two pre-existing silent bugs in the embargo handlers were uncovered:

- **`InviteToEmbargoOnCaseReceivedUseCase`**: used
  `activity.context_` (JSON-LD `@context` = AS2 namespace URI) instead
  of `request.context_id` (AS2 `context` property = case URI). The
  participant consent-state update and cascade were both silently
  skipped for every inbound invite.
- **`RejectInviteToEmbargoOnCaseReceivedUseCase`**: used
  `invite.context_` instead of `invite.context` when reading back the
  stored proposal from the DataLayer, causing `case_id` to resolve to
  the AS2 namespace and the participant update/cascade to be skipped.

### Adapter wiring

`_SYNC_PORT_SEMANTICS` in `inbox_handler.py` expanded from 2 to 9
entries: `ADD_EMBARGO_EVENT_TO_CASE`, `ADD_NOTE_TO_CASE`,
`ADD_PARTICIPANT_STATUS_TO_PARTICIPANT`,
`ACCEPT_INVITE_TO_EMBARGO_ON_CASE`, `INVITE_TO_EMBARGO_ON_CASE`,
`REJECT_INVITE_TO_EMBARGO_ON_CASE`, `REMOVE_EMBARGO_EVENT_FROM_CASE`.

### Tests

10 new cascade tests across 3 test files:

- `TestNoteUseCases` — log entry committed; no outbox messages without
  sync_port
- `TestParticipantStatusLogEntryCascade` — cascade on BT success; no
  outbox messages without sync_port
- `TestEmbargoLogEntryCascade` — one test per handler; BT-failure
  cascade for `RemoveEmbargo`

Code review flagged an apparent inconsistency between `RemoveEmbargo`
(cascades on failure) and `AddParticipantStatus` (success-only). The
difference is intentional and was documented in a follow-up commit.

All 2477 tests pass; Black, flake8, mypy, and pyright clean.

**PR**: [#620](https://github.com/CERTCC/Vultron/pull/620)
