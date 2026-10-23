---
title: "CM-24-002's attributed_to was dropped at extraction, so no core code could use it"
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2789
signal: concern
---

## What was wrong

CM-24-002 requires a delegated Activity to carry the requesting participant in
`attributed_to` "so that receivers can recover the originating identity". The
trigger side implemented it faithfully — `_prepare_delegated_context()` sets it,
the factory stamps it on the wire object, and it goes out on the wire.

`_build_activity_snapshot` (`vultron/wire/as2/extractor/_builders.py`) then
dropped it. That function builds the `VultronActivity` a received-side use case
reads as `request.activity`, and it copied `actor`, `target`, `to`, `cc`,
`origin`, `context`, `in_reply_to`, `summary`, `content`, `suggested_roles` and
`roles` — but not `attributed_to`. So the field existed on the wire, satisfied
every trigger-side test, and was unreachable in core.

`OfferCaseOwnershipTransferReceivedUseCase` consequently forwarded the
ownership-transfer Offer with `attributed_to = request.actor_id`, which for a
delegated message is the CaseActor. The CaseActor attributed the vendor's intent
to itself, on the transferee's copy and on every replica materialising the offer
from the ledger snapshot. Filed and fixed as #3012.

## Why nothing caught it

The sending half and the receiving half were tested separately and both were
right about their own side. `test_offer_cascade_forwards_to_transferee_via_case_actor_outbox`
even asserts `attributed_to=vendor_id` on the forward call — and passed, because
its fixture builds the *non-delegated* shape (`actor=vendor_id`), where
`request.actor_id` happens to be the vendor. The delegated shape
(`actor=case_actor_id, attributed_to=vendor_id`) is the one production sends, and
no test used it. The new
`test_forwarded_offer_attributes_the_requesting_participant` does.

## How to apply

- **A "so that receivers can …" clause in a spec is a claim about the receiving
  side.** It is not satisfied by the sender setting the field. When implementing
  a requirement phrased that way, write the assertion on the receiving end —
  read the field back out of the extracted event, not out of the wire object.
- **Fixture shape decides which bug a test can see.** A received-side fixture
  that builds the *simple* shape of an activity cannot detect a defect that only
  appears in the *delegated* shape, even when its assertion names the right
  field. For anything under CM-24, seed `actor=case_actor_id` with a distinct
  `attributed_to`; if the two are the same actor, the test proves nothing about
  which one the code read.
- **Field-by-field copy functions rot silently.** `_build_activity_snapshot`
  enumerates fields by hand, so every field added to `VultronObject` since it was
  written is absent by default and nothing fails. Worth checking the rest of its
  omissions against what core actually needs.

---

**Promoted**: 2026-09-03 — captured in `notes/testing-pitfalls.md` ("A Received-Side Test Only Sees Bugs Its Fixture Shape Can Reach"). Docs PR: <https://github.com/CERTCC/Vultron/pull/3147>.
