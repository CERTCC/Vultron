---
status: proposed
date: 2026-10-22
created: 2026-10-22
updated: 2026-10-22
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0114, ADR-0124, ADR-0135, ADR-0142, ADR-0152;
  specs/sync-ledger-replication.yaml SYNC-00-003, SYNC-00-007, SYNC-00-008,
  SYNC-04-001, SYNC-15-003; specs/case-management.yaml CM-10-004,
  CM-10-007; issues #2961, #5089, #1156
informed: []
stakeholder_type: [project-contributor]
---

# A Participant States Its Ledger Position, and the Case Manager Answers a Lag

## Context and Problem Statement

The CASE_MANAGER pushes each committed `CaseLedgerEntry` to every active participant as `Announce(CaseLedgerEntry)`.
A participant that receives an entry with a gap holds it and sends `Reject(CaseLedgerEntry)` naming its tail, and the CASE_MANAGER replays the missing suffix.
That loop repairs a lost entry as soon as the case commits another one, because the next entry arrives with a gap.

It does not repair the last entry before a quiet period.
If that `Announce` is lost, or dead-lettered after the outbox exhausts its attempts on a participant that is offline, the participant receives nothing further, sends no `Reject`, and keeps a stale case until something else happens in the case.
When the lost entry ends an embargo, the participant goes on believing the embargo is active.
A `Reject` that arrives inside the replay cooldown is dropped the same way.

The CASE_MANAGER cannot detect this lag itself.
Its per-peer replication state (`VultronReplicationState`) records a position only when a `Reject` arrives, so it has no record of how far a participant that never rejects has got.
A comparison of that record with the ledger tail reads nearly every participant as behind.

How does the CASE_MANAGER learn that a participant is behind when nothing new is being committed?

## Decision Drivers

- SYNC-00-007 and SYNC-00-008 require the reconciliation mechanism to detect a lagging replica and retry until it converges.
- An activity must say what it means. A message that claims "I refused this entry" when nothing was refused misleads other implementations.
- Case content goes only to active participants (CM-10-004, ADR-0114); a removed, unconsented or closed participant's replica stops on purpose and must not be read as lag.
- Vultron's core has no scheduler; time-driven decisions run when an activity arrives (CLP-10-025).
- A pull from a published ledger collection (#5089) waits on actor authentication (#1156), which is not near.

## Considered Options

- The CASE_MANAGER sweeps every peer's replication state, on each commit or on a timer, and replays to those behind the tail.
- The participant reports its position with `Reject(CaseLedgerEntry)` naming its own tail entry.
- The participant states its position, when it chooses, in a `Read(CaseLedgerEntry)` naming the last entry it applied.
- Wait for the published ledger collection (#5089) and let participants pull.

## Decision Outcome

Chosen option: "The participant states its position, when it chooses, in a `Read(CaseLedgerEntry)` naming the last entry it applied", because it gives the CASE_MANAGER a truthful acknowledgement it does not have today, uses an ActivityStreams activity in its own meaning, and needs no scheduler on the CASE_MANAGER.

- **A participant that wants to check sends `Read(CaseLedgerEntry)`.** A participant that wants to check sends `Read(CaseLedgerEntry)` whose object is the last entry it applied.
  ActivityStreams defines `Read` as "the actor has read the object", so the activity states a fact and asks for nothing.
  When to send it is the participant's own policy.
- **The CASE_MANAGER answers the `Read`.** It records the stated position as that peer's acknowledged position.
  When the position is behind the tail, it replays the entries after it, through the same recipient check, rate limit and outbox de-duplication as a `Reject`-triggered replay.
  It answers a sender that is not an active participant with nothing.
- **A stated position is not a case event.** It changes nothing in the case file, so it is never ledgered (ADR-0152).
- **A position the CASE_MANAGER's ledger does not contain** is logged and answered with nothing; repairing a diverged replica stays with ADR-0142.
- **A position stated on every case activity is decided separately** (#5080, planned in #5109 and #5110).
  That passive statement records and replays through the same answer, so this decision covers only the active `Read`.

### Consequences

- Good, because the acknowledged position in per-peer replication state now means what its name says, for any participant that reads.
- Good, because a participant that missed the last entry of a quiet case recovers by its own `Read`, without waiting for a new commit.
- Good, because the CASE_MANAGER runs no timer and keeps no sweep, so a paused participant cannot be misread as lagging.
- Good, because the published ledger collection, when it lands, adds a pull without replacing this; push and acknowledgement stay the main path.
- Bad, because a participant that never reads stays stale until the next commit; the CASE_MANAGER cannot repair a peer that tells it nothing.
- Bad, because it adds one received message type.
- Bad, because a `Read` can predate entries already on their way to the sender, so the CASE_MANAGER sees a lag that delivery is about to close and may replay entries that have already left the outbox, where its de-duplication no longer catches them; only the replay rate bound limits these replays.

## Validation

Tests drop the last `Announce(CaseLedgerEntry)` to a participant, send no further entry, and assert that the participant's `Read` brings its tail to the CASE_MANAGER's.
A removed participant whose stated position lags is sent nothing.

## Pros and Cons of the Options

### The participant states its position

- Good, because the CASE_MANAGER gets an acknowledgement from the only party that knows how far it has got.
- Good, because `Read` states a fact in ActivityStreams' own meaning and claims no refusal.
- Good, because it needs no scheduler and no sweep on the CASE_MANAGER.
- Bad, because it depends on the participant reading; a participant that never reads is not repaired until the next commit.
- Bad, because a position can be out of date by the time it arrives, which can cause redundant replays bounded only by the rate limit.

### The CASE_MANAGER sweeps every peer's replication state

- Good, because it needs no cooperation from the participant.
- Bad, because the CASE_MANAGER has no acknowledgement to compare with the tail; the recorded position is written only by a `Reject`, so the sweep resends history to every peer.
- Bad, because a timer needs a scheduler that core does not have, and a sweep on commit adds nothing the next entry's gap `Reject` does not already do.
- Bad, because it must filter out every paused participant, whose position stops at its pause on purpose.

### The participant reports its position with `Reject(CaseLedgerEntry)`

- Good, because the message and its replay path exist.
- Bad, because it says the participant refused an entry it did not refuse, which other implementations may act on.

### Wait for the published ledger collection

- Good, because an HTTP GET of a collection is how ActivityPub pulls.
- Bad, because it waits on actor authentication; without it the collection would expose embargoed content.
- Neutral, because a pull and a stated position do not compete; the collection can be added later.

## More Information

- `Follow` of a ledger collection was set aside: it is a standing subscription, not a one-off check, and it needs the collection to exist.
- `View` fits less well than `Read`; a ledger is read.

Generated spec requirements: `sync-ledger-replication.yaml` SYNC-17-001 through SYNC-17-007.
