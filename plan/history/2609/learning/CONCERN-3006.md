---
source: CONCERN-3006
timestamp: '2026-09-15T13:43:48.487614+00:00'
title: Acknowledgement model discrepancy — messages.md vs. ledger hash-chain NAK
type: learning
---

## Concern

The formal protocol specifies a positive acknowledgement message per state machine
(`RK`, `EK`, `CK`, `GK`). The implementation acknowledges ledger-replicated state
on a different model entirely, and MSM-05-002 now records it as normative. This
issue asks whether `messages.md` should follow.

**What the implementation does.** A participant receiving
`Announce(CaseLedgerEntry)` whose `prev_log_hash` matches its local tail sends
**nothing** — the match *is* the acknowledgement. It speaks up only on a mismatch,
emitting `Reject(CaseLedgerEntry)`, whereupon the CaseActor replays every entry
after the last accepted hash (`RejectLedgerEntryReceivedUseCase`,
`vultron/core/use_cases/received/sync.py`).

That is negative acknowledgement with gap-fill replay — cumulative and implicit,
structurally closer to TCP cumulative ACK/SACK than to per-message positive acks.
It is arguably better: it is O(1) in quiet operation instead of O(n), and hash
continuity proves receipt of the *whole prefix* rather than one message.

`RK` survives as a real wire activity (`Read(Offer(VulnerabilityReport))`,
MSM-01-008) because report submission is not ledger-replicated. So the protocol
now has **two** acknowledgement models, and only one of them is described in
`messages.md`.

**Resolution**: 2026-09-15 — Planned and implemented in docs PR #3240.

- `messages.md` keeps EK/CK/GK in the formal set; a new `!!! note` callout explains they have no per-message wire counterpart (hash-chain continuity is the mechanism).
- New reference page `docs/reference/messages/faults_and_acknowledgements.md` created covering the full fault trichotomy and ack evolution.
- `acknowledge.md` updated with ledger-replicated ack section.
- MSM-05-005 (all protocol-significant activities reach the ledger) and MSM-05-006 (no heartbeat required — liveness via Announce is MAY) added to spec.
- All four open questions from the concern resolved.
- Implementation tracked in #3246.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3240>.
Spec: `specs/message-semantics-mapping.yaml`.
