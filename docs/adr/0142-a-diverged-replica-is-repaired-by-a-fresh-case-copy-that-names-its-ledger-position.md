---
status: accepted-provisional
date: 2026-10-16
created: 2026-10-16
updated: 2026-10-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Concern #4742; ADR-0080, ADR-0114, ADR-0124;
  specs/sync-ledger-replication.yaml SYNC-03, SYNC-14, SYNC-15;
  specs/participant-case-replica.yaml PCR-02-004; specs/protocol-asks.yaml ASK-07
informed: []
stakeholder_type: [project-contributor]
---

# A Diverged Replica Is Repaired by a Fresh Case Copy That Names Its Ledger Position

## Context and Problem Statement

Under the copy model (ADR-0124) a replica applies every entry by copying what it carries, through one apply function that refuses an entry whose starting state does not match the replica's case file.
When the refused entry already extends the replica's stored chain, the refusal is not a gap: the replica's case file has diverged from the CASE_MANAGER's.
The copy model makes that a defect, not a steady state, but it can still happen: a bug in an apply step, or state written outside the ledger before a domain was converted.

A diverged replica is stuck.
The refused entry is never stored, so every later entry arrives as a forward gap; the gap Reject makes the CASE_MANAGER replay from the replica's tail, which resends the refused entry, which is refused again.
Nothing tells the CASE_MANAGER why.
A fresh `Announce(VulnerabilityCase)` would replace the replica's case, but it replaces on any copy, with nothing to say whether the copy is current: an old copy that arrives late moves a replica backwards.

How does a diverged replica tell the CASE_MANAGER, and how is it repaired?

## Decision Drivers

- The CASE_MANAGER's case is authoritative; a replica that cannot follow it cannot take part in the case.
- Recovery must not loop: the existing reject and replay path already bounds its own rate (SYNC-15-003).
- A repair must not move a replica backwards: the transport is unordered and the outbox retries, so an old copy can arrive late.
- The ledger records case history, not the health of its own replication (CLP-04-007).
- The divergence is a bug somewhere, so it must stay visible after it is repaired.

## Considered Options

- Report only: a fault the CASE_MANAGER records and a person acts on
- Report, and the CASE_MANAGER repairs by sending a fresh case copy
- Reuse the "replay from genesis" Reject

## Decision Outcome

Chosen option: "Report, and the CASE_MANAGER repairs by sending a fresh case copy", because it is the only option that both tells the CASE_MANAGER what happened and un-sticks the replica, and it composes from mechanisms that already exist: the full-case announcement, the reject and replay path, and the forward-only replay of a seeded replica (ADR-0114).

### The replica reports

A replica that refuses an entry extending its chain sends the case's CASE_MANAGER a `Create(ProcessingFault)` whose failure class says the entry was refused because the case diverged.
That is the fault's meaning under MSM-05-001: the entry was received but could not be processed.
The replica keeps holding the entry, exactly as before.

### The fault is replication signalling, never a ledger entry

The fault reports on replication, as the gap `Reject(CaseLedgerEntry)` does, and like it is never committed.
Ledgering it would loop: the stuck replica could not apply the entry that records its own fault, and a failure to apply that entry would itself be a fault to ledger.
It is logged, and the CASE_MANAGER's response to it is per-peer replication state.

### The CASE_MANAGER repairs with a copy that names its position

On that fault from an active participant, the CASE_MANAGER sends the replica `Announce(VulnerabilityCase)` of its current case, rate-bounded per peer.

The case's wire form carries a **ledger tail**: the index and hash of the last entry the copy reflects.
The ledger is part of how a case is tracked, so the case says where in it the copy stands.
The tail is filled in from the ledger each time the case is read or sent and is never stored as its own value, so it cannot disagree with the ledger it points into, and filling it in is not a change to the case file that needs its own entry.

### The replica decides by the tail

Every full-case announcement to a replica that already holds the case is an authoritative update (PCR-02-004), judged by its tail:

- If the replica's chain is already past the tail, the copy is stale and is skipped.
- If the replica holds a different entry at the tail's index, the two chains conflict; the copy is refused and the conflict reported.
- Otherwise the replica replaces its case file with the copy, and if its chain falls short of the tail it asks for the missing entries with the usual Reject.
  Each entry at or before the tail, whether replayed or the held refused entry drained after the replacement, is already reflected in the copy and is stored as a no-op, so the chain catches up and the refused entry stops being refused.

A copy taken at a position is the case as applying the ledger to that position leaves it (ADR-0124), so replacing and then backfilling leaves the replica exactly where seed-plus-replay would.

### Consequences

- Good, because a diverged replica recovers without a person, and the CASE_MANAGER learns that it diverged.
- Good, because no new message type is needed: a fault class, one field on the case's wire form, and the existing announcement and replay.
- Good, because the tail makes every full-case announcement safe to apply, not only a repair, so the replica rule needs no repair-only window, and a late old copy can no longer move a replica backwards.
- Good, because a repeated divergence right after a repair shows that the CASE_MANAGER's case disagrees with its own ledger, which can be logged as the defect it is.
- Bad, because a repair hides the bug that caused the divergence unless the fault is watched; the fault and the repair are logged for that reason.
- Bad, because every apply step must treat an entry a newer copy is already past as a no-op, for every domain, not only the embargo register.
- Neutral, because the fault is not ledgered, so other participants never learn that one replica diverged; nothing they do depends on it.

## Validation

- A test diverges one replica's case file, delivers the next copied entry, and asserts the replica converges to the CASE_MANAGER's case file and chain tail.
- A test asserts a stale full-case announcement leaves a replica unchanged.
- A test asserts no divergence fault reaches a case ledger.

## Pros and Cons of the Options

### Report only: a fault the CASE_MANAGER records and a person acts on

- Good, because a divergence is never papered over.
- Bad, because the replica stays stuck, and keeps looping, until someone intervenes.
- Bad, because recording it in the ledger, as ASK-07-008 asked of case-attributable faults, loops for this fault.

### Report, and the CASE_MANAGER repairs by sending a fresh case copy

- Good, because it recovers and reports in one message.
- Good, because the full-case announcement and the backfill already exist.
- Bad, because the case's wire form gains a field, and a replica must now judge every full-case announcement against its chain.

### Reuse the "replay from genesis" Reject

- Good, because the CASE_MANAGER already answers it by sending the case and replaying.
- Bad, because a Reject means "received and understood but declined" (MSM-05-001), and the CASE_MANAGER would still not learn why.
- Bad, because the copy it sends carries no position, so a replica cannot tell it from a stale one without the tail rule anyway.

## More Information

Decided in the planning of Concern #4742 on 2026-10-16.
Implementation: the tail and the replica's rule in #4797, the fault in #4798, the CASE_MANAGER's repair in #4799.
Whether ASK-07-008 should keep ledgering the other fault classes is Concern #4800.

Generated spec requirements: `sync-ledger-replication.yaml` SYNC-16-001 through SYNC-16-008.
