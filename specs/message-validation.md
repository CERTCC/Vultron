# Message Validation Specification

## Overview

The inbox handler validates ActivityStreams 2.0 activities before processing to ensure protocol conformance and required field presence. Invalid activities are rejected with appropriate error responses.

**Source**: ActivityStreams 2.0 specification, API design requirements

**Note**: 
- **HTTP-level validation** (Content-Type, size limits) consolidated in `specs/http-protocol.md` (HP-01, HP-02)
- This spec focuses on **ActivityStreams structure and semantic validation**

---

## Activity Structure Validation (MUST)

- `MV-01-001` Incoming payloads MUST conform to ActivityStreams 2.0 structure
  - MUST have a `type` field containing a valid Activity type
  - MUST have an `id` field containing a unique URI
  - MAY have an `actor` field identifying the activity initiator
  - MAY have an `object` field containing the activity target

## Schema Validation (MUST)

- `MV-02-001` The system MUST use Pydantic models to validate activities
- `MV-02-002` The system MUST reject activities that fail Pydantic validation with HTTP 422
- `MV-02-003` Validation error responses MUST include detailed error information
- `MV-02-004` The system MUST log validation failures at ERROR level

## Required Field Validation (MUST)

- `MV-03-001` The system MUST validate required fields based on activity type
  - Create activities MUST have an `object` field
  - Accept/Reject activities MUST have an `object` field referencing a prior activity
  - Add activities MUST have both `object` and `target` fields
  - Remove activities MUST have both `object` and `target` fields

## Object Type Validation (MUST)

- `MV-04-001` The system MUST validate that object types are recognized Vultron types
  - VulnerabilityReport
  - VulnerabilityCase
  - CaseParticipant
  - EmbargoEvent
  - Standard ActivityStreams types (Person, Organization, Service)

## URI Validation (MUST)

- `MV-05-001` The system MUST validate that ID and reference fields contain valid URIs
  - MUST use URI validation schemes (http, https, urn, etc.)
  - SHOULD reject obviously malformed URIs
  - MAY validate URI reachability for external references

## Duplicate Detection (SHOULD)

- `MV-08-001` The system SHOULD detect and handle duplicate activity submissions during validation
  - **Responsibility**: Validation layer checks if activity ID has been processed recently
  - **Behavior**: Returns HTTP 202 for duplicates without invoking handlers
  - **Layering**: This is the primary duplicate detection mechanism; inbox-layer detection (IE-10-001) is optional optimization
  - **Cross-reference**: See `inbox-endpoint.md` IE-10-001 for HTTP-layer optimization and `handler-protocol.md` HP-07-001 for handler-layer idempotency as defense-in-depth

## Verification

### MV-01-001 Verification
- Unit test: Activity missing `type` field → ValidationError
- Unit test: Activity missing `id` field → ValidationError
- Unit test: Valid minimal activity → passes validation

### MV-02-001, MV-02-002, MV-02-003, MV-02-004 Verification
- Integration test: POST invalid activity → HTTP 422 response
- Verification: Error response contains Pydantic validation details
- Verification: Log contains ERROR entry with validation failure

### MV-03-001 Verification
- Unit test: Each activity type with missing required fields → ValidationError
- Unit test: Each activity type with all required fields → passes

### MV-04-001 Verification
- Unit test: Unrecognized object type → ValidationError or warning
- Unit test: Each recognized Vultron object type → passes

### MV-05-001 Verification
- Unit test: Malformed URIs → ValidationError
- Unit test: Valid URI schemes → passes

### MV-08-001 Verification
- Integration test: Submit same activity twice → both return HTTP 202
- Verification: Second submission does not invoke handler
- **See also**: `specs/inbox-endpoint.md` IE-10-001 verification for complete duplicate detection tests

## Related

- **HTTP Protocol**: `specs/http-protocol.md` (Content-Type validation MV-06-001, size limits MV-07-001 consolidated as HP-01, HP-02)
- **Idempotency**: `specs/inbox-endpoint.md` IE-10-001, `specs/handler-protocol.md` HP-07-001
- **Implementation**: `vultron/api/v2/routers/actors.py` (`parse_activity()`)
- **Implementation**: `vultron/as_vocab/activities/` (Pydantic models)
- **Tests**: `test/api/v2/routers/test_actors.py`
- **Related Spec**: [inbox-endpoint.md](inbox-endpoint.md)
- **Related Spec**: [error-handling.md](error-handling.md)

