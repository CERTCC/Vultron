# Inbox Endpoint Specification

## Overview

The inbox endpoint is the primary entry point for actor-to-actor communication in Vultron. It receives ActivityStreams activities via HTTP POST, validates them, and queues them for asynchronous processing.

**Source**: ActivityPub specification, API design requirements

**Cross-references**: 
- HTTP protocol requirements: `http-protocol.md`
- Logging requirements: `structured-logging.md`
- Message validation: `message-validation.md`

---

## Endpoint Configuration (MUST)

- `IE-02-001` The endpoint URL MUST be discoverable from actor profile
  - **Implementation**: Default pattern `POST /actors/{actor_id}/inbox/`
  - **Rationale**: Allow flexibility for different deployment contexts
- `IE-02-002` The endpoint MUST accept POST requests only
- `IE-02-003` The endpoint MUST reject non-POST requests with HTTP 405
  - **Cross-reference**: `http-protocol.md` HP-03-001

## Request Handling (MUST)

- `IE-03-001` The endpoint MUST validate Content-Type header
  - **Cross-reference**: `http-protocol.md` HP-01-001
- `IE-03-002` The endpoint MUST enforce request size limits
  - **Cross-reference**: `http-protocol.md` HP-02-001

## Activity Validation (MUST)

- `IE-04-001` The endpoint MUST validate activity structure via schema validation
  - **Implementation**: Uses Pydantic models (see `message-validation.md`)
- `IE-04-002` The endpoint MUST return HTTP 422 for validation failures
  - Include detailed validation errors in response
  - **Cross-reference**: `http-protocol.md` HP-03-001

## Response Timing (MUST)

- `IE-05-001` The endpoint MUST return HTTP 202 within 100ms
  - **Cross-reference**: `http-protocol.md` HP-06-001
- `IE-05-002` The endpoint MUST NOT block on handler execution

## Asynchronous Processing (MUST)

- `IE-06-001` The endpoint MUST queue activities for background processing
- `IE-06-002` Background processing MUST be isolated from HTTP request/response cycle
  - **Implementation**: FastAPI BackgroundTasks or equivalent async mechanism

## Error Responses (MUST)

- `IE-07-001` The endpoint MUST return appropriate HTTP status codes
  - **Cross-reference**: `http-protocol.md` HP-03-001 (consolidated status code table)

## Response Format (MUST)

- `IE-08-001` Response body MUST be JSON with fields: `status`, `activity_id`, `message`
  - **Cross-reference**: `error-handling.md` for error response format

## Logging (MUST)

- `IE-09-001` The endpoint MUST log all requests at INFO level
  - **Cross-reference**: `structured-logging.md` SL-01-001, SL-02-001, SL-03-001

## Idempotency (SHOULD)

- `IE-10-001` The endpoint SHOULD detect duplicate activity IDs at the HTTP layer (optimization)
  - **Note**: This is an optional performance optimization; primary duplicate detection occurs at validation and handler layers
  - **Cross-reference**: See `message-validation.md` MV-08-001 for validation-layer detection and `handler-protocol.md` HP-07-001 for handler-layer idempotency
- `IE-10-002` The endpoint SHOULD return HTTP 202 for duplicates without queuing for reprocessing
  - **Behavior**: Early return avoids unnecessary background task creation

## Verification

### IE-02-001, IE-02-002, IE-02-003 Verification
- Integration test: POST to correct endpoint → HTTP 202
- Integration test: GET to endpoint → HTTP 405
- Integration test: Invalid actor_id → HTTP 404

### IE-03-001, IE-03-002 Verification
- See `http-protocol.md` HP-01-001, HP-02-001 verification criteria

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
- See `http-protocol.md` HP-03-001 for status code verification
- Integration test: Response body contains required fields

### IE-09-001 Verification
- See `structured-logging.md` SL-01-001, SL-02-001, SL-03-001 for logging verification

### IE-10-001, IE-10-002 Verification
- Integration test: Submit same activity twice → both return 202
- Integration test: Verify second submission not processed
- See `message-validation.md` MV-08-001 for idempotency details

## Related

- Implementation: `vultron/api/v2/routers/actors.py`
- Tests: `test/api/v2/routers/test_actors.py`
- **Cross-specifications**:
  - [http-protocol.md](http-protocol.md) - HTTP status codes, Content-Type, size limits
  - [structured-logging.md](structured-logging.md) - Logging format and correlation IDs
  - [message-validation.md](message-validation.md) - Activity validation and idempotency
  - [error-handling.md](error-handling.md) - Error response format
