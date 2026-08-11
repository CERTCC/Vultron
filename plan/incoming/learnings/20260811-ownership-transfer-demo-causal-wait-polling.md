---
title: "Demo scripts must poll for causally derived IDs in forwarding use cases"
type: learning
timestamp: "2026-08-11"
source: ISSUE-2178
signal: spec-gap
---

## Observation

`notes/ownership-transfer.md` documents that `OfferCaseOwnershipTransferReceivedUseCase`
creates a NEW forwarded Offer (CM-21-005) and queues it to the transferee's inbox.
However, the note's `fvcv_handoff_demo.py` guidance only said "Remove the
`post_to_inbox_and_wait` self-delivery block." It did not say what the demo
should do instead — leaving an implicit assumption that the original offer ID
could be used to poll for delivery.

Bug #2178 was the result: the demo polled Coordinator's DataLayer for
`ownership_offer.id_` (the original Vendor1 offer). That ID is only stored in
the CaseActor's DataLayer; Coordinator's DataLayer receives a different
forwarded Offer ID. The poll never succeeded; the `accept-case-ownership-transfer`
trigger then failed with `VultronNotFoundError` because it also used the wrong ID.

## Pattern

Whenever a received-side use case creates a new forwarding activity in response
to a received one (forwarding pattern — CM-21-005, PCR-08-007), the demo must
discover the causally derived activity ID by scanning the recipient's DataLayer
with a discriminator-based poll, NOT by polling for the sender's original ID.

The discriminator scan pattern (`find_ownership_transfer_offer_for_actor`,
`find_case_invite_for_actor`) looks for semantic properties
(type + target + object) rather than identity (specific ID).

`wait_for_object_stored(client, obj_id=original_id)` is only correct when
the received-side use case stores the SAME object (same ID) in the recipient's
DataLayer. It will silently time out when the use case creates a forwarding
copy with a new ID.

## Required doc update

`notes/ownership-transfer.md` (§ `fvcv_handoff_demo.py` changes) should add:

> After the Vendor1 offer-trigger returns, poll Coordinator's DataLayer with
> `find_ownership_transfer_offer_for_actor(coordinator_client, case_id,
> transferee_id=coordinator.id_)` to discover the forwarded Offer ID.
> Use the returned ID — NOT `ownership_offer.id_` — for the
> `accept-case-ownership-transfer` trigger body.
>
> Rationale: `OfferCaseOwnershipTransferReceivedUseCase` creates a new Offer
> with a new ID (CM-21-005). Polling for the original ID will never match on
> the recipient's container.

Related: issue #2181 (broader pattern: demos conflate sequential with causal ordering).
Fix PR: https://github.com/CERTCC/Vultron/pull/2182
