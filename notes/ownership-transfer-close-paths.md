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
    (`OwnershipOfferOpenNode`, `case/nodes/ownership_offer_guard.py`), which runs
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
  - **Two readers, one deadline.** `OwnershipOfferOpenNode` refuses a
    reply at or after `end_time` even when no expiry entry exists, so a lost
    expiry commit never admits a late answer; the expiry step runs first and
    normally makes the guard refuse it as closed instead. Both compare against
    the same `now`, read once per delivery from `now_utc()`.
- **Expiry (CM-21-017) — implemented.** The CASE_MANAGER finds an expired Offer
  lazily, when it next processes an Accept, Reject or Undo of the Offer or a new
  proposal for the case, and commits a distinct
  `offer_case_ownership_transfer_expired` entry before acting
  (`ExpireOverdueOwnershipOfferNode`, a clock decision). The
  snapshot is the CASE_MANAGER's own `Expire(Offer)`, stamped with its clock; its
  `semantic_type` is in `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, so it closes
  the Offer. It is `NO_REPLICA_EFFECT`: replicas learn expiry from the entry and
  never compute it, as for embargo Invite expiry (CM-28-014).
  - **Why a clock decision.** The expiry is the CASE_MANAGER's own decision
    from its clock, committed as its own entry before the activity is judged
    (CLP-07-013), and ledgered even when that activity is then admitted (a new
    proposal, CM-21-014). So each of the four received trees passes it as a
    clock decision, which the factory runs after the door guards and before
    the open-Offer guards (CLP-10-025, ADR-0135; [bt-integration](bt-integration.md)
    § "The Received-Side Stages"); after `case_fully_closed`
    the post-close door guard ends the tree first (CM-23-013).
  - **Only the party prompts it.** An Accept, Reject or Undo prompts the expiry
    only when it names the open Offer and its sender is that Offer's transferee
    (Accept, Reject) or offerer (Undo) — `ExpiryPrompt` / `OfferParty` — so a
    sender with no standing never makes the CASE_MANAGER write (HP-01-006), as
    the embargo Invite expiry checks the invitee first. A new Offer prompts it
    with no prompt, because its handler refuses a sender that is not the Case
    Owner before the expiry runs (CM-21-019).
  - **Ask kind.** `OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRY` is `AskExpiry.VOID`
    (ASK-03-002): a late reply authorizes nothing.
