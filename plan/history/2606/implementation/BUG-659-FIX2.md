---
source: BUG-659-FIX2
timestamp: '2026-06-02T16:38:58.835298+00:00'
title: 'Bug #659 follow-up — participant_status append-order fix'
type: implementation
---

## Context

Follow-up to the initial BUG-659.md entry. The NullPool + WAL adapter
hardening (commit aafaa868) was necessary but did not eliminate the
M4 timeout. Diagnostic logging added in commit 7e3fc52b localised the
real root cause to the wire-layer `CaseParticipant.participant_status`
property.

## Symptoms

`vultron-demo two-actor` flaked in CI: M4
(`wait_for_participant_vfd_state`) timed out waiting for the vendor's
vfd_state to reach `VFd` on the finder replica, even though
adapter-side diagnostic logs confirmed the `VFd` ParticipantStatus
was correctly persisted and read back from SQLite on every poll.

## Root cause

`CaseParticipant.participant_status` selected the "current" status by
`max(participant_statuses, key=(updated or published, index))`. The
`init_participant_status_if_empty` model validator constructs the
initial vfd locally with `published=now_utc()` *at construction time*.
When the M3 `Add(VFd)` activity arrived and the BT appended a new
`ParticipantStatus`, that status carried sender-authored timestamps
that could be *earlier* than the finder's local default on the initial
entry (any clock skew or processing gap is enough). The tiebreaker
then selected index-0 initial vfd despite a freshly appended VFd at
index 1.

## Fix

Return `self.participant_statuses[-1]` from the property. Append order
IS this replica's authoritative chronology; it is robust to sender
clock skew and matches what `VultronParticipant` already does in the
core layer.

## Validation

- Local repro via `jsonable_encoder` round-trip demonstrated the bug
  deterministically and confirmed the fix.
- New unit tests in `test/wire/as2/vocab/test_case_participant.py`
  (`TestParticipantStatusProperty`): 3 tests, first one fails on old
  property, all pass with the fix.
- Full pytest suite: 2725 passed, 12 skipped, 3 xfailed.
- Kept diagnostic DEBUG logs in `datalayer_sqlite.py` and
  `wait_for_participant_vfd_state` — cheap insurance for next time.

## Related

- #663 (`BroadcastStatusToPeersNode` self-loop) still open and out of
  scope here.
