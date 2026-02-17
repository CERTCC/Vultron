# HTTP Protocol Requirements

**Version:** 1.0  
**Status:** ACTIVE  
**Last Updated:** 2026-02-13

## Purpose

Consolidated HTTP protocol requirements for Vultron API v2: status codes, headers, content negotiation.

**Source:** ActivityStreams 2.0 specification, HTTP/1.1 RFC 7231  
**Consolidates:** `inbox-endpoint.md` (IE-03, IE-07), `message-validation.md` (MV-06, MV-07), `error-handling.md` (EH-06)

---

## Content-Type Validation (MUST)

- `HP-01-001` Inbox endpoint MUST accept `application/activity+json` Content-Type
- `HP-01-002` Inbox endpoint MUST accept `application/ld+json; profile="https://www.w3.org/ns/activitystreams"` Content-Type
- `HP-01-003` Inbox endpoint MUST reject requests with invalid Content-Type using HTTP 415

## Request Size Limits (MUST)

- `HP-02-001` Inbox endpoint MUST reject requests exceeding 1 MB with HTTP 413

## HTTP Status Codes (MUST)

- `HP-03-001` API MUST use standard HTTP status codes with consistent semantics per table below

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

- `HP-04-001` All JSON responses MUST include `Content-Type: application/json` header

## Correlation ID Propagation (SHOULD)

- `HP-05-001` API SHOULD accept `X-Correlation-ID` or `X-Request-ID` headers for request tracing
- `HP-05-002` API SHOULD generate correlation ID from activity `id` field if header not provided

## Request Timeout Handling (SHOULD)

- `HP-06-001` Inbox endpoints SHOULD respond within 100ms
- `HP-06-002` Processing exceeding 100ms SHOULD return HTTP 202 and queue for background processing
- `HP-06-003` Timeout occurrences SHOULD be logged at WARNING level

## Rate Limiting Headers (MAY)

- `HP-07-001` API MAY include `X-RateLimit-Limit` header (maximum requests per window)
- `HP-07-002` API MAY include `X-RateLimit-Remaining` header (requests remaining)
- `HP-07-003` API MAY include `X-RateLimit-Reset` header (UTC timestamp for window reset)

## Verification

### HP-01-001, HP-01-002, HP-01-003

```python
# Accept valid Content-Type
response = client.post("/actors/test/inbox/", json=activity,
    headers={"Content-Type": "application/activity+json"})
assert response.status_code in [200, 202]

# Reject invalid Content-Type
response = client.post("/actors/test/inbox/", json=activity,
    headers={"Content-Type": "application/json"})
assert response.status_code == 415
```

### HP-02-001

```python
large_activity = {"type": "Create", "object": {"data": "x" * (1024 * 1024 + 1)}}
response = client.post("/actors/test/inbox/", json=large_activity)
assert response.status_code == 413
```

### HP-03-001

- Integration test: Verify each error condition → correct HTTP status code
- Unit test: 4xx errors log at WARNING level, 5xx at ERROR level

### HP-04-001

```python
response = client.post("/actors/test/inbox/", json=activity)
assert "application/json" in response.headers["content-type"]
```

### HP-05-001, HP-05-002

```python
response = client.post("/actors/test/inbox/", json=activity,
    headers={"X-Correlation-ID": "test-123"})
# Verify logs contain correlation ID
```

### HP-06-001, HP-06-002, HP-06-003

```python
# Measure response time with timeit
# Verify BackgroundTasks usage for long-running processing
```

## FastAPI Response Serialization (SHOULD)

- `HP-07-001` Endpoints returning polymorphic types SHOULD omit return type annotations or use Union types
  - **Context**: FastAPI uses return type annotations as implicit `response_model`, restricting JSON serialization to fields defined in the annotated class
  - **Issue**: Base class type annotations (e.g., `-> as_Base`) cause subclass fields to be excluded from JSON responses
  - **Verification**: API responses include all expected fields, not just base class fields

### Implementation Notes

**Problem**: When an endpoint has return type `-> as_Base` but returns a subclass like `VulnerabilityCase`, FastAPI's response_model filtering excludes subclass-specific fields from the JSON response.

```python
# Anti-pattern: Returns only as_Base fields (6 fields)
def get_object_by_key() -> as_Base:
    return VulnerabilityCase(...)  # Case-specific fields excluded!

# Correct: No type annotation allows full serialization
def get_object_by_key():
    return VulnerabilityCase(...)  # All fields included

# Alternative: Explicit union for known types
def get_object_by_key() -> Union[VulnerabilityCase, VulnerabilityReport, as_Actor]:
    ...
```

**Verification**: Test that API endpoints return complete object serialization, not just base class fields. Check database content AND API response content.

## Related

- Implementation: `vultron/api/v2/routers/actors.py`
- Tests: `test/api/v2/routers/test_actors.py`
