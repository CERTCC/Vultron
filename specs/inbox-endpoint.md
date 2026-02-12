# Inbox Endpoint Specification

## Overview

The inbox endpoint is the primary entry point for actor-to-actor communication in Vultron. It receives ActivityStreams activities via HTTP POST, validates them, and queues them for asynchronous processing.

**Source**: ActivityPub specification, API design requirements

---

## Implementation Framework (MUST)

- `IE-01-001` The inbox endpoint MUST be implemented using FastAPI

## Endpoint Configuration (MUST)

- `IE-02-001` The endpoint URL pattern MUST be `POST /actors/{actor_id}/inbox/`
- `IE-02-002` The endpoint MUST accept POST requests only
- `IE-02-003` The endpoint MUST reject non-POST requests with HTTP 405

## Request Validation (MUST)

- `IE-03-002` The endpoint MUST enforce 1 MB size limit
  - Reject oversized payloads with HTTP 413

## Activity Validation (MUST)

- `IE-04-001` The endpoint MUST validate activities using Pydantic models
- `IE-04-002` The endpoint MUST return HTTP 422 for validation failures
  - Include detailed validation errors in response

## Response Timing (MUST)

- `IE-05-001` The endpoint MUST return HTTP 202 within 100ms
- `IE-05-002` The endpoint MUST NOT block on handler execution

## Asynchronous Processing (MUST)

- `IE-06-001` The endpoint MUST queue activities for background processing
- `IE-06-002` The endpoint MUST use FastAPI BackgroundTasks for async processing

## Error Responses (MUST)

- `IE-07-001` The endpoint MUST return appropriate HTTP status codes
  - 202: Accepted
  - 400: Bad request
  - 404: Actor not found
  - 405: Method not allowed
  - 413: Payload too large
  - 415: Unsupported media type
  - 422: Validation error
  - 429: Rate limit exceeded
  - 500: Internal server error

## Response Format (MUST)

- `IE-08-001` Response body MUST be JSON with fields: `status`, `activity_id`, `message`

## Logging (MUST)

- `IE-09-001` The endpoint MUST log all requests at INFO level
- `IE-09-002` The endpoint MUST log errors at ERROR level
  - Include activity ID, actor ID, error details

## Idempotency (SHOULD)

- `IE-10-001` The endpoint SHOULD detect duplicate activity IDs
- `IE-10-002` The endpoint SHOULD return HTTP 202 for duplicates without reprocessing

## Verification

### IE-01-001, IE-02-001, IE-02-002, IE-02-003 Verification
- Integration test: POST to correct endpoint → HTTP 202
- Integration test: GET to endpoint → HTTP 405
- Integration test: Invalid actor_id → HTTP 404

### IE-03-001, IE-03-002 Verification
- Integration test: Valid Content-Type → HTTP 202
- Integration test: Invalid Content-Type → HTTP 415
- Integration test: 1.1 MB payload → HTTP 413

### IE-04-001, IE-04-002 Verification
- Integration test: Valid activity → HTTP 202
- Integration test: Invalid activity → HTTP 422 with error details

### IE-05-001, IE-05-002 Verification
- Performance test: Response time < 100ms for valid request
- Integration test: Verify response returned before handler completes

### IE-06-001, IE-06-002 Verification
- Integration test: Verify activity queued to BackgroundTasks
- Integration test: Verify handler executes after response sent

### IE-07-001, IE-08-001 Verification
- Integration test: Each error condition → correct HTTP status
- Integration test: Response body contains required fields

### IE-09-001, IE-09-002 Verification
- Integration test: Verify INFO log entry for successful request
- Integration test: Verify ERROR log entry for failures

### IE-10-001, IE-10-002 Verification
- Integration test: Submit same activity twice → both return 202
- Integration test: Verify second submission not processed

## Related

- Implementation: `vultron/api/v2/routers/actors.py`
- Tests: `test/api/v2/routers/test_actors.py`
- Related Spec: [message-validation.md](message-validation.md)
- Related Spec: [error-handling.md](error-handling.md)
- Related Spec: [observability.md](observability.md)
