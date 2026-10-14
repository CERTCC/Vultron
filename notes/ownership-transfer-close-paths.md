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
---

# Ownership Transfer — Closing an Offer Without an Answer

This note is the design #4491 implements; withdrawal, the deadline and expiry
are all built. The Offer, Accept and Reject paths, and the one-open-Offer guard,
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
  - **Who may withdraw.** The rule is `CASE_OWNER` at the CASE_MANAGER, which the
    factory checks against the recorded Offer with `SenderIsOwnershipOffererNode`:
    the sender must be the participant the Offer speaks for. That is its
    `attributedTo` only when the CASE_MANAGER is its `actor` (the delegated shape,
    CM-24-002), else its `actor`. An `attributedTo` on an Offer a participant sent
    itself is an unchecked claim, ignored as the Offer handler ignores it when
    forwarding (`RecordedOwnershipOffer.offerer_id`). The offerer must still hold
    `CASE_OWNER`; that is standing too, so an offerer whose Offer an Accept closed
    is refused for it before the Offer's state is read (#4437).
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
    (`OfferCaseOwnershipTransferReceivedEvent.answer_deadline`) and on the
    activity snapshot with the offset it arrived with (CS-13-005), so the
    ledgered Offer carries it; `RecordedOwnershipOffer.end_time` reads it back in
    UTC. The CASE_MANAGER's forward carries it to the transferee.
  - **Two readers, one deadline.** `OwnershipOfferOpenNode` refuses a
    reply at or after `end_time` even when no expiry entry exists, so a lost
    expiry commit never admits a late answer; the expiry step runs first and
    normally makes the guard refuse it as closed instead. Both compare against
    the same `now`, read once per delivery from `now_utc()`.
- **Expiry (CM-21-017) — implemented.** The CASE_MANAGER finds an expired Offer
  lazily, when it next processes an Accept, Reject or Undo of the Offer or a new
  Offer for the case, and commits a distinct
  `offer_case_ownership_transfer_expired` entry before acting
  (`create_ownership_offer_expiry_tree`, `ExpireOverdueOwnershipOfferNode`). The
  snapshot is the CASE_MANAGER's own `Expire(Offer)`, stamped with its clock; its
  `event_type` is in `OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES`, so it closes
  the Offer. It is `NO_REPLICA_EFFECT`: replicas learn expiry from the entry and
  never compute it, as for embargo Invite expiry (CM-28-014).
  - **Why a tree of its own.** The expiry is the CASE_MANAGER's clock decision,
    committed as its own entry before the activity changes anything (CLP-07-013),
    and a received tree commits nothing before its guards (CLP-10-010). So each
    of the four use cases runs the CASE_MANAGER-gated expiry tree, then its
    received tree — the split the embargo Invite expiry makes
    (`AcceptInviteToEmbargoOnCaseReceivedUseCase._run_expiry_tree`). After
    `case_fully_closed` the expiry tree changes nothing (CM-23-013).
  - **Only the party prompts it.** An Accept, Reject or Undo prompts the expiry
    only when it names the open Offer and its sender is that Offer's transferee
    (Accept, Reject) or offerer (Undo) — `ExpiryPrompt` / `OfferParty` — so a
    sender with no standing never makes the CASE_MANAGER write (HP-01-006), as
    the embargo Invite expiry checks the invitee first. A new Offer prompts it
    with no sender check, since the Offer itself has none yet (#4540).
  - **Ask kind.** `OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRY` is `AskExpiry.VOID`
    (ASK-03-002): a late reply authorizes nothing.
