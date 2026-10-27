---
title: Ownership Transfer — Closing an Offer Without an Answer (Withdrawal, Deadline)
status: active
kind: plan
tracks:
  - "#4491"
  - "#4055"
description: >
  Design for the ways an ownership-transfer Offer closes without the transferee's
  answer: owner withdrawal, and a binding answer deadline with lazy expiry.
related_specs:
  - specs/case-management.yaml
  - specs/case-ledger-processing.yaml
  - specs/triggerable-behaviors.yaml
  - specs/handler-protocol.yaml
  - specs/received-status-handling.yaml
  - specs/vultron-as2-mapping.yaml
  - specs/protocol-asks.yaml
related_notes:
  - notes/ownership-transfer.md
  - notes/bt-integration.md
---

# Ownership Transfer — Closing an Offer Without an Answer

This note is the design #4491 implements; withdrawal, the deadline and expiry
are all built. The Offer, Accept and Reject paths, and the one-open-Offer guard,
are in [ownership-transfer](ownership-transfer.md). Every closing entry's
`semantic_type` is in `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, which every "is it
open?" reader uses, so a new closing entry needs no other change to close the Offer.

## Withdrawal and Deadline (CM-21-015 – CM-21-017)

One open Offer per case would let a silent transferee block every later transfer, so
an Offer can also close without an answer (#4490):

- **Withdrawal (CM-21-015, TRIG-11-006) — implemented.** The owner sends `Undo` of
  its own proposal, `Undo(Offer(Offer(VulnerabilityCase)))`, to the CASE_MANAGER
  through the `withdraw-case-ownership-transfer` trigger, from its own identity
  (not delegated). The CASE_MANAGER withdraws the Offer it made from that proposal,
  whose id it derives (`ownership_offer_id`, ADR-0148). The trigger refuses, as not
  found, a case the owner does not hold or one with no CASE_MANAGER: a withdrawal
  goes to the CASE_MANAGER or nowhere (PCR-08-011). It also refuses, as not found,
  an `offer_id` naming anything but the owner's own proposal, such as the
  CASE_MANAGER's Offer: the owner withdraws what it sent. The CASE_MANAGER ledgers it as
  `undo_case_ownership_transfer` and broadcasts it like a Reject
  (`UndoCaseOwnershipTransferReceivedUseCase`,
  `create_undo_ownership_transfer_tree`); ownership is unchanged.
  - **Who may withdraw.** The rule is `CASE_OWNER` at the CASE_MANAGER, which the
    factory checks against the recorded Offer with `SenderIsOwnershipOffererNode`:
    the sender must be the participant the Offer speaks for: its `attributedTo`,
    since the CASE_MANAGER is the `actor` of every Offer it makes (CM-24-002,
    ADR-0148). An `attributedTo` on an Offer the CASE_MANAGER did not send is an
    unchecked claim and is ignored (`RecordedOwnershipOffer.offerer_id`). The
    offerer must still hold
    `CASE_OWNER`; that is standing too, so an offerer whose Offer an Accept closed
    is refused for it before the Offer's state is read (#4437). A redelivery of the
    Undo that closed the Offer is a duplicate, so the role is not re-checked for
    it: it stays `SKIPPED` even after a later Offer moved ownership on
    (HP-01-003).
  - **Closed and redelivered.** The reply trees share the open-Offer guard
    (`OwnershipOfferOpenNode`, `case/nodes/ownership_reply_guard.py`), which runs
    right after the sender check: a withdrawal of a closed Offer is `REFUSED` and a
    redelivery of the Undo that closed it is `SKIPPED` (HP-01-003). A sender with
    no standing is refused before the Offer's state is read (#4437).
  - **Ledger.** `undo_case_ownership_transfer` is `NO_REPLICA_EFFECT`, for the
    Reject's reason (RSH-08-004). `("Undo", "Offer")` is a canonical, owner-authored
    payload signature.
- **Deadline (CM-21-016, TRIG-11-007) — implemented.** The Offer may carry an
  activity-level `end_time`, set through the offer trigger's optional `end_time`
  (aware, in the future, held in UTC). Unlike an embargo `Invite.end_time`
  (CM-28-001), it is binding: an Accept or Reject processed after it is refused.
  - **Where it is read.** The wire edge puts it on the event in UTC
    (`ProposeCaseOwnershipTransferReceivedEvent.proposed_answer_deadline`, from
    the inner Offer, and `OfferCaseOwnershipTransferReceivedEvent.answer_deadline`)
    and on the activity snapshot with the offset it arrived with (CS-13-005), so the
    ledgered Offer carries it; `RecordedOwnershipOffer.end_time` reads it back in
    UTC. The owner sets it on the proposal's inner Offer, and the Offer the
    CASE_MANAGER makes carries it to the transferee (CM-21-016).
  - **One reader, the Offer's own deadline.** `OwnershipOfferOpenNode` refuses a
    reply at or after the ledgered Offer's `end_time`, and `open_ownership_offer`
    treats an Offer past it as closed, so a new proposal is admitted
    (`RecordedOwnershipOffer.is_open_at`). Both run behind the CASE_MANAGER
    gate and compare against one `now` per delivery, read from `now_utc()`.
- **Expiry (CM-21-017) — implemented.** The expiry is an observation, not an
  act: nothing is ledgered or sent for it, because every holder of the ledger
  can read the deadline from the Offer and no replica changes when it passes
  (ADR-0152). The CASE_MANAGER reads it lazily, when it next processes an
  Accept, Reject or Undo of the Offer or a new proposal for the case; it is no
  clock decision (CLP-10-025). A late reply from a sender with no standing is
  refused by the sender guard first, before the Offer's state is read
  (HP-01-006, CM-21-019); after the case is fully closed the post-close door
  guard ends the tree first (CM-23-013).
  - **Ask kind.** `OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRY` is `AskExpiry.VOID`
    (ASK-03-002): a late reply authorizes nothing.
