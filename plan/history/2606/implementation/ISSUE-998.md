---
source: ISSUE-998
timestamp: '2026-06-16T16:25:24.074151+00:00'
title: Fix EXPECTED_EVENT_TYPES names and add canonical ledger writes
type: implementation
---

## Issue #998 — Fix EXPECTED_EVENT_TYPES names and add canonical ledger writes

Corrected the CI case-ledger invariant test (Inv-5) that had been xfailed
since PR #936. Two categories of fixes:

**Name corrections in `test/ci/test_case_ledger_invariants.py`:**
Legacy event type names that predated the `MessageSemantics` StrEnum were
replaced with the correct values: `accept_report` → removed (not in demo
flow), `propose_embargo` → `invite_to_embargo_on_case`, `accept_embargo` →
`accept_invite_to_embargo_on_case`, `notify_fix_ready` /
`notify_fix_deployed` / `notify_published` → consolidated into
`add_participant_status`, `add_note` → `add_note_to_case`. Added
`submit_report`, `engage_case`, and `remove_embargo_event_from_case` to make
existing ledger coverage explicit. Removed the `xfail` decorator.

**New canonical ledger writes:**

- `validate_report`: `SvcValidateReportUseCase` now accepts `sync_port` and
  commits a `validate_report` ledger entry (via the CaseActor) after the
  validation BT succeeds. `TriggerService.validate_report()` passes
  `self._sync_port` through.
- `close_case`: `AddParticipantStatusToParticipantReceivedUseCase` calls a
  new `_commit_close_case_if_all_closed()` helper after each
  `add_participant_status` commit. When all CVD participants (excluding
  CASE_MANAGER) have `RM.CLOSED`, a `close_case` entry is appended to the
  canonical case ledger (DEMOMA-07-003 step 5).

PR: <https://github.com/CERTCC/Vultron/pull/1003>
