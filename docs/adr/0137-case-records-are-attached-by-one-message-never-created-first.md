---
status: accepted-provisional
date: 2026-10-15
created: 2026-10-15
updated: 2026-10-15
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; specs/vultron-as2-mapping.yaml VAM-01-010; CLP-07-013;
  RSH-08-004; issues #4598, #4635, #4676
informed: []
stakeholder_type: [project-contributor]
---

# Case Records Are Attached by One Message, Never Created First

## Context and Problem Statement

ActivityStreams lets a sender attach a new object in two ways.
The sender can send one `Add` that carries the object.
As an alternative, the sender can send a `Create` that mints the object, and then an `Add` that attaches it.

The reference implementation attaches a case status and a participant status with one `Add`, and it carries a proposed embargo event on the `Invite` that proposes it.
A participant record comes into existence only when the CASE_MANAGER records the `Invite` that brings the invitee into the case ([ADR-0114](0114-joining-a-case-stub-invite-inert-participant.md)).
Its inbox refuses a received `Create` of any of these objects as an unrecognized activity (#4598).
That was recorded as a choice of the prototype, and the question of what the protocol allows stayed open (#4635, #4676).

A note works differently.
A note is content that can stand on its own, so `Create(Note)` mints it and a separate `Add(Note)` attaches it to the case.

This ADR records the maintainer's decision from a live interview on 2026-10-15.

## Decision Drivers

- A case status, a participant status, an embargo proposal and a participant record have no meaning apart from the case they belong to.
- Every change to the case file is its own committed ledger entry, and every committed entry needs a replica apply step or a declared no-replica-effect row (CLP-07-013, RSH-08-004).
- The message vocabulary is being made stable, so a form the protocol allows binds every future implementation.

## Considered Options

- One message attaches the record
- `Create` then `Add`
- `Create` with a case `context` attaches the record

## Decision Outcome

Chosen option: "One message attaches the record", because the records have no meaning apart from their attachment, and the other two options add a protocol state that nothing needs.

The protocol brings each record into the case with exactly one message.
A case status is attached by `Add(CaseStatus)` with the case as `target`.
A participant status is attached by `Add(ParticipantStatus)` with the participant as `target`.
A proposed embargo event travels on the `Invite` that proposes it.
A participant record is made by the CASE_MANAGER as a consequence of the `Invite` it records.
A `Create` of any of these records, sent to an inbox, is not a protocol message, and a receiver MUST NOT change the case file because of one.
This does not cover the `Create` that a CASE_MANAGER-authored ledger entry carries as its payload snapshot (CLP-07-013): that `Create` records a change the CASE_MANAGER made, and it is not a message a participant sends.

The protocol does not say how a receiver handles such a `Create`.
A peer may refuse it, log it or ignore it.
This codebase refuses it as an unrecognized activity, and it carries each record inline on its message; both are rules of this codebase only.

### Consequences

- Good, because a record exists in the case only once it is attached, so no "created but not attached" state needs a definition, a ledger entry or a replica step.
- Good, because a status change stays one message and one ledger entry.
- Neutral, because a general ActivityStreams client that mints objects with `Create` first cannot attach these records that way.
- Neutral, because notes keep their separate `Create` and `Add`, so the vocabulary has two attachment shapes.

## Validation

The test `test_received_create_of_a_case_record_is_refused_case_unchanged` in `test/adapters/driving/fastapi/test_inbox_outcome_chain.py` sends each of the four `Create` forms to an inbox.
It confirms that the case, the ledger and the outbox stay unchanged.

## Pros and Cons of the Options

### One message attaches the record

- Good, because it matches what the records mean: each one declares something about the case and nothing apart from it.
- Good, because the reference implementation already works this way and needs no new ledger entries or replica steps.
- Bad, because it adds a protocol restriction that ActivityStreams itself does not make.

### `Create` then `Add`

- Good, because it is the general ActivityStreams pattern, and notes already use it.
- Bad, because each `Create` changes the case file, so each one needs its own committed ledger entry and replica apply step.
- Bad, because the `Add` must resolve a reference to the stored object, and the protocol must define a record that exists but is not attached.

### `Create` with a case `context` attaches the record

- Good, because it is one message, like the chosen option.
- Bad, because each `Create` still needs its own ledger entry and replica apply step.
- Bad, because nothing in the vocabulary attaches by `context` today: even `Create(Note)` with a case `context` only mints the note, and the `Add` attaches it.

## More Information

Generated spec requirements: `vultron-as2-mapping.yaml` VAM-01-011.
VAM-01-010 holds this codebase's inline and refusal rules.
