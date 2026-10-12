---
title: Ownership Transfer — Closing an Offer (Reject, Withdrawal, Deadline)
status: active
kind: plan
tracks:
  - "#4475"
  - "#4491"
  - "#4055"
description: >
  Design for the ways an ownership-transfer Offer closes other than an Accept: a
  ledgered transferee Reject, one open Offer per case, owner withdrawal, and a
  binding answer deadline with lazy expiry. Not yet built.
related_specs:
  - specs/case-management.yaml
  - specs/case-ledger-processing.yaml
  - specs/triggerable-behaviors.yaml
related_notes:
  - notes/ownership-transfer.md
---

# Ownership Transfer — Closing an Offer

`RejectCaseOwnershipTransferReceivedUseCase` currently logs and returns `skipped`, and
there is no withdrawal or deadline. This note is the design #4475 (Reject, one open
Offer) and #4491 (withdrawal, deadline) implement. The settled routing for the Offer
and Accept is in [ownership-transfer](ownership-transfer.md); the Reject reuses the
Accept's `recorded_ownership_offer()` helper and sender guard (CM-21-011).

## The Reject Path (CM-21-010, CM-21-012 – CM-21-014)

A declined transfer has the same shape as an accepted one (settled by #3748):

```text
Transferee calls trigger: reject-case-ownership-transfer      ← TRIG-11-005
  → Reject(Offer(VulnerabilityCase))
      addressed:  to=[case_actor_id]                          ← CM-21-010
      queued in:  transferee's outbox

CASE_MANAGER inbox receives Reject
  → RejectCaseOwnershipTransferReceivedUseCase:
      guard:  sender is the transferee of an open Offer
              it recorded                                     ← CM-21-013
              (anyone else: REFUSED, nothing written)
      1. Commits CaseLedgerEntry (reject_case_ownership_transfer).  ← CM-21-012
      2. Announce(CaseLedgerEntry) → all participants.
```

- **The offerer learns of the decline from the broadcast.** It is not a recipient of
  the Reject (CM-21-010).
- **Replicas change no state.** `attributed_to` and every `CASE_OWNER` role stay; the
  entry only closes the Offer.
- **"Open" is read from the ledger.** An Offer is open until the ledger holds an
  Accept, Reject, withdrawal or expiry entry for it, found through
  `find_protocol_pair()` with an ownership-transfer reply-types constant beside the
  existing ones in `vultron/core/models/protocol_pair.py` (CLP-11-001). The replica's
  `VultronOwnershipTransferOfferRecord` is bookkeeping (CLP-07-014), never the answer.
- **One open Offer per case (CM-21-014).** The CASE_MANAGER refuses a new Offer while
  one is open. Once closed, the owner may offer again to anyone, the decliner included.

## Withdrawal and Deadline (CM-21-015 – CM-21-017)

One open Offer per case would let a silent transferee block every later transfer, so
an Offer can also close without an answer (#4490):

- **Withdrawal (CM-21-015, TRIG-11-006).** The owner that made an open Offer sends
  `Undo(Offer(VulnerabilityCase))` to the CASE_MANAGER through the
  `withdraw-case-ownership-transfer` trigger; it is ledgered and broadcast like a
  Reject. Anyone else's Undo is refused.
- **Deadline (CM-21-016, TRIG-11-007).** The Offer may carry an activity-level
  `end_time`, set through the offer trigger. Unlike an embargo `Invite.end_time`
  (CM-28-001), it is binding: an Accept or Reject processed after it is refused.
- **Expiry (CM-21-017).** The CASE_MANAGER finds an expired Offer lazily, when it next
  processes an answer, an Undo or a new Offer for the case, and commits a distinct
  expiry entry before acting. Replicas learn expiry from that entry and never compute
  it, as for embargo Invite expiry (CM-28-014).
