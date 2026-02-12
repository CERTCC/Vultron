# Response Format Specification

## Context

The Vultron protocol uses ActivityStreams activities for both requests and responses. When handlers process inbound activities, they may generate response activities (Accept, Reject, Update, etc.) sent to the originating actor or other participants.

## Requirements

### RF-1: Response Activity Structure - Conform to ActivityStreams 2.0 with type, id, actor, object fields
### RF-2: Accept Response - Use Accept type with object referencing accepted activity
### RF-3: Reject Response - Use Reject type with rejection reason
### RF-4: Update Response - Use Update type with changed fields
### RF-5: Error Response - Use ActivityStreams error extensions
### RF-6: Multi-Recipient Responses - Generate separate responses for each recipient
### RF-7: Response Delivery - Queue to outbox, retry on failure
### RF-8: Response Timing - Generate within handler, don't delay inbox acknowledgment
### RF-9: Response Correlation - Include inReplyTo field pointing to original activity
### RF-10: Idempotent Responses - Don't generate duplicate responses

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: (Future) `vultron/api/v2/backend/outbox.py`
- Tests: `test/api/v2/backend/test_response_generation.py`
- Related Spec: [inbox-endpoint.md](inbox-endpoint.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)
- Standard: ActivityStreams 2.0 specification

