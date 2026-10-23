---
source: CONCERN-4742
timestamp: '2026-10-16T15:27:41.321097+00:00'
title: A replica that refuses a copied embargo entry tells the CASE_MANAGER nothing
type: learning
---

## Problem

Under the copy model (ADR-0124, #4713), a replica applies every embargo and consent entry through the one apply function. When an entry's starting state does not match the replica's case, the replica refuses it. `ApplyEmbargoChangeFromLedgerNode` then holds the entry in `LedgerGapBuffer` and reports the announce `DEFERRED`. That is what #4713's AC-4 asks for.

The refused entry already extends the replica's stored chain: its predecessor is stored. So the refusal is not a gap that a replay can fill. It means the replica's case has **diverged** from the CASE_MANAGER's. What follows:

- The entry is never stored, so every later entry from the CASE_MANAGER arrives as a forward gap. The existing hash check buffers each one and sends `Reject(CaseLedgerEntry)` with the replica's tail. The CASE_MANAGER replays from that tail, which resends the refused entry, and the replica refuses it again. The replica is stuck, and the loop repeats on every new entry.
- Nothing tells the CASE_MANAGER that the replica refused an entry *because its case diverged*. The CASE_MANAGER sees only a generic chain-gap Reject.

A `Reject` for the refused entry itself would not help: the replay would resend the same entry. Recovery needs either a fault the CASE_MANAGER can act on (compare `EmitImpossibleStateFaultNode`, RSH-05-021, for participant status) or a re-seed of the replica's case.

This is latent until #4714–#4717 convert the embargo arms. Until then the CASE_MANAGER commits no consent-row or register-step copy entries.

## Decision needed

Which signal or recovery should a diverged replica use?

1. A `Create(ProcessingFault)` with a new failure class (for example `LedgerEntryRefused/Diverged`) sent to the CASE_MANAGER. The fault is detectable, but nothing repairs the replica.
2. A request for a fresh copy of the case: the CASE_MANAGER re-seeds the replica from its case at the current ledger position.
3. Both.

Each option adds protocol behaviour, so it needs a spec entry, and possibly an ADR, before code.

## Where

- `vultron/core/behaviors/sync/nodes/embargo_copy_effect.py` (`ApplyEmbargoChangeFromLedgerNode._refuse`)
- `vultron/core/use_cases/received/sync.py` (`_refused_announce_verdict`, `drain_gap_buffer`)

Found during pr-ship review of PR #4740.

Where: vultron/core/behaviors/sync/nodes/embargo_copy_effect.py

**Resolved**: 2026-10-16 — implementation tracked in #4797, #4798, #4799; Concern #4800 filed for ASK-07-008.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4806>.
Spec: `specs/sync-ledger-replication.yaml` (SYNC-16).
Notes: `notes/sync-ledger-replication.md`.
Decision record: ADR-0142.
