---
status: proposed
date: 2026-11-18
created: 2026-11-18
updated: 2026-11-18
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Idea #6615, Issue #6456, PR #6611, Issue #6330; ADR-0033,
  ADR-0212, ADR-0124, ADR-0198; specs/case-management.yaml CM-18, CM-23-044;
  specs/message-semantics-mapping.yaml MSM-07; specs/status-dimension-objects.yaml
  SDO-03; specs/received-status-handling.yaml RSH-09;
  specs/case-ledger-processing.yaml CLP-07, CLP-15-011
informed: []
stakeholder_type: [project-contributor]
---

# A Replica Changes State Only From the Case Manager's Entries, and Consent Is Part of a Participant's Status

## Context and Problem Statement

A participant's **Embargo Consent** is kept as a separate row on its participant record: one `EmbargoConsent` row for each embargo in the case's **Embargo Register** (ADR-0212).
A row carries no time, so the ledger cannot show when a participant came to agree, decline or time out, except by the entry that caused the change.
For the same reason the rule that every received whole object carries `published` needs an exemption for consent rows (CLP-15-011, PR #6611).

A participant's other state is kept differently.
When the CASE_MANAGER receives a participant's validate, engage or defer, it writes a new **Participant Status** for that participant.
The status is dated to the act and is ledgered as the CASE_MANAGER's own `Add(ParticipantStatus)` entry.
Replicas copy that entry and decide nothing.
"I accepted this embargo" is a statement about the participant's state, as "I validated this case" is, but it is recorded in a different place and in a different way.

The ledger also mixes two kinds of entry.
For RM verdicts, case closure and ownership transfer, the participant's entry is only a record of what it said, and the CASE_MANAGER's next entry carries the change.
For an embargo answer, the participant's own `Accept` or `Reject` entry is the change: each replica runs the consent step itself when it applies that entry (ADR-0124).

The question: **where is a participant's consent recorded, and which entries is a replica allowed to change its state from?**

## Decision Drivers

- One fact is recorded once: two records of the same fact can disagree (ADR-0212).
- Every change of a participant's state is dated, so a case can be traced event by event.
- A replica decides nothing: it copies what the CASE_MANAGER recorded (ADR-0124, CM-23-044).
- The ledger keeps a participant's own words as it sent them, so a signed message stays verifiable.
- The checks on an embargo answer (is the embargo still available, may this participant withdraw) stay in one place.
- A stored status is always whole, so a reader of the latest status reads the participant's whole state.

## Considered Options

- Keep consent rows, and stamp each row with the time of the act that changed it.
- Move consent into the participant's status, and let replicas keep applying a participant's answer from its own entry.
- Move consent into the participant's status, and let a replica change state only from the CASE_MANAGER's entries.

## Decision Outcome

Chosen option: "Move consent into the participant's status, and let a replica change state only from the CASE_MANAGER's entries", because it is the only option in which every change of a participant's state is one dated record, written by one author, and copied by every replica.

### A replica changes state only from the CASE_MANAGER's entries

A replica changes its copy of the case only when it applies an entry that the CASE_MANAGER wrote.
Every other entry is a record of a message: the replica keeps it, and changes nothing because of it.
When an act changes the case, the act's entry comes first, and the CASE_MANAGER's entries that carry each change follow it.

The ledger already works this way for RM verdicts, engagement decisions, case closure and ownership transfer.
This decision states the rule for the whole ledger.
Consent and a participant's own status claims adopt it with this decision.
The Case Owner's decisions, case Invite answers, role grants and the content that participants add adopt it in later work, which this decision does not settle in detail.

### Consent is part of a participant's status

A **Participant Status** carries the participant's whole consent table: one answer, and the RSVP deadline of an open invitation, for each embargo that the participant was invited to, answered or carried over to.
Each new status copies the table forward from the status before it, as it copies the other state it does not change.
The latest status is therefore the participant's whole state.

An embargo that is in the case's register but not in the table has not been asked about.
The register lists every embargo of the case, so this read is complete and unambiguous, and a proposal writes no status for a participant whose consent it does not change.

The CASE_MANAGER writes a new status when a participant's consent changes.
This includes an `Accept`, a `Reject` or a `Leave` from the participant, and also the CASE_MANAGER's own changes: a carry-over, a time-out, and its own consent as a stakeholder.
One act writes at most one new status for each participant whose consent it changes, carrying every row the act changed.
The status is attributed to the participant whose consent it records, is dated to the act, and is ledgered as the CASE_MANAGER's `Add(ParticipantStatus)`.

**Signatory** and **Lapsed** are read from the latest status and the register.
The separate consent rows and their `Create(EmbargoConsent)` and `Update(EmbargoConsent)` entries are removed.
A status is a whole object that carries `published`, so the consent rows' exemption from the received-time rule is removed with them.

A participant changes its consent only by an embargo activity.
A status claim from a participant that changes its consent is refused, and the reason names the activity to send.

### A participant claims what changed; the CASE_MANAGER records the whole status

A participant reports a change of its own state by an `Add(ParticipantStatus)` that carries only the fields that changed.
A field that the claim does not carry is unchanged.
A claim cannot clear a field: no wire object carries a null (VM-07-001), and the state a claim reports only moves forward, so a claim that carries a null is refused.

The CASE_MANAGER checks each claimed field against the participant's state.
It then merges the claim onto the participant's latest status and records the result as its own entry, which names the claim it came from.
The id, the time and the author of the recorded status come from the CASE_MANAGER's act, not from the claim.
The ledger holds both entries: the participant's claim as it arrived, then the CASE_MANAGER's `Add(ParticipantStatus)` with the whole status.

### A claim and a record are two types

A status claim is a type in which every field is optional.
The recorded status is a subclass of it that requires every field a whole status has.
This is the lifecycle-staged pattern of ADR-0033: the general type is the parent, and a more specific stage narrows it.
It differs in one way: the strict subclass owns the `ParticipantStatus` wire type, so a stored status always reads back as a whole status.
The parse edge reads a participant's received claim into the claim type, because the message that carries it says that it is a claim.

### Effect on earlier decisions

ADR-0212, ADR-0124 and ADR-0198 are edited in place to match, with the maintainer's approval on 2026-11-18.

- ADR-0212 keeps its consent states, triggers and register.
  Consent becomes a table on each status, "not asked" is read from the register, and each consent change is a CASE_MANAGER status entry that carries its time.
- ADR-0124 keeps its single apply function and its rule that a replica copies.
  An act's own entry becomes a record, and the CASE_MANAGER's entries after it carry each change.
- ADR-0198 keeps its rule that every received whole object carries `published`, with its other exemptions.
  The exemption for an embargo consent row is removed.

### Consequences

- Good, because every change of a participant's state, its consent included, is one dated status, so the case can be traced event by event.
- Good, because a replica never runs a step of a state machine: it copies statuses that the CASE_MANAGER wrote, and the nodes that applied an embargo answer on a replica are removed.
- Good, because the ledger keeps each participant's message as it was sent, beside the record of what it changed.
- Good, because a participant reports only what changed, so a report of one field cannot move another field backwards by mistake.
- Good, because the received-time rule has one exemption fewer.
- Bad, because an answer to an embargo becomes two entries, the answer and the status, where it was one.
- Bad, because every status repeats the consent table; at a few embargoes for each case this is small.
- Bad, because a claim that carries only changes cannot show that the participant's view of its own state has drifted from the CASE_MANAGER's.
- Bad, because the wire format changes: the status carries consent, a status claim may be partial, and `EmbargoConsent` is no longer sent on its own.
  The prototype owes no compatibility.

## Validation

- Unit tests merge claims onto statuses, and assert that a missing field is unchanged, that a claim carrying a null is refused, and that a claim that changes consent is refused.
- Tests assert that every consent change writes one dated status, and that signatory and lapsed read the same as before.
- The rebuild-from-ledger test of ADR-0124 rebuilds consent from statuses alone.
- A test asserts that no replica effect applies an entry that the CASE_MANAGER did not write, for the entry kinds that have adopted this decision.

## Pros and Cons of the Options

### Keep consent rows, and stamp each row with the time of the act

- Good, because it is the smallest change, and the rows keep their place on the participant record.
- Good, because it removes the exemption from the received-time rule.
- Bad, because consent stays the one part of a participant's state that is not in its status, so the latest status is not its whole state.
- Bad, because replicas keep applying embargo answers themselves.

### Move consent into the status, and let replicas apply answers from the participant's entry

- Good, because consent is dated and part of the whole state.
- Bad, because a replica must still run the consent step from a participant's message, so two kinds of entry change a replica's state.
- Bad, because the status that records an answer would have to be built on each replica, which reads the act's time on each replica.

### Move consent into the status, and let a replica change state only from the CASE_MANAGER's entries

- Good, because one author writes every change of state, and every replica copies it.
- Good, because consent is dated and part of the whole state.
- Bad, because each answer is two entries.

## More Information

The decision came from the planning interview for Idea #6615 on 2026-11-17 and 2026-11-18.
The specs that encode the replaced decisions are amended by the implementation work, together with the code that meets them, so that no spec describes behavior that the code does not have.
