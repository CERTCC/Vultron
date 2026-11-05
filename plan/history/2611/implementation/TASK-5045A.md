---
source: TASK-5045A
timestamp: '2026-11-05T17:50:58.276995+00:00'
title: 'One staged record holds a received message (part 1 of #5045)'
type: implementation
---

PR #5925 is part of issue #5045 (slice 1 of 3); #5045 stays open for slices 2 and 3.

Retired `DeferredInboxActivity` and `VultronPendingCaseInbox.activity_ids` into the
activity's one `ReceivedActivityRecord`, so a received message is one staged record
under one receiver-derived key (ADR-0154). The record carries two independent facts:
`stage` (`HELD`/`ARCHIVED`) and `replay_owed` (with `awaiting_case_id`,
`received_at`, `replay_rows_json`).

Two fields rather than one enum, because both their combinations are reachable. A
buffered `Announce(CaseLedgerEntry)` arriving ahead of its predecessor is `ARCHIVED`
**and** owes a replay: intake archives it, then the SYNC-14 handler holds it for the
gap. Confirmed by driving a real delivery through the production dispatcher and
inbox pipeline, not by inspection. `hold_ledger_announce` can only ever run on an
archived record, because `_received_body` refuses anything else — so that pairing is
not merely reachable, it is the only outcome of the SYNC-14 hold. Collapsing the two
onto one enum would have made release or discard delete an archive CLP-10-018
requires to stand.

`replay_owed`, not the record type or stage, decides whether a routed copy carries
received evidence (`_HeldBody.kind`, renamed `deferred` -> `awaiting_replay`). Keying
on the stage would have routed a buffered `Announce`'s redelivery with evidence.

All transitions go through the new `vultron/core/services/received_holding.py`, which
`test/architecture/test_received_holding_writers.py` pins as the only writer of the
holding fields (intake excepted, which names the stage it archives at).

Three defects fixed, each with a mutation-proven regression test:

- `inbox_pipeline.py` held a deferred body without naming its case, so
  `records_awaiting_case` was empty, nothing would replay it and expiry would never
  discard it — a message lost silently.
- `received_holding.hold_for_replay` left a newly-named case unrecorded on a body
  already held, which made the above silent rather than loud.
- `_queue_pending_case_activity` restarted the CBT-03-001 expiry window on a
  redelivery (found in review). Reading "is anything else waiting" *after* the hold
  cannot tell a repeat from a first arrival, because the hold is what makes the
  activity one of the waiting. A sender redelivering inside the window would have
  held the pre-bootstrap queue open indefinitely, against CBT-03-003's bound. The
  reading is now taken before the hold (`_case_window_is_open`).

Specs amended: IO-03-009, DL-06-006, IE-10-001 (IE-06-012's verification prose
followed the rename). CLP-10-010/017/018/019, HP-01-012 and the intake-first
ratchets are untouched and belong to the slices that move the doors.
`docs/topics/reference_architecture.md` still describes intake-first deliberately:
this slice does not change the order.
