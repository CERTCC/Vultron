---
title: "Buffer out-of-order ledger entries keyed on prev_log_hash for O(1) drain"
type: learning
timestamp: "2026-07-21"
source: ISSUE-1556
---

`Announce(CaseLedgerEntry)` has no delivery-ordering guarantee (and Vultron may
not be the only implementation on the wire), so a replica can receive an entry
before its hash-chain predecessor. The old receive path dropped such an entry
and relied on a `Reject → replay` round-trip that is itself order-fragile
(`SendMissingEntriesNode` replays each entry as a separate `Announce`), so under
reordering an entry could be lost indefinitely.

**Fix:** receiver-side `LedgerGapBuffer` (`vultron/core/models/ledger_gap_buffer.py`)
makes convergence order-independent. Key design choices:

- **Key on `prev_log_hash`, not `id_`/`entry_hash`/a list.** The drain question
  is "what buffered entry extends my new tail?" — that entry is exactly
  `buffer[new_tail.entry_hash]` (because `entry.prev_log_hash ==
  predecessor.entry_hash`). O(1) per hop → O(k) cascade. Any other key makes
  find-next O(n) and the cascade O(n²).
- **Hash-chaining makes indefinite buffering safe.** A held entry waits for the
  exact predecessor hash ("teeth of the zipper"), so a fork/rewrite can't
  masquerade as the successor. Expiry is therefore pure memory hygiene
  (size-bound eviction of the farthest-ahead entry), never a correctness knob.
- **Mirror `PendingAssertionStore`**: actor-local, per-case, in-memory,
  module-level per-actor registry, ephemeral. It is the "clearly separate,
  non-ledger holding area" SYNC-13-003 sanctions — DataLayer presence still
  means "committed + effects applied" (SYNC-13-001).
- **Drain by re-running the announce BT** on each buffered successor rather than
  duplicating apply-effects logic — reuses the exact effects-before-persist path
  (SYNC-12-001) for free.

Buffering also makes the `Reject → replay` recovery order-robust automatically,
because replayed entries flow through the same receive path — no separate replay
redesign was needed. Keep sending the `Reject` at buffer time as the backstop
for entries that are genuinely lost (never delivered) rather than reordered.

**Promoted**: 2026-07-22 — captured in `notes/sync-ledger-replication.md (already present)`.
Docs PR: TBD (fill in after PR is opened).
