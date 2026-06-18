---
source: CONCERN-1043
timestamp: '2026-06-18T18:57:08.722754+00:00'
title: DEMOMA-07-003 raw re-broadcast superseded by Announce(CaseLedgerEntry) fan-out
type: learning
---

## Summary

DEMOMA-07-003 step 3 requires the Case Actor to directly re-broadcast
`Add(ParticipantStatus)` to all other participants after processing.
However, the SYNC layer (`FanOutLogEntryNode` → `Announce(CaseLedgerEntry)`)
already fans the same update out to all participants after the ledger commit
in `_commit_log_cascade_bt`. Both paths run today, so every peer receives
the same status update twice — once as a raw `Add(ParticipantStatus)` and
once wrapped in `Announce(CaseLedgerEntry)`.

## Category

Specification / Protocol correctness

## Severity

Medium — current code functions, but the direct re-broadcast is a pre-SYNC
artefact that:

- causes double-processing of status updates on every peer inbox
- puts non-canonical messages in peer inboxes alongside canonical ledger
  announcements
- is the primary reason `BroadcastStatusToPeersNode` and `peer_broadcast_bt`
  exist

## Key Finding

The `Announce(CaseLedgerEntry)` fan-out (via `FanOutLogEntryNode` in
`_commit_log_cascade_bt`) covers a **superset** of step 3's recipients —
including the original sender, which step 3 explicitly excluded. Removing
step 3 therefore improves coverage, not reduces it.

## Resolution

- Updated DEMOMA-07-003 step 3 wording to specify `Announce(CaseLedgerEntry)`
  fan-out per ADR-0019/SYNC-02-002 as the canonical propagation mechanism.
- Added DEMOMA-07-005 (`MUST_NOT`) prohibiting parallel raw
  `Add(ParticipantStatus)` re-broadcast to peers.
- A related Concern #1047 was filed for the "single-BT-per-execute()"
  spec invariant (generalisation of the actor-switching pattern, related
  to #1036).

**Resolved**: 2026-06-18 — implementation tracked in #1045.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1044>.
Spec: `specs/multi-actor-demo.yaml` DEMOMA-07-003 (updated), DEMOMA-07-005
(new).
