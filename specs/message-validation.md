# Message Validation Specification

## Context

The inbox handler receives ActivityStreams 2.0 activities via POST requests. Activities MUST be validated before processing to ensure they conform to the protocol schema and contain required fields. Invalid activities MUST be rejected with appropriate error responses.

## Requirements

### MV-1: Activity Structure Validation
The system MUST validate that incoming payloads conform to ActivityStreams 2.0 structure:
- MUST have a `type` field containing a valid Activity type
- MUST have an `id` field containing a unique URI
- MAY have an `actor` field identifying the activity initiator
- MAY have an `object` field containing the activity target

### MV-2: Pydantic Schema Validation
The system MUST use Pydantic models to validate activities:
- MUST reject activities that fail Pydantic validation with HTTP 422
- MUST include validation error details in the response
- MUST log validation failures at ERROR level

### MV-3: Required Field Validation
The system MUST validate required fields based on activity type:
- Create activities MUST have an `object` field
- Accept/Reject activities MUST have an `object` field referencing a prior activity
- Add activities MUST have both `object` and `target` fields
- Remove activities MUST have both `object` and `target` fields

### MV-4: Object Type Validation
The system MUST validate that object types are recognized Vultron types:
- VulnerabilityReport
- VulnerabilityCase
- CaseParticipant
- EmbargoEvent
- Standard ActivityStreams types (Person, Organization, Service)

### MV-5: URI Validation
The system MUST validate that ID and reference fields contain valid URIs:
- MUST use URI validation schemes (http, https, urn, etc.)
- SHOULD reject obviously malformed URIs
- MAY validate URI reachability for external references

### MV-6: Content-Type Validation
The system MUST validate request Content-Type headers:
- MUST accept `application/activity+json`
- MUST accept `application/ld+json; profile="https://www.w3.org/ns/activitystreams"`
- SHOULD accept `application/json` with a warning
- MUST reject other content types with HTTP 415

### MV-7: Size Limits
The system MUST enforce reasonable size limits:
- Activity payload MUST NOT exceed 1 MB
- MUST reject oversized payloads with HTTP 413

### MV-8: Duplicate Detection
The system SHOULD detect and handle duplicate activity submissions:
- SHOULD track recently processed activity IDs
- SHOULD return HTTP 202 for duplicate submissions without reprocessing
- MAY implement idempotency based on activity ID

## Verification

### MV-1 Verification
- Unit test with activities missing `type` field → ValidationError
- Unit test with activities missing `id` field → ValidationError
- Unit test with valid minimal activity → passes validation

### MV-2 Verification
- Integration test POSTing invalid activity → HTTP 422 response
- Verify error response contains Pydantic validation details
- Verify log contains ERROR entry with validation failure

### MV-3 Verification
- Unit test for each activity type with missing required fields → ValidationError
- Unit test for each activity type with all required fields → passes

### MV-4 Verification
- Unit test with unrecognized object type → ValidationError or warning
- Unit test with each recognized Vultron object type → passes

### MV-5 Verification
- Unit test with malformed URIs → ValidationError
- Unit test with valid URI schemes → passes

### MV-6 Verification
- Integration test with each acceptable Content-Type → HTTP 202
- Integration test with unacceptable Content-Type → HTTP 415

### MV-7 Verification
- Integration test with 1.1 MB payload → HTTP 413
- Integration test with 0.9 MB payload → HTTP 202

### MV-8 Verification
- Integration test submitting same activity twice → both return HTTP 202
- Verify second submission does not invoke handler

## Related

- Implementation: `vultron/api/v2/routers/actors.py` (`parse_activity()`)
- Implementation: `vultron/as_vocab/activities/` (Pydantic models)
- Tests: `test/api/v2/routers/test_actors.py`
- Related Spec: [inbox-endpoint.md](inbox-endpoint.md)
- Related Spec: [error-handling.md](error-handling.md)

