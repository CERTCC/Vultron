---
source: CONCERN-4974
timestamp: '2026-10-22T14:12:26.383507+00:00'
title: A replica's hash refusal reaches no one, so the CASE_MANAGER keeps replaying
  the broken entry
type: learning
---

## Summary

Since #3744 (PR #4971), a replica refuses a received `CaseLedgerEntry` whose content does not reproduce its `entryHash` (SYNC-03-006): it logs at ERROR and reports `REFUSED`, and sends nothing.
The CASE_MANAGER never learns about the refusal.

## Why it matters

The replica's tail does not move, so the next entry it receives fails the predecessor check and triggers a `Reject(CaseLedgerEntry)`.
The CASE_MANAGER then replays from that tail, which resends the same broken entry, and the replica refuses it again.
The loop is bounded only by the replay cooldown (SYNC-15-003), and the replica never catches up.
If the entry is broken in the CASE_MANAGER's own store, which is how #3744 arose, only the replica's ERROR log shows anything is wrong.

SYNC-16-001 already covers a related case: the replica tells the CASE_MANAGER about an entry it cannot apply, with a `Create(ProcessingFault)`.
The companion draft (section 5.5) says an entry invalid in itself "takes its own fault instead", but no failure class exists for a hash mismatch.

## Open question

Should a hash refusal send `Create(ProcessingFault)` with its own failure class (for example `LedgerEntryRefused/HashMismatch`) to the CASE_MANAGER?
And what should the CASE_MANAGER do when it gets one: log the integrity fault at ERROR, stop replaying that entry, or something else?

Where: vultron/core/behaviors/sync/nodes/receive.py (CheckEntryHashIntactNode), specs/sync-ledger-replication.yaml (SYNC-03-006, SYNC-16)

Governing specs: SYNC-03-006, SYNC-16-001, SYNC-16-002, SYNC-15-003

Where: vultron/core/behaviors/sync/nodes/receive.py

**Resolved**: 2026-10-22 — implementation tracked in #5093, #5094; send-side check filed as Idea #5095.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5096>.
Spec: `specs/sync-ledger-replication.yaml` (SYNC-03-007, SYNC-03-008).
Notes: `notes/sync-ledger-replication.md`.

Decision: the replica reports a hash refusal with `Create(ProcessingFault)` `LedgerEntryRefused/HashMismatch`; the CASE_MANAGER logs it at ERROR and re-checks its own copy with the shared `ledger_entry_hash_intact()`, and does nothing else. Replay and re-seed cannot repair a hash mismatch, and the doubling replay cooldown already bounds the loop.
