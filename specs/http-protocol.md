# HTTP Protocol Requirements

## Overview

Consolidated HTTP protocol requirements for Vultron API v2: status codes, headers, content negotiation.

**Source**: ActivityStreams 2.0 specification, HTTP/1.1 RFC 7231  
**Consolidates**: `inbox-endpoint.md` (IE-03, IE-07), `message-validation.md` (MV-06,
MV-07), `error-handling.md` (EH-06), `agentic-readiness.md` (AR-03-002)

---

## Content-Type Validation (MUST)

- `HTTP-01-001` Inbox endpoint MUST accept `application/activity+json` Content-Type
- `HTTP-01-002` Inbox endpoint MUST accept `application/ld+json; profile="https://www.w3.org/ns/activitystreams"` Content-Type
- `HTTP-01-003` Inbox endpoint MUST reject requests with invalid Content-Type using HTTP 415

## Request Size Limits (MUST)

- `HTTP-02-001` `PROD_ONLY` Inbox endpoint MUST reject requests exceeding 1 MB with HTTP 413

## HTTP Status Codes (MUST)

- `HTTP-03-001` API MUST use standard HTTP status codes with consistent semantics per table below

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Synchronous success |
| 202 | Accepted | Activity queued for async processing |
| 400 | Bad Request | Malformed activity structure |
| 404 | Not Found | Actor or resource does not exist |
| 405 | Method Not Allowed | Non-POST to inbox |
| 413 | Payload Too Large | Request exceeds 1 MB |
| 415 | Unsupported Media Type | Invalid Content-Type |
| 422 | Unprocessable Entity | Semantic validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unhandled exception |
| 503 | Service Unavailable | System not ready |

## Response Headers (MUST)

- `HTTP-04-001` All JSON responses MUST include `Content-Type: application/json` header

## Correlation ID Propagation (SHOULD)

- `HTTP-05-001` `PROD_ONLY` API SHOULD accept `X-Correlation-ID` or `X-Request-ID` headers for request tracing
- `HTTP-05-002` `PROD_ONLY` API SHOULD generate correlation ID from activity `id` field if header not provided

## Request Timeout Handling (SHOULD)

- `HTTP-06-001` Inbox endpoints SHOULD respond with HTTP headers within 100ms
  - **Measurement point**: Time from HTTP request received by server to response
    headers sent
  - **Excludes**: Network latency, client processing time
  - **Rationale**: Ensures responsive UX for ActivityPub federation
- `HTTP-06-002` Processing exceeding 100ms SHOULD return HTTP 202 and queue for
  background processing
  - **Implementation**: FastAPI BackgroundTasks decouple handler execution from
    HTTP response
- `HTTP-06-003` `PROD_ONLY` Timeout occurrences SHOULD be logged at WARNING level
  - **Log format**: "Inbox request exceeded 100ms threshold: {duration}ms"

## Rate Limiting Headers (MAY)

- `HTTP-07-001` `PROD_ONLY` API MAY include `X-RateLimit-Limit` header (maximum requests per window)
- `HTTP-07-002` `PROD_ONLY` API MAY include `X-RateLimit-Remaining` header (requests remaining)
- `HTTP-07-003` `PROD_ONLY` API MAY include `X-RateLimit-Reset` header (UTC timestamp for window reset)
- `HTTP-07-004` `PROD_ONLY` Transient error responses (HTTP 429, 503) MUST include a `Retry-After`
  header indicating when the client should retry

## Verification

### HTTP-01-001, HTTP-01-002, HTTP-01-003

- Integration test: POST with `application/activity+json` Content-Type → HTTP
  202
- Integration test: POST with `application/json` Content-Type → HTTP 415

### HTTP-02-001

- Integration test: POST with payload > 1 MB → HTTP 413

### HTTP-03-001

- Integration test: Verify each error condition → correct HTTP status code
- Unit test: 4xx errors log at WARNING level, 5xx at ERROR level

### HTTP-04-001

- Integration test: Response `Content-Type` header contains `application/json`

### HTTP-05-001, HTTP-05-002

- Integration test: Request with `X-Correlation-ID` header → logs contain
  correlation ID

### HTTP-06-001, HTTP-06-002, HTTP-06-003

- Performance test: Response headers sent within 100ms of receiving request
- Integration test: Handlers invoked via `BackgroundTasks` (not blocking HTTP)

### HTTP-07-004

- Integration test: HTTP 429 and 503 responses include `Retry-After` header

## FastAPI Response Serialization (MUST)

- `HTTP-08-001` API responses MUST include all fields of the actual returned
  object type, not only fields declared on the annotated base class
  - **Context**: FastAPI uses return type annotations as implicit
    `response_model`, restricting serialization to fields on the annotated
    class; subclass fields are silently excluded
  - **Implementation**: Omit return type annotations on endpoints returning
    polymorphic types, or use explicit `Union` types

### HTTP-08-001 Verification

- Integration test: API endpoint response contains all expected subclass fields
- Integration test: Database content and API response content match

## Related

- Implementation: `vultron/api/v2/routers/actors.py`
- Tests: `test/api/v2/routers/test_actors.py`
