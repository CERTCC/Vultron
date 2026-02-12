# Message Validation Specification

## Overview

The inbox handler validates ActivityStreams 2.0 activities before processing to ensure protocol conformance and required field presence. Invalid activities are rejected with appropriate error responses.

**Total**: 9 requirements  
**Source**: ActivityStreams 2.0 specification, API design requirements

---

## Activity Structure Validation (MUST)

- `MV-001` Incoming payloads MUST conform to ActivityStreams 2.0 structure
  - MUST have a `type` field containing a valid Activity type
  - MUST have an `id` field containing a unique URI
  - MAY have an `actor` field identifying the activity initiator
  - MAY have an `object` field containing the activity target

## Schema Validation (MUST)

- `MV-002` The system MUST use Pydantic models to validate activities
- `MV-003` The system MUST reject activities that fail Pydantic validation with HTTP 422
- `MV-004` Validation error responses MUST include detailed error information
- `MV-005` The system MUST log validation failures at ERROR level

## Required Field Validation (MUST)

- `MV-006` The system MUST validate required fields based on activity type
  - Create activities MUST have an `object` field
  - Accept/Reject activities MUST have an `object` field referencing a prior activity
  - Add activities MUST have both `object` and `target` fields
  - Remove activities MUST have both `object` and `target` fields

## Object Type Validation (MUST)

- `MV-007` The system MUST validate that object types are recognized Vultron types
  - VulnerabilityReport
  - VulnerabilityCase
  - CaseParticipant
  - EmbargoEvent
  - Standard ActivityStreams types (Person, Organization, Service)

## URI Validation (MUST)

- `MV-008` The system MUST validate that ID and reference fields contain valid URIs
  - MUST use URI validation schemes (http, https, urn, etc.)
  - SHOULD reject obviously malformed URIs
  - MAY validate URI reachability for external references

## Content-Type Validation (MUST)

- `MV-009` The system MUST validate request Content-Type headers
  - MUST accept `application/activity+json`
  - MUST accept `application/ld+json; profile="https://www.w3.org/ns/activitystreams"`
  - SHOULD accept `application/json` with a warning
  - MUST reject other content types with HTTP 415

## Size Limits (MUST)

- `MV-010` Activity payload MUST NOT exceed 1 MB
- `MV-011` The system MUST reject oversized payloads with HTTP 413

## Duplicate Detection (SHOULD)

- `MV-012` The system SHOULD detect and handle duplicate activity submissions
  - SHOULD track recently processed activity IDs
  - SHOULD return HTTP 202 for duplicate submissions without reprocessing
  - MAY implement idempotency based on activity ID

## Verification

### MV-001 Verification
- Unit test: Activity missing `type` field → ValidationError
- Unit test: Activity missing `id` field → ValidationError
- Unit test: Valid minimal activity → passes validation

### MV-002, MV-003, MV-004, MV-005 Verification
- Integration test: POST invalid activity → HTTP 422 response
- Verification: Error response contains Pydantic validation details
- Verification: Log contains ERROR entry with validation failure

### MV-006 Verification
- Unit test: Each activity type with missing required fields → ValidationError
- Unit test: Each activity type with all required fields → passes

### MV-007 Verification
- Unit test: Unrecognized object type → ValidationError or warning
- Unit test: Each recognized Vultron object type → passes

### MV-008 Verification
- Unit test: Malformed URIs → ValidationError
- Unit test: Valid URI schemes → passes

### MV-009 Verification
- Integration test: Each acceptable Content-Type → HTTP 202
- Integration test: Unacceptable Content-Type → HTTP 415

### MV-010, MV-011 Verification
- Integration test: 1.1 MB payload → HTTP 413
- Integration test: 0.9 MB payload → HTTP 202

### MV-012 Verification
- Integration test: Submit same activity twice → both return HTTP 202
- Verification: Second submission does not invoke handler

## Related

- Implementation: `vultron/api/v2/routers/actors.py` (`parse_activity()`)
- Implementation: `vultron/as_vocab/activities/` (Pydantic models)
- Tests: `test/api/v2/routers/test_actors.py`
- Related Spec: [inbox-endpoint.md](inbox-endpoint.md)
- Related Spec: [error-handling.md](error-handling.md)

