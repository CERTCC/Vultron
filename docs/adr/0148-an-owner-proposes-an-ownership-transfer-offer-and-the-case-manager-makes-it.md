---
status: proposed
date: 2026-10-20
created: 2026-10-20
updated: 2026-10-26
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0039, ADR-0053, ADR-0109, ADR-0113;
  ADR-0114; notes/ownership-transfer.md, notes/datalayer-design.md;
  issues #4911, #5186, #5189
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0053-ownership-transfer-routed-via-caseactor.md
---

# An Owner Proposes an Ownership-Transfer Offer and the CASE_MANAGER Makes It

## Context and Problem Statement

ADR-0053 routes the ownership-transfer Offer through the CASE_MANAGER: the Case Owner sends `Offer(VulnerabilityCase)` to the CASE_MANAGER, which records it and forwards it to the transferee.
ADR-0109 then said a participant reaches the CASE_MANAGER by message and the CASE_MANAGER acts, and that the ownership-transfer offer follows the shape of the case invitation, where the owner's request is an `Offer(CaseParticipant)` and the CASE_MANAGER emits the `Invite` the invitee answers.

The ownership flow never took that shape.
The owner's request and the CASE_MANAGER's message are the same activity type, so the CASE_MANAGER's step became a forward: a second `Offer(VulnerabilityCase)` with its own id, `actor` the CASE_MANAGER and `attributedTo` the owner (CM-24-001, CM-24-002), linked back to the owner's Offer by `inReplyTo` (CM-21-018).
There are then two Offers for one transfer, and three things follow:

- The ledger records the owner's Offer, while the transferee receives and answers the forward, so the CASE_MANAGER must resolve every answer through the back-link before it can tell whether the Offer is open.
- A replica that learns of the Offer only from the ledger keeps a core record of it under the owner's Offer id, so the answer triggers can find it.
  That is a record the receiver writes under an id another party chose, the shape CLP-10-017 and DL-06-006 rule out for received activities (#4911).
- A demo and every reader of an answer must know which of the two ids it holds.

How should the owner's request and the Offer the transferee answers relate, so that a transfer has exactly one Offer?

Revision 2 adds a second question.
The check revision 1 named on the transferee was only that it is an actor the CASE_MANAGER can address, neither the CASE_MANAGER nor the proposer, and that leaves two gaps.
The Offer carries the case inline, with its active embargo, its participant records and its reports, so an actor outside the case is sent embargoed case content just by being offered the case, which the entitlement rule forbids (CM-10-004, ADR-0114).
And an actor with no participant record cannot be granted `CASE_OWNER`, since that role lives on the participant record (CM-21-002), so an accepted transfer to such an actor leaves the case with no owner.

Who may be offered ownership of a case?

## Decision Drivers

- One transfer, one Offer: the Offer that is ledgered, answered, closed and expired is the same activity.
- The CASE_MANAGER emits only under its own identity, and nothing it emits or stores is keyed by an id another party chose (ADR-0109, DL-06-006).
- The owner's request and the CASE_MANAGER's Offer are told apart by their shape, not by who sent them (ADR-0039).
- The same propose-then-execute shape the case invitation and the embargo relay already use (ADR-0109, ADR-0113).
- No new vocabulary type where the ActivityStreams vocabulary already says it.
- No actor receives case content before it is entitled to it, and while an embargo is active that means agreeing to the embargo first (CM-10-004).
- A transfer must end with exactly one participant holding `CASE_OWNER` (CM-21-001).

## Considered Options

- **A. Keep the forward.** The owner's `Offer(VulnerabilityCase)` is the Offer; the CASE_MANAGER forwards a linked copy.
- **B. Relay the owner's Offer unchanged.** The CASE_MANAGER delivers the owner's Offer as received, `actor` still the owner, as a courier.
- **C. A dedicated proposal object.** The owner offers a new ownership-transfer-proposal object to the CASE_MANAGER, which emits the Offer.
- **D. The owner offers the Offer.** The owner sends `Offer(Offer(VulnerabilityCase))` to the CASE_MANAGER; the inner Offer is the template, and the CASE_MANAGER emits its own `Offer(VulnerabilityCase)` from it.

For who may be offered ownership (revision 2):

- **T1. Any actor the CASE_MANAGER can address.** The rule as revision 1 wrote it.
- **T2. Any listed participant.** The transferee must have a participant record on the case, whether or not it has joined.
- **T3. A listed participant, offered without case content.** As T2, with the Offer carrying the case by reference only, so an invitee that has not joined can be offered the case.
- **T4. An active participant.** The transferee must be an active participant (CM-10-004) both when the owner proposes the transfer and when the transferee accepts it.

## Decision Outcome

Chosen option: **D. The owner offers the Offer**, because it is the only option with one Offer per transfer, authored by the CASE_MANAGER under its own id, whose request is told apart from the Offer by shape without a new type.

An actor that works through the CASE_MANAGER proposes, and the CASE_MANAGER executes the act under its own identity, with `attributedTo` the proposer.
For ownership transfer:

1. **The owner proposes.**
   The Case Owner sends `Offer(Offer(VulnerabilityCase))` to the CASE_MANAGER.
   The inner Offer carries what the owner decides: the case as its object, the transferee as its `target`, and the optional answer deadline as its `endTime` (CM-21-016).
2. **The CASE_MANAGER makes the Offer.**
   It admits the proposal only from the Case Owner and only while no other Offer for the case is open (CM-21-014, CM-21-019).
   It validates the inner Offer rather than copying it: the object is this case and the target is an actor it can address and an active participant of the case, other than itself and the proposer (CM-21-021).
   Otherwise it refuses the proposal, makes no Offer and commits no ledger entry.
   It mints its own id for the `Offer(VulnerabilityCase)` it emits, sets `actor` to itself and `attributedTo` to the owner, and ignores any id, `actor` or `to` the owner put inside.
   That emitted Offer is the one the ledger records.
3. **The transferee answers that Offer.**
   Its `Accept` or `Reject` names the CASE_MANAGER's Offer by its id, and the open-Offer check reads that id.
   No back-link is resolved.
   The CASE_MANAGER admits an `Accept` only if the transferee is still an active participant, since it can be removed, or lapse when an embargo revision it has not agreed to comes into force, between the Offer and the answer; otherwise it refuses the `Accept` with no role change (CM-21-021).
4. **The owner withdraws its proposal.**
   The owner sends `Undo` of its own proposal; the CASE_MANAGER withdraws the Offer it made from it and ledgers the withdrawal (CM-21-015).
   The owner needs nothing it learned from the ledger to withdraw.
5. **The owner invites first.**
   To hand a case to an actor not yet in it, the owner invites that actor, and offers the case once the actor has joined and agreed to any active embargo.

For who may be offered ownership, chosen option: **T4. An active participant**, because it is the only option under which the Offer's case content goes only to an actor already entitled to it, and it reuses the entitlement rule the protocol already has rather than adding a new one (revision 2).

### Consequences

- Good, because a transfer has one Offer, so answer resolution, open-Offer checks and the demo all use one id.
- Good, because the transferee holds the Offer it answers in its intake archive, the offerer holds its own proposal, and a bystander never answers, so no replica keeps a ledger-derived record of the Offer: `VultronOwnershipTransferOfferRecord` and `ApplyOfferOwnershipTransferFromLedgerNode` are deleted, which resolves #4911.
- Good, because the request and the Offer differ in shape, so neither pattern needs a sender or direction check to tell them apart.
- Good, because ownership transfer joins the propose-then-execute shape of the case invitation and the embargo relay.
- Bad, because the wire flow changes for an existing message: the owner's message gains a nesting level, and its pattern, extractor branch, trigger and received use case change with it.
- Bad, because the CASE_MANAGER must validate a nested activity it will not send as is, a check the forward did not need.
- Good, because the Offer carries case content only to an actor entitled to it, and the transferee always has a participant record, so an accepted transfer always ends with one `CASE_OWNER`.
- Bad, because handing a case to an actor outside it takes two steps, an invitation and then an Offer.
- Neutral, because the CASE_MANAGER's Offer keeps `actor` and `attributedTo` as CM-24-001 and CM-24-002 require; only its origin changes from a forward to an act.

## Validation

- A test delivers the owner's proposal to the CASE_MANAGER and asserts one `Offer(VulnerabilityCase)` leaves it, with an id the CASE_MANAGER minted, `attributedTo` the owner, and a ledger entry whose snapshot is that Offer.
- A test answers that Offer from the transferee and asserts the answer closes it with no back-link lookup.
- A test sends an inner Offer naming another case, or an inner id that collides with a stored object, and asserts the CASE_MANAGER refuses it or ignores the id.
- A test sends the proposal from a participant that is not the Case Owner, and another while an Offer for the case is open, and asserts each is refused with no ledger commit and no outbound Offer (CM-21-019, CM-21-014).
- A test sends the owner's `Undo` of its proposal and asserts the CASE_MANAGER ledgers the withdrawal of the Offer it made from it, which closes that Offer (CM-21-015).
- A test delivers a proposal naming an actor off the roster, an invitee that has not joined, a removed participant and a participant that is not a signatory to the active embargo, and asserts each is refused with no ledger entry and no Offer made (CM-21-021).
- A test lets the transferee stop being active between the Offer and its `Accept`, and asserts the `Accept` is refused with no role change, and a test asserts that no admitted `Accept` leaves the case with no participant holding `CASE_OWNER` (CM-21-021).
- An architecture test or grep asserts `VultronOwnershipTransferOfferRecord` no longer exists.

## Pros and Cons of the Options

### A. Keep the forward

- Good, because it is built.
- Bad, because a transfer has two Offers, every answer is resolved through a back-link (CM-21-018), and a replica keeps a record of the owner's Offer under the owner's id (#4911).

### B. Relay the owner's Offer unchanged

- Good, because there is literally one activity end to end.
- Bad, because the CASE_MANAGER delivers an activity whose `actor` is not the sender, which every receiver must then exempt from the CASE_MANAGER-sender check.
- Bad, because the Offer the ledger records keeps an id the owner chose, so the CASE_MANAGER's store holds the owner's id for a record it treats as its own.

### C. A dedicated proposal object

- Good, because the request and the Offer differ by type, as ADR-0039 did for the case-manager-role offer.
- Bad, because it adds a vocabulary type for what `Offer(Offer(…))` already says.

### D. The owner offers the Offer (chosen)

- Good, because the request's object is the Offer the owner wants made, so the CASE_MANAGER's act is fully described by the request.
- Good, because it needs no new type.
- Bad, because the CASE_MANAGER must validate the nested template.

### T1. Any actor the CASE_MANAGER can address

- Good, because an owner can hand a case to anyone in one step.
- Bad, because the Offer sends the embargo, the reports and the participant list to an actor that has agreed to nothing.
- Bad, because an actor with no participant record cannot hold `CASE_OWNER`, so an accepted transfer leaves the case with no owner.

### T2. Any listed participant

- Good, because the transferee has a participant record, so the role can always be granted.
- Bad, because an invitee that has not joined is not entitled to case content, and the Offer still sends it the whole case.

### T3. A listed participant, offered without case content

- Good, because an invitee could be offered the case before it joins without seeing case content.
- Bad, because the transfer and the embargo negotiation then run in parallel, and an accepted Offer from an actor that later declines the embargo has to be reconciled.
- Bad, because it changes the Offer's shape option D settles, for a step the invitation already provides.

### T4. An active participant (chosen)

- Good, because it uses the existing entitlement rule (CM-10-004) and closes both gaps.
- Bad, because it adds a step for a transferee outside the case.

## More Information

This record partially supersedes ADR-0053: the routing of the Offer and its answers through the CASE_MANAGER stands, and the forward of the owner's Offer is replaced by the CASE_MANAGER's own Offer.
The requirements that change with it are CM-21-005 (the forward), CM-21-014 (the open-Offer gate, now applied to the proposal), CM-21-015 (the withdrawal, now an `Undo` of the proposal), CM-21-016 (the deadline, now carried on the inner Offer), CM-21-018 (the back-link, retired) and CM-21-019 (sender standing for the proposal and for the Offer at the transferee); each is amended in the implementation change that makes the code match.
The same shape for the case proposal, `Offer(Create(VulnerabilityCase))` in place of `Offer(CaseProposal)`, is not decided here; it is captured for later consideration in #4936.
Revision 2 (#5186) adds the transferee rule, CM-21-021, and the active-participant condition in CM-21-005; #5189 builds it.
