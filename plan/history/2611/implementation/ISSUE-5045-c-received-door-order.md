---
source: ISSUE-5045-c-received-door-order
timestamp: '2026-11-06T05:21:24.400482+00:00'
title: 'Received trees: doors before intake; seen-before door answers resends (#5045,
  slice 3)'
type: implementation
---

Slice 3 of 3 of #5045 (PR #5998). Every received tree now runs its door guards in
ADR-0154's order (addressee, seen before, path, post-close, closed sender, case
resolution, sender guard) before intake writes anything. A new seen-before door
answers a resend from the message's one ReceivedActivityRecord: a receipt stub is
REFUSED again with its reason, an archive or a record owed a replay is SKIPPED, and a
HELD record owing nothing runs again. Intake keeps no in-memory lists; the outcome
stage archives an applied message and stubs a refused one. An ARCHIVED record that
owes a replay now fails validation, so a store holding one must be re-seeded.

The pr-ship fix pass restored CLP-10-044 for the re-run of a record a run left in
holding: the refusal effects are skipped again, as main skipped them on intake's
found_ids. Without the skip, a lost receipt stub let a resend commit and announce a
second RSH-06-004 note, whose id is minted. The re-run flag the door sets is a
cross-stage in-memory read carried over from main; #5047 owns replacing it.
