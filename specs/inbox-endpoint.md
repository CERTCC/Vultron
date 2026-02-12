# Inbox Endpoint Specification

## Context

The inbox endpoint is the primary entry point for actor-to-actor communication in Vultron. It receives ActivityStreams activities via HTTP POST, validates them, and queues them for asynchronous processing.

## Requirements

### IE-1: Endpoint URL Pattern - POST /actors/{actor_id}/inbox/
### IE-2: Request Validation - Accept POST only, validate Content-Type and size
### IE-3: Activity Validation - Use Pydantic models, return HTTP 422 on failure
### IE-4: Synchronous Response - Return HTTP 202 within 100ms
### IE-5: Asynchronous Processing - Queue activities for background processing
### IE-6: Error Responses - Return appropriate HTTP status codes (400, 404, 405, 413, 415, 422, 429, 500)
### IE-7: Response Format - JSON with status, activity_id, message
### IE-8: Logging - Log all requests at INFO level, errors at ERROR level
### IE-9: Idempotency - Detect duplicate activity IDs
### IE-10: Authentication and Authorization - Support HTTP Signature (future)
### IE-11: Rate Limiting - Limit requests per actor per time window

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: `vultron/api/v2/routers/actors.py`
- Implementation: `vultron/api/v2/backend/inbox_handler.py`
- Tests: `test/api/v2/routers/test_actors.py`
- Tests: `test/api/v2/backend/test_inbox_handler.py`
- Related Spec: [message-validation.md](message-validation.md)
- Related Spec: [queue-management.md](queue-management.md)
- Standard: ActivityPub specification

