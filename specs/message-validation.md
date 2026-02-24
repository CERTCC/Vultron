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
  - MAY have an `object` field containing the activity 
- MV-01-005 Pattern-matching implementation MUST be defensive:
  - If a pattern expects an object type (or an actor base class), the match algorithm MUST handle both subclassed object types and URI string references without raising exceptions.
  - When activity data includes string references, the inbox handler SHOULD attempt rehydration prior to pattern matching; if rehydration is not possible, the system MUST log a warning and return MessageSemantics.UNKNOWN (see `specs/semantic-extraction.md`).

## Schema Validation (MUST)

- `MV-02-001` The system MUST use Pydantic models to validate activities
- `MV-02-002` The system MUST reject activities that fail Pydantic validation with HTTP 422
- `MV-02-003` Validation error responses MUST include detailed error information
- `MV-02-004` The system MUST log validation failures at WARNING level
  - Validation failures are client errors (HTTP 422); see `structured-logging.md` SL-03-001

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
- MV-04-002 Human-readable name conventions:
  - For Create-style activities that create sub-objects (e.g., `CreateParticipant`), the activity `name` field SHOULD be a descriptive human-readable string that identifies the actor performing the Create, the created object ID, and context (case id).
  - Example: `"{actor} Create CaseParticipant {participant_id} from {attributed_to} in {case_id}"`
  - This is a SHOULD (for useful auditing and logs) rather than a strict MUST.

## URI Validation (MUST)

- `MV-05-001` The system MUST validate that ID and reference fields contain valid URIs
  - MUST use URI validation schemes (http, https, urn, etc.)
  - SHOULD reject obviously malformed URIs
  - MAY validate URI reachability for external references
- MV-05-002 The system MUST treat ActivityStreams object IDs as opaque URIs.
  - IDs MUST be full URIs (e.g., `urn:uuid:...` or `https://...`) — bare UUIDs are NOT allowed in canonical persisted records.
  - Implementation components MUST NOT parse or assume internal structure of IDs (do not split or extract meaningful substrings from IDs).
  - All layers (API, handlers, data layer) MUST consistently store and compare IDs as URI strings; when creating IDs, prefer fully-qualified URIs.
  - The data layer and rehydration logic MUST perform URL-encoding/decoding only for transport concerns and must persist the original URI string as-is.
  
## Duplicate Detection (SHOULD)

- `MV-08-001` The system SHOULD detect duplicate activity submissions during validation
  - **Cross-reference**: See `idempotency.md` ID-02-001 for complete requirements

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

- See `idempotency.md` ID-02-001 verification criteria

## Related

- **HTTP Protocol**: `specs/http-protocol.md` (Content-Type validation MV-06-001, size limits MV-07-001 consolidated as HTTP-01, HTTP-02)
- **Idempotency**: `specs/inbox-endpoint.md` IE-10-001, `specs/handler-protocol.md` HP-07-001
- **Implementation**: `vultron/api/v2/routers/actors.py` (`parse_activity()`)
- **Implementation**: `vultron/as_vocab/activities/` (Pydantic models)
- **Tests**: `test/api/v2/routers/test_actors.py`
- **Related Spec**: [inbox-endpoint.md](inbox-endpoint.md)
- **Related Spec**: [error-handling.md](error-handling.md)
