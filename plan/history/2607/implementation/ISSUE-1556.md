---
source: ISSUE-1556
timestamp: '2026-07-21T16:58:38.160714+00:00'
title: SYNC out-of-order Announce(CaseLedgerEntry) buffering
type: implementation
---

## Symptoms

At case closure a late-joining replica (Vendor2 in the FVV/FVCV demos) received
`Announce(CaseLedgerEntry)` activities out of order and permanently dropped the
ones whose `prev_log_hash` did not match its local tail, stalling with a gapped
ledger. `wait_for_contiguous_ledger_coverage` timed out.

## Root cause

The receive path dropped forward-gap entries and relied on a `Reject → replay`
round-trip that is itself order-fragile (each replayed entry is a separate
`Announce` that can reorder again and hit the same drop). Under an unordered
transport an entry could be lost indefinitely. A secondary defect:
`SyncActivityAdapter.send_reject_log_entry` enqueued via scope-dependent
`outbox_append` instead of explicit-actor `record_outbox_item`.

## Fix

Receiver-side buffering makes convergence order-independent (SYNC-10-004):

- New `LedgerGapBuffer` (actor-local, per-case, in-memory, ephemeral; mirrors
  `PendingAssertionStore`), keyed on `prev_log_hash` for O(1) drain-next and
  O(k) cascades; size-bounded with farthest-ahead eviction.
- On mismatch, buffer genuine forward gaps and still send the Reject as the
  loss backstop; after each commit, drain buffered successors by re-running the
  announce BT (reusing the SYNC-12-001 effects-before-persist path).
- `send_reject_log_entry` now uses `add_activity_to_outbox` (explicit actor).

Replay is order-robust for free since replayed entries flow through the same
receive path. Tests: `LedgerGapBuffer` unit tests + reversed / single-gap /
multi-gap-cascade / shuffled-replay regression tests through
`AnnounceLedgerEntryReceivedUseCase`.

PR: <https://github.com/CERTCC/Vultron/pull/1564>
