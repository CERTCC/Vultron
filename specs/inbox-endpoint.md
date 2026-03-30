# Inbox Endpoint Specification

## Overview

The inbox endpoint is the primary entry point for actor-to-actor communication in Vultron. It receives ActivityStreams activities via HTTP POST, validates them, and queues them for asynchronous processing.

**Source**: ActivityPub specification, API design requirements

**Cross-references**: `http-protocol.md`, `message-validation.md`, `idempotency.md`, `structured-logging.md`

---

## Endpoint Configuration

- `IE-02-001` The endpoint URL MUST be discoverable from actor profile
  - **Implementation**: Default pattern `POST /actors/{actor_id}/inbox/`
  - **Rationale**: Allow flexibility for different deployment contexts
- `IE-02-002` The endpoint MUST accept POST requests only
- `IE-02-003` The endpoint MUST reject non-POST requests with HTTP 405
  - IE-02-003 depends-on HTTP-03-001

## Request Handling

- `IE-03-001` The endpoint MUST validate Content-Type header
  - IE-03-001 depends-on HTTP-01-001
- `IE-03-002` The endpoint MUST enforce request size limits
  - IE-03-002 depends-on HTTP-02-001

## Activity Validation

- `IE-04-001` The endpoint MUST validate activity structure via schema validation
  - **Implementation**: Uses Pydantic models (see `message-validation.md`)
- `IE-04-002` The endpoint MUST return HTTP 422 for validation failures
  - Include detailed validation errors in response
  - IE-04-002 depends-on HTTP-03-001

## Response Timing

- `IE-05-001` The endpoint MUST return HTTP 202 within 100ms
  - IE-05-001 depends-on HTTP-06-001
- `IE-05-002` The endpoint MUST NOT block on handler execution

## Asynchronous Processing

- `IE-06-001` The endpoint MUST queue activities for background processing
- `IE-06-002` Background processing MUST be isolated from HTTP request/response cycle
  - **Implementation**: FastAPI BackgroundTasks or equivalent async mechanism

## Error Responses

- `IE-07-001` The endpoint MUST return appropriate HTTP status codes
  - IE-07-001 depends-on HTTP-03-001

## Response Format

- `IE-08-001` Response body MUST be JSON with fields: `status`, `activity_id`, `message`
  - IE-08-001 depends-on EH-05-001

## Logging

- `IE-09-001` The endpoint MUST log all requests at INFO level
  - IE-09-001 depends-on SL-01-001
  - IE-09-001 depends-on SL-02-001
  - IE-09-001 depends-on SL-03-001

## Idempotency

- `IE-10-001` The endpoint SHOULD implement early duplicate detection at HTTP layer
  - **Note**: Optional performance optimization; see `idempotency.md` for complete requirements
  - IE-10-001 depends-on ID-05-002

## Verification

### IE-02-001, IE-02-002, IE-02-003 Verification

- Integration test: POST to correct endpoint → HTTP 202
- Integration test: GET to endpoint → HTTP 405
- Integration test: Invalid actor_id → HTTP 404

### IE-03-001, IE-03-002 Verification

- See `http-protocol.md` HTTP-01-001, HTTP-02-001 verification criteria

### IE-04-001, IE-04-002 Verification

- Integration test: Valid activity → HTTP 202
- Integration test: Invalid activity → HTTP 422 with error details

### IE-05-001, IE-05-002 Verification

- Performance test: Response time < 100ms for valid request
- Integration test: Verify response returned before handler completes

### IE-06-001, IE-06-002 Verification

- Integration test: Verify activity queued for async processing
- Integration test: Verify handler executes after response sent

### IE-07-001, IE-08-001 Verification

- See `http-protocol.md` HTTP-03-001 for status code verification
- Integration test: Response body contains required fields

### IE-09-001 Verification

- See `structured-logging.md` SL-01-001, SL-02-001, SL-03-001 for logging verification

### IE-10-001 Verification

- See `idempotency.md` ID-05-002 for verification criteria

## Related

- **Implementation**: `vultron/adapters/driving/fastapi/routers/actors.py`
- **Tests**: `test/adapters/driving/fastapi/routers/test_actors.py`
- **Cross-specifications**: `http-protocol.md`, `message-validation.md`, `idempotency.md`, `structured-logging.md`, `error-handling.md`
