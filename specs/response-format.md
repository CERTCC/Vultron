# Response Format Specification

## Overview

The Vultron protocol uses ActivityStreams activities for both requests and responses. When handlers process inbound activities, they generate response activities (Accept, Reject, Update, etc.) sent to the originating actor or other participants.

**Source**: ActivityStreams 2.0 specification, protocol design

---

## Response Activity Structure (MUST)

- `RF-01-001` Response activities MUST conform to ActivityStreams 2.0
  - MUST have `type` field with appropriate activity type
  - MUST have `id` field with unique URI
  - MUST have `actor` field identifying responding actor
  - MUST have `object` field referencing relevant object or activity

## Accept Response (MUST)

- `RF-02-001` Accept responses MUST use `Accept` activity type
- `RF-02-002` Accept responses MUST include `object` field referencing accepted activity or object
- `RF-02-003` Accepting an Offer of an object MUST reference the Offer activity in the `object` field of the Accept response
- `RF-02-004` When accepting an offered object, the `object` field of the
  `Accept` activity MUST reference the Offer activity itself (e.g.,
  `OfferCaseOwnershipTransfer`, `RecommendActor`), not the underlying object
  being offered
  - Downstream processing SHOULD rehydrate the referenced Offer to discover
    the underlying offered object

## Reject Response (MUST)

- `RF-03-001` Reject responses MUST use `Reject` activity type
- `RF-03-002` Reject responses SHOULD include reason in `content` field
- `RF-03-003` Rejecting an Offer of an object MUST reference the Offer activity in the `object` field of the Reject response
- `RF-03-004` When rejecting an offered object, the `object` field of the
  `Reject` activity MUST reference the Offer activity itself, not the
  underlying object being offered
  - Downstream processing SHOULD rehydrate the referenced Offer to discover
    the underlying offered object

## TentativeReject Response (MUST)

- `RF-04-001` TentativeReject responses MUST use `TentativeReject` activity type
- `RF-04-002` TentativeReject responses SHOULD include reason in `content` field
- `RF-04-003` Tentatively Rejecting an Offer of an object MUST reference the Offer activity in the `object` field of the TentativeReject response
- `RF-04-004` When tentatively rejecting an offered object, the `object` field 
  of the `Tentative Reject` activity MUST reference the Offer activity itself, 
  not the underlying object being offered
  - Downstream processing SHOULD rehydrate the referenced Offer to discover
    the underlying offered object

## Error Response (MUST)

- `RF-05-001` Error responses SHOULD use ActivityStreams error extensions
  - Include error type and message

## Response Delivery (MUST)

- `RF-06-001` Response activities MUST be delivered to the relevant actors' inboxes

## Response Timing (MUST)

- `RF-07-001` Response generation MUST NOT delay inbox acknowledgment

## Response Correlation (MUST)

- `RF-08-001` Response activities MUST include `inReplyTo` field
  - MUST reference the activity ID being responded to

## Idempotent Responses (MUST)

- `RF-09-001` Response generation MUST be idempotent
  - **Cross-reference**: See `idempotency.md` for complete requirements

## Verification

### RF-01-001, RF-02-001, RF-02-002 Verification

- Unit test: Accept response has required fields
- Unit test: Response conforms to ActivityStreams 2.0 schema
- Integration test: Accept response delivered to originating actor

### RF-03-001, RF-03-002, RF-03-004 Verification

- Unit test: Reject response has required fields
- Unit test: Reject response includes reason
- Integration test: Reject response delivered with reason
- Unit test: `AcceptActorRecommendation` / `RejectActorRecommendation` `object`
  references `RecommendActor` (Offer), not the actor ref itself


### RF-04-001, RF-04-002 Verification

- Unit test: TentativeReject response has required fields
- Unit test: TentativeReject response includes reason
- Integration test: TentativeReject response delivered with reason

### RF-05-001 Verification

- Unit test: Error response includes error type and message
- Integration test: Error response follows ActivityStreams format

### RF-06-001 Verification

- Integration test: Response queued to outbox
- Integration test: Response delivered to recipient inbox

### RF-07-001 Verification

- Unit test: Handler generates response during execution
- Integration test: Inbox returns 202 before response sent

### RF-08-001 Verification

- Unit test: Response includes `inReplyTo` field
- Unit test: `inReplyTo` matches original activity ID
- Integration test: Correlation maintained in logs

### RF-09-001 Verification

- See `idempotency.md` verification criteria
- Integration test: Reprocessing same activity doesn't duplicate response

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: (Future) `vultron/api/v2/backend/outbox.py`
- Related Spec: [outbox.md](outbox.md)
- Tests: `test/api/v2/backend/test_response_generation.py`
- Related Spec: [inbox-endpoint.md](inbox-endpoint.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)
- Standard: [ActivityStreams 2.0](https://www.w3.org/TR/activitystreams-core/)
