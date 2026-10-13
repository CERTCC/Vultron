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
related_notes:
  - notes/ownership-transfer.md
---

# Ownership Transfer — Closing an Offer Without an Answer

This note is the design #4491 implements. Withdrawal is built; the deadline and
expiry are not yet. The Offer, Accept and Reject paths, and the one-open-Offer guard,
are in [ownership-transfer](ownership-transfer.md). Every closing entry's
`event_type` is in `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, which every "is it
open?" reader uses, so a new closing entry needs no other change to close the Offer.

## Withdrawal and Deadline (CM-21-015 – CM-21-017)

One open Offer per case would let a silent transferee block every later transfer, so
an Offer can also close without an answer (#4490):

- **Withdrawal (CM-21-015, TRIG-11-006) — implemented.** The owner that made an
  open Offer sends `Undo(Offer(VulnerabilityCase))` to the CASE_MANAGER through the
  `withdraw-case-ownership-transfer` trigger, from its own identity (not
  delegated), naming the Offer it made. The trigger refuses, as not found, a case
  the owner does not hold or one with no CASE_MANAGER: a withdrawal goes to the
  CASE_MANAGER or nowhere (PCR-08-011). The CASE_MANAGER ledgers it as
  `undo_case_ownership_transfer` and broadcasts it like a Reject
  (`UndoCaseOwnershipTransferReceivedUseCase`,
  `create_undo_ownership_transfer_tree`); ownership is unchanged.
  - **Who may withdraw.** The guard is `SenderIsOwnershipOffererNode`: the sender
    must be the participant the recorded Offer speaks for and still hold
    `CASE_OWNER`. That is its `attributedTo` only when the CASE_MANAGER is its
    `actor` (the delegated shape, CM-24-002), else its `actor`. An `attributedTo`
    on an Offer a participant sent itself is an unchecked claim, ignored as the
    Offer handler ignores it when forwarding (`RecordedOwnershipOffer.offerer_id`).
  - **Closed and redelivered.** It shares `SenderIsOwnershipOfferPartyNode` with the
    transferee's guard, so a withdrawal of a closed Offer is `REFUSED` and a
    redelivery of the Undo that closed it is `SKIPPED` (HP-01-003).
  - **Ledger.** `undo_case_ownership_transfer` is `NO_REPLICA_EFFECT`, for the
    Reject's reason (RSH-08-004). `("Undo", "Offer")` is a canonical, owner-authored
    payload signature.
- **Deadline (CM-21-016, TRIG-11-007).** The Offer may carry an activity-level
  `end_time`, set through the offer trigger. Unlike an embargo `Invite.end_time`
  (CM-28-001), it is binding: an Accept or Reject processed after it is refused.
- **Expiry (CM-21-017).** The CASE_MANAGER finds an expired Offer lazily, when it next
  processes an answer, an Undo or a new Offer for the case, and commits a distinct
  expiry entry before acting. Replicas learn expiry from that entry and never compute
  it, as for embargo Invite expiry (CM-28-014). The expiry entry's `event_type` joins
  `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`.
