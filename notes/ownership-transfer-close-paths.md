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
related_notes:
  - notes/ownership-transfer.md
---

# Ownership Transfer — Closing an Offer Without an Answer

An Offer has no withdrawal and no deadline; this note is the design #4491
implements. The Offer, Accept and Reject paths, and the one-open-Offer guard, are in
[ownership-transfer](ownership-transfer.md); a withdrawal or expiry entry joins
`OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES` when it is ledgered.

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
