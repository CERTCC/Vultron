---
status: proposed
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-13
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0109, ADR-0116, ADR-0148, ADR-0196;
  specs/case-management.yaml CM-16, CM-21, CM-24, CM-31;
  notes/activitystreams-semantics.md, notes/as2-vocabulary-alignment.md;
  issues #6245, #6293
informed: []
partially_supersedes:
  - 0116-removing-a-participant-withdraws-entitlement-not-membership.md
  - 0148-an-owner-proposes-an-ownership-transfer-offer-and-the-case-manager-makes-it.md
stakeholder_type: [project-contributor]
---

# An Owner's Request Is an Offer of the Act, Which the CASE_MANAGER Accepts and Makes

## Context and Problem Statement

A Vultron activity states something its sender has already done; it is not a command.
The Case Owner decides who leaves a case and who is let back in, but the CASE_MANAGER holds the participant records and makes every change to them.
Today the Owner asks for a removal by sending `Remove(CaseParticipant)[target=VulnerabilityCase]`, and for a reinstatement by sending `Add(CaseParticipant)[target=VulnerabilityCase]` (ADR-0116).
Each states that the Owner removed or added a participant record, which the Owner has not done: the message is a command written as a notification.
It also names the CASE_MANAGER's bookkeeping record instead of the actor the Owner decided about.

The ownership transfer already has the Owner propose the act, as `Offer(Offer(VulnerabilityCase))`, and the CASE_MANAGER make it (ADR-0148).
That proposal gets no answer of its own, though: the Owner learns the outcome only from the ledger.
A peer reading ActivityStreams 2.0 expects every Offer to be answered with an Accept or a Reject.

When the CASE_MANAGER acts on someone's behalf it credits the asker in `attributedTo`, but it does not name the request it carried out.

How does the Case Owner ask the CASE_MANAGER for an act on the case, and how does the CASE_MANAGER answer and carry it out?

## Decision Drivers

- An activity states what its sender did; a request for someone else to act is an Offer of that act (VOC Offer: "Sally is offering to add a File to Folder A").
- Distinct actors communicate only through the protocol. Where they run, on one server or two, changes nothing on the wire or in the ledger (ADR-0109).
- An answer names what it answers (VOC `inReplyTo`).
- An Offer is answered with an Accept or a Reject, as ActivityPub answers a Follow. The Accept is a decision, not a receipt: delivery is acknowledged by the HTTP response.
- One fact has one activity, so a peer never counts two removals where one happened.
- What the CASE_MANAGER tells the Owner never contradicts what its ledger records.

## Considered Options

- A direct act from the Owner, naming the actor: `Remove(Actor, origin=<case>)`
- An Offer of the act, answered only by the act (the ADR-0148 shape)
- An Offer of the act, answered by an Accept, and the act made by the CASE_MANAGER

## Decision Outcome

Chosen option: "An Offer of the act, answered by an Accept, and the act made by the CASE_MANAGER", because it is the only option in which every message states what its sender did, every Offer gets an answer, and the ledger records the act of the actor that made the change.

### The Owner offers the act, naming the actor

The Owner asks for a removal with `Offer(Remove(<Actor>, origin=<case>))` and for a reinstatement with `Offer(Add(<Actor>, target=<case>))`, sent to the CASE_MANAGER only.
The inner act names the actor the Owner decided about, as a typed reference, not the participant record.
Each actor has one participant record per case, so the actor identifies the record the CASE_MANAGER changes.
A reinstatement reuses that record, which keeps the participant's history and consent (ADR-0116).

### The CASE_MANAGER refuses, or accepts and makes the act

The CASE_MANAGER refuses a request that breaks its rules with a refusal notice (ADR-0196), changing nothing.
Otherwise it sends the Owner an `Accept` of the Offer and makes the act itself: `actor` is the CASE_MANAGER, `attributedTo` the Owner, and `inReplyTo` the Owner's Offer.
The Accept says the CASE_MANAGER decided to carry the request out; the act says it was carried out.
The Accept and the act commit together, so the Owner never holds an Accept for an act that did not happen.

The act the CASE_MANAGER makes is the ledger entry, and the same activity, with the same id, goes directly to the actor it names.
There is no second, unledgered notice.
A replica still applies the change only from the ledger entry.

### Ownership transfer gets the same answer

The ownership-transfer proposal keeps its form (ADR-0148), and the CASE_MANAGER now also answers it with an `Accept` when it makes the transfer Offer, committed together.
That Offer names the proposal in `inReplyTo`.

### A delegated act names its request

When the CASE_MANAGER makes an act another actor asked for, it sets `attributedTo` to the asker and `inReplyTo` to the request it received.
Both are set exactly when the asker is a different actor from the `actor`.
An actor that holds both roles acts directly, with neither.
Every delegated act has a request to name, because a distinct asker always reaches the CASE_MANAGER by message.

### Consequences

- Good, because every message states what its sender did, and an ActivityStreams 2.0 reader takes each one at face value.
- Good, because `Add(CaseParticipant)` no longer means the Owner's request, which frees it for the CASE_MANAGER's own record-keeping.
- Good, because every Offer the CASE_MANAGER receives gets an answer, so one rule covers removal, reinstatement and ownership transfer.
- Good, because a removal is one activity, so a peer cannot mistake a notice for a second removal.
- Bad, because the removal and reinstatement messages change form, and with them the received trees, the message patterns, the examples, the message reference and the manage-participants demo. Pre-1.0, the old form is replaced outright, with no compatibility shim.
- Bad, because the Owner now receives two messages for one request: the Accept directly and the act by ledger fan-out.

## Validation

- A test sends the Owner's `Offer(Remove(<Actor>, origin=<case>))` and asserts that the Owner receives an Accept, and that the ledger holds one entry, the CASE_MANAGER's `Remove`, with `attributedTo` the Owner and `inReplyTo` the Offer.
- A test asserts that the removed actor receives that same `Remove`, by id, and no other removal message.
- A test asserts that a refused request leaves no ledger entry and sends no Accept.
- A test asserts that the ownership-transfer proposal is answered with an Accept committed with the transfer Offer.
- A test asserts that every delegated act carries `inReplyTo` naming the received request.

## Pros and Cons of the Options

### A direct act from the Owner, naming the actor

- Good, because it is one message and the ledger records the Owner's own act, as today.
- Bad, because it states that the Owner removed the actor when the CASE_MANAGER does the removing: it is a command.

### An Offer of the act, answered only by the act

- Good, because the CASE_MANAGER's act is the only answer, so the Owner gets one message.
- Bad, because the Offer gets no Accept or Reject, which an ActivityStreams 2.0 reader expects.
- Bad, because the Owner cannot tell, from what it was sent, the CASE_MANAGER's decision apart from its act.

### An Offer of the act, answered by an Accept, and the act made by the CASE_MANAGER

- Good, because the decision and the change are separate messages, each true of its sender.
- Good, because it matches how ActivityPub answers a request: an Accept, then the change it agreed to.
- Bad, because it adds an Accept to every request.

## More Information

This record partially supersedes ADR-0116 in its choice of the removal and reinstatement messages.
ADR-0116's decision that removal is a stored fact that withdraws entitlement, not membership, stands.
It partially supersedes ADR-0148 in the answer to the Owner's proposal; the proposal's form and the CASE_MANAGER making the transfer Offer stand.

The vocabulary rules behind it, including that `origin` names where something comes from or leaves, are in `notes/activitystreams-semantics.md` § "Choosing AS2 Terms".
The work it implies is tracked in `notes/as2-vocabulary-alignment.md`.
