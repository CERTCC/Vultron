# Response Format Specification

## Overview

The Vultron protocol uses ActivityStreams activities for both requests and responses. When handlers process inbound activities, they generate response activities (Accept, Reject, Update, etc.) sent to the originating actor or other participants.

**Total**: 10 requirements  
**Source**: ActivityStreams 2.0 specification, protocol design

---

## Response Activity Structure (MUST)

- `RF-001` Response activities MUST conform to ActivityStreams 2.0
  - MUST have `type` field with appropriate activity type
  - MUST have `id` field with unique URI
  - MUST have `actor` field identifying responding actor
  - MUST have `object` field referencing relevant object or activity

## Accept Response (MUST)

- `RF-002` Accept responses MUST use `Accept` activity type
- `RF-003` Accept responses MUST include `object` field referencing accepted activity or object

## Reject Response (MUST)

- `RF-004` Reject responses MUST use `Reject` activity type
- `RF-005` Reject responses SHOULD include reason in `content` field

## Update Response (SHOULD)

- `RF-006` Update responses SHOULD use `Update` activity type
- `RF-007` Update responses MUST include `object` with changed fields

## Error Response (MUST)

- `RF-008` Error responses SHOULD use ActivityStreams error extensions
  - Include error type and message

## Multi-Recipient Responses (MUST)

- `RF-009` The system MUST generate separate response activities for each recipient
- `RF-010` Response `to` field MUST contain target actor URI

## Response Delivery (MUST)

- `RF-011` Response activities MUST be queued to outbox for delivery
- `RF-012` Failed deliveries MUST be retried with exponential backoff

## Response Timing (MUST)

- `RF-013` Responses MUST be generated within handler execution
- `RF-014` Response generation MUST NOT delay inbox acknowledgment

## Response Correlation (MUST)

- `RF-015` Response activities MUST include `inReplyTo` field
  - MUST reference the activity ID being responded to

## Idempotent Responses (MUST)

- `RF-016` The system MUST NOT generate duplicate responses
  - Check for existing response before generating new one

## Verification

### RF-001, RF-002, RF-003 Verification
- Unit test: Accept response has required fields
- Unit test: Response conforms to ActivityStreams 2.0 schema
- Integration test: Accept response delivered to originating actor

### RF-004, RF-005 Verification
- Unit test: Reject response has required fields
- Unit test: Reject response includes reason
- Integration test: Reject response delivered with reason

### RF-006, RF-007 Verification
- Unit test: Update response includes changed fields
- Integration test: Update response reflects state change

### RF-008 Verification
- Unit test: Error response includes error type and message
- Integration test: Error response follows ActivityStreams format

### RF-009, RF-010 Verification
- Unit test: Multi-recipient logic generates separate activities
- Unit test: Each response has correct `to` field
- Integration test: Multiple recipients receive responses

### RF-011, RF-012 Verification
- Integration test: Response queued to outbox
- Integration test: Failed delivery retried
- Integration test: Exponential backoff observed

### RF-013, RF-014 Verification
- Unit test: Handler generates response during execution
- Integration test: Inbox returns 202 before response sent

### RF-015 Verification
- Unit test: Response includes `inReplyTo` field
- Unit test: `inReplyTo` matches original activity ID
- Integration test: Correlation maintained in logs

### RF-016 Verification
- Unit test: Duplicate response check works
- Integration test: Reprocessing same activity doesn't duplicate response

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: (Future) `vultron/api/v2/backend/outbox.py`
- Tests: `test/api/v2/backend/test_response_generation.py`
- Related Spec: [inbox-endpoint.md](inbox-endpoint.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)
- Standard: [ActivityStreams 2.0](https://www.w3.org/TR/activitystreams-core/)
