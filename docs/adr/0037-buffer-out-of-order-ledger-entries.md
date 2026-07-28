---
status: accepted
date: 2026-07-21
deciders: Allen D. Householder
consulted: []
informed: []
---

# Buffer Out-of-Order `Announce(CaseLedgerEntry)` Instead of Dropping

## Context and Problem Statement

Participant replicas receive the canonical recorded log from the CaseActor as a
stream of `Announce(CaseLedgerEntry)` activities. That stream travels over a
transport with **no ordering guarantee**, and Vultron may not be the only
protocol implementation on the wire, so a replica can receive an entry before
its hash-chain predecessor arrives.

The original receive path (`CheckHashOrRejectOnMismatchNode`) treated any entry
whose `prev_log_hash` did not match the local tail as a divergence: it **dropped**
the entry and sent a `Reject(CaseLedgerEntry)` so the CaseActor would replay the
missing prefix. At case closure this stalled a late-joining replica (Vendor2 in
the FVV/FVCV demos) indefinitely and `wait_for_contiguous_ledger_coverage` timed
out (issue #1556). How should a replica handle an entry that is valid but
arrives before its predecessor?

## Decision Drivers

- Convergence must not depend on `Announce` delivery order (SYNC-10-004 requires
  a contiguous prefix; the transport does not provide ordering).
- The fix must interoperate with unknown implementations — we cannot assume the
  sender retries, or that any recovery message is delivered in order either.
- Must preserve the effects-before-persist invariant (SYNC-12-001) and the
  DataLayer-presence-means-committed invariant (SYNC-13-001).
- Bounded memory under a broken or hostile peer that streams far-future entries.

## Considered Options

- **A. Repair the `Reject → replay` loop only** — keep dropping out-of-order
  entries; make the CaseActor reliably process the participant's Reject and
  replay the missing prefix promptly.
- **B. Receiver-side buffering** — hold out-of-order entries locally and apply
  them in hash-chain order once their predecessor arrives.
- **C. Both** — buffering plus a hardened replay loop.

## Decision Outcome

Chosen option: **B, receiver-side buffering** (which subsumes most of C).

Option A alone is insufficient: the replay path re-announces each missing entry
as a *separate* `Announce`, which travels the same unordered transport and can
reorder again — hitting the very same drop. Repairing replay narrows the race
but cannot close it under adversarial reordering. Buffering, by contrast, makes
convergence **order-independent**: any valid entry is retained until the entry
that closes its gap arrives, then drained in order.

Buffering also makes the existing `Reject → replay` recovery order-robust *for
free*, because replayed entries flow through the same (now buffering) receive
path. We therefore did **not** redesign the replay loop; we keep sending the
`Reject` at buffer time purely as the backstop for entries that are genuinely
*lost* (never delivered) rather than merely reordered. A companion correctness
fix makes `SyncActivityAdapter.send_reject_log_entry` enqueue against the
explicit receiving `actor_id` (like the announce path) instead of the DataLayer's
own scope, so the Reject is delivered correctly even from a shared or
differently-scoped DataLayer.

### Consequences

- Good: a late-joining replica converges to a contiguous prefix within a few
  seconds of the tail arriving, regardless of `Announce` order (SYNC-10-004).
- Good: no new dependence on sender retry behavior — robust against other
  implementations and lossy/reordering transports.
- Good: the buffer is a non-ledger holding area (SYNC-13-003), so the
  "DataLayer presence ⇒ committed + effects applied" invariant is preserved.
- Neutral: buffered state is in-memory and lost on restart; the SYNC-10 catch-up
  gate re-syncs any gap after restart, so no durability is required.
- Bad: adds a per-actor in-memory structure and a drain step on the receive
  path; bounded by a size cap with farthest-ahead eviction (recoverable via the
  Reject backstop).

## Validation

- `LedgerGapBuffer` unit tests (`test/core/models/test_ledger_gap_buffer.py`):
  O(1) drain-next, multi-hop cascade, per-case isolation, duplicate/fork
  handling, size-bound eviction, per-actor registry.
- Out-of-order regression tests through `AnnounceLedgerEntryReceivedUseCase`
  (`test/core/use_cases/received/test_sync.py`): fully-reversed delivery,
  single-gap click-into-place, multi-gap cascade, shuffled-replay convergence —
  each asserting no entry is permanently dropped.

## Pros and Cons of the Options

### A. Repair the `Reject → replay` loop only

- Good, because it reuses the existing recovery mechanism with no new state.
- Bad, because replay re-announces entries individually over the same unordered
  transport, so the reorder-and-drop race reappears — it cannot guarantee
  convergence under adversarial ordering.
- Bad, because correctness depends on the CaseActor reliably processing every
  Reject during a rapid closure fan-out, which is exactly what failed.

### B. Receiver-side buffering

- Good, because convergence becomes independent of delivery order.
- Good, because it needs no cooperation from the sender or transport.
- Good, because it makes the replay path order-robust as a side effect.
- Neutral, because it introduces bounded, ephemeral per-actor state.
- Bad, because a misbehaving peer could stream far-future entries (mitigated by
  the size cap + eviction).

### C. Both

- Good, because it is the most defensive.
- Bad, because once B is in place a separate replay redesign is redundant for
  this failure mode — extra surface area for no additional guarantee.

## More Information

Design rationale and the hash-chain "teeth of the zipper" argument (why
indefinite buffering is safe) are recorded in
`notes/sync-ledger-replication.md` § "Out-of-Order Delivery and the Ledger Gap
Buffer". Implemented in PR #1564 (closes #1556).

Generated spec requirements: `sync-ledger-replication.yaml` SYNC-14-001 through
SYNC-14-006 and the clarification to SYNC-08-005; `outbox.yaml` OX-02-003.
