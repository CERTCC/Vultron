---
status: proposed
date: 2026-10-20
created: 2026-10-20
updated: 2026-10-20
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0039, ADR-0053, ADR-0109, ADR-0113;
  notes/ownership-transfer.md, notes/datalayer-design.md; issue #4911
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

## Decision Drivers

- One transfer, one Offer: the Offer that is ledgered, answered, closed and expired is the same activity.
- The CASE_MANAGER emits only under its own identity, and nothing it emits or stores is keyed by an id another party chose (ADR-0109, DL-06-006).
- The owner's request and the CASE_MANAGER's Offer are told apart by their shape, not by who sent them (ADR-0039).
- The same propose-then-execute shape the case invitation and the embargo relay already use (ADR-0109, ADR-0113).
- No new vocabulary type where the ActivityStreams vocabulary already says it.

## Considered Options

- **A. Keep the forward.** The owner's `Offer(VulnerabilityCase)` is the Offer; the CASE_MANAGER forwards a linked copy.
- **B. Relay the owner's Offer unchanged.** The CASE_MANAGER delivers the owner's Offer as received, `actor` still the owner, as a courier.
- **C. A dedicated proposal object.** The owner offers a new ownership-transfer-proposal object to the CASE_MANAGER, which emits the Offer.
- **D. The owner offers the Offer.** The owner sends `Offer(Offer(VulnerabilityCase))` to the CASE_MANAGER; the inner Offer is the template, and the CASE_MANAGER emits its own `Offer(VulnerabilityCase)` from it.

## Decision Outcome

Chosen option: **D. The owner offers the Offer**, because it is the only option with one Offer per transfer, authored by the CASE_MANAGER under its own id, whose request is told apart from the Offer by shape without a new type.

An actor that works through the CASE_MANAGER proposes, and the CASE_MANAGER executes the act under its own identity, with `attributedTo` the proposer.
For ownership transfer:

1. **The owner proposes.**
   The Case Owner sends `Offer(Offer(VulnerabilityCase))` to the CASE_MANAGER.
   The inner Offer carries what the owner decides: the case as its object, the transferee as its `target`, and the optional answer deadline as its `endTime` (CM-21-016).
2. **The CASE_MANAGER makes the Offer.**
   It admits the proposal only from the Case Owner and only while no other Offer for the case is open (CM-21-014, CM-21-019).
   It validates the inner Offer rather than copying it: the object is this case and the target is an actor it can address.
   It mints its own id for the `Offer(VulnerabilityCase)` it emits, sets `actor` to itself and `attributedTo` to the owner, and ignores any id, `actor` or `to` the owner put inside.
   That emitted Offer is the one the ledger records.
3. **The transferee answers that Offer.**
   Its `Accept` or `Reject` names the CASE_MANAGER's Offer by its id, and the open-Offer check reads that id.
   No back-link is resolved.
4. **The owner withdraws its proposal.**
   The owner sends `Undo` of its own proposal; the CASE_MANAGER withdraws the Offer it made from it and ledgers the withdrawal (CM-21-015).
   The owner needs nothing it learned from the ledger to withdraw.

### Consequences

- Good, because a transfer has one Offer, so answer resolution, open-Offer checks and the demo all use one id.
- Good, because the transferee holds the Offer it answers in its intake archive, the offerer holds its own proposal, and a bystander never answers, so no replica keeps a ledger-derived record of the Offer: `VultronOwnershipTransferOfferRecord` and `ApplyOfferOwnershipTransferFromLedgerNode` are deleted, which resolves #4911.
- Good, because the request and the Offer differ in shape, so neither pattern needs a sender or direction check to tell them apart.
- Good, because ownership transfer joins the propose-then-execute shape of the case invitation and the embargo relay.
- Bad, because the wire flow changes for an existing message: the owner's message gains a nesting level, and its pattern, extractor branch, trigger and received use case change with it.
- Bad, because the CASE_MANAGER must validate a nested activity it will not send as is, a check the forward did not need.
- Neutral, because the CASE_MANAGER's Offer keeps `actor` and `attributedTo` as CM-24-001 and CM-24-002 require; only its origin changes from a forward to an act.

## Validation

- A test delivers the owner's proposal to the CASE_MANAGER and asserts one `Offer(VulnerabilityCase)` leaves it, with an id the CASE_MANAGER minted, `attributedTo` the owner, and a ledger entry whose snapshot is that Offer.
- A test answers that Offer from the transferee and asserts the answer closes it with no back-link lookup.
- A test sends an inner Offer naming another case, or an inner id that collides with a stored object, and asserts the CASE_MANAGER refuses it or ignores the id.
- A test sends the proposal from a participant that is not the Case Owner, and another while an Offer for the case is open, and asserts each is refused with no ledger commit and no outbound Offer (CM-21-019, CM-21-014).
- A test sends the owner's `Undo` of its proposal and asserts the CASE_MANAGER ledgers the withdrawal of the Offer it made from it, which closes that Offer (CM-21-015).
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

## More Information

This record partially supersedes ADR-0053: the routing of the Offer and its answers through the CASE_MANAGER stands, and the forward of the owner's Offer is replaced by the CASE_MANAGER's own Offer.
The requirements that change with it are CM-21-005 (the forward), CM-21-014 (the open-Offer gate, now applied to the proposal), CM-21-015 (the withdrawal, now an `Undo` of the proposal), CM-21-016 (the deadline, now carried on the inner Offer), CM-21-018 (the back-link, retired) and CM-21-019 (sender standing for the proposal and for the Offer at the transferee); each is amended in the implementation change that makes the code match.
The same shape for the case proposal, `Offer(Create(VulnerabilityCase))` in place of `Offer(CaseProposal)`, is not decided here; it is captured for later consideration in #4936.
