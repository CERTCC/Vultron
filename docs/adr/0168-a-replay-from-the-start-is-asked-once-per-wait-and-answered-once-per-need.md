---
status: accepted-provisional
date: 2026-10-30
created: 2026-10-30
updated: 2026-10-30
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0059, ADR-0112, ADR-0155; issues #5552, #5521, #4882;
  specs/sync-ledger-replication.yaml SYNC-15
informed: []
stakeholder_type: [project-contributor]
---

# A Replay from the Start Is Asked Once per Wait and Answered Once per Need

## Context and Problem Statement

A participant can receive ledger entries for a case before it holds the case.
ADR-0059 made it hold each such entry and drain the held entries as soon as the case arrives.
ADR-0059 also kept one `Reject(CaseLedgerEntry)` with `last_accepted_hash=""` per held entry, as the backstop for a case that never arrives.

Each of those Rejects asks the CASE_MANAGER to send the case and replay the whole ledger from the start.
The CASE_MANAGER's replay bound starts at a 2-second cooldown for this position.
On a loaded host the CASE_MANAGER handles queued Rejects further apart than that, so each one passes the bound and sends one more full replay.
The participant already converged from its held entries, so every one of those replays is a duplicate, and together they delayed an unrelated message by about 20 seconds (#5552).

How should the protocol limit these requests and replays while it keeps the guarantee that a participant that never gets the case still recovers?

## Decision Drivers

- A participant that never receives the case must still recover.
- Neither side may flood the other with messages that carry no new information.
- Other implementations share the wire, so the CASE_MANAGER cannot rely on a participant's restraint.
- The protocol fixes behavior other participants can observe; numbers and records belong to an implementation.
- No new timer mechanism is introduced at the participant.

## Considered Options

- A. The participant asks once per case while it holds entries for it.
- B. The participant holds entries and asks only after a timeout.
- C. The CASE_MANAGER treats a Reject that an earlier replay already answered as answered.
- D. Both: the participant limits its requests, and the CASE_MANAGER declines a request an earlier replay already answered, each bounded by a rate limit that is never a stop.

## Decision Outcome

Chosen option: "D", because each side then stops the flood it can see, and neither limit is a permanent stop, so the recovery guarantee holds.

The invariant is:

- A participant waiting for a case asks for a replay from the start, and does not ask again for the same case until a bounded interval has passed.
- The CASE_MANAGER answers a request a replay it already sent has answered with nothing, until a bounded interval has passed.
- Any actor may rate-limit repeated requests or replays about the same thing, and a limit always lets a later request through.

At the protocol level these are `SHOULD` and `MAY` rules, with the recovery guarantee kept as a `MUST`.
The intervals, the records that hold them and the CASE_MANAGER's existing doubling cooldown are this codebase's choices and live in `project` requirements.
The specs carry the current values.

### Consequences

- Good, because a participant that gets entries before its case sends one request instead of one per entry.
- Good, because a request the CASE_MANAGER handles late, after a replay already covered its entry, sends nothing.
- Good, because the CASE_MANAGER's bound protects it from a participant that does not limit itself.
- Bad, because a participant whose one replay is lost waits up to the participant's interval before its next request can go out.
- Bad, because the participant needs a new stored record per waiting case, and the CASE_MANAGER needs one more field in its per-peer replication state.
- Bad, because the participant asks only when an entry for the missing case arrives, and the replayed entries that reach it inside the interval are withheld, so a participant whose case copy is lost recovers only when a further entry arrives after the interval.
- Bad, because the participant's interval starts when it asks and the CASE_MANAGER's starts at its later replay, so a request for an old entry just after the participant's interval can still be declined, and the participant then waits up to one more interval.

## Validation

- A test sends a participant several entries before the case and finds one genesis Reject, then a second one only after the interval.
- A test has the CASE_MANAGER handle a genesis Reject for an entry its last replay to that peer already sent and finds no replay and no case copy, and finds a replay again after the interval.
- A test delivers a held entry after the interval and finds a fresh Reject that the CASE_MANAGER does not drop as a redelivery.

## Pros and Cons of the Options

### A. The participant asks once per case

- Good, because it is the smallest change.
- Bad, because a participant that asks exactly once is stuck when that one replay is lost.
- Bad, because it does nothing for a participant from another implementation that keeps asking.

### B. The participant asks only after a timeout

- Good, because when the case is merely late, no request is sent at all.
- Bad, because it needs a timer at the participant, which the inbox does not have.
- Bad, because every recovery from a real loss waits for the timeout.

### C. The CASE_MANAGER treats an answered Reject as answered

- Good, because it protects the CASE_MANAGER whatever the participant does.
- Bad, because our own participants still send one request per held entry, and each one costs the CASE_MANAGER a received tree.

### D. Both sides, each rate-limited, never stopped

- Good, because it removes the flood at its source and still bounds it at the receiver.
- Good, because both limits let a later request through, so the recovery guarantee holds.
- Bad, because it changes both the participant and the CASE_MANAGER.

## More Information

This decision refines the loss backstop that ADR-0059 kept.
ADR-0059's hold and drain are unchanged.

Generated spec requirements: `sync-ledger-replication.yaml` SYNC-15-001, SYNC-15-003, SYNC-15-016 through SYNC-15-025.
