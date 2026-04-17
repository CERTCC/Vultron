# Message Validation Specification

## Overview

The inbox handler validates ActivityStreams 2.0 activities before processing to ensure protocol conformance and required field presence. Invalid activities are rejected with appropriate error responses.

**Source**: ActivityStreams 2.0 specification, API design requirements

**Note**:

- **HTTP-level validation** (Content-Type, size limits) consolidated in `specs/http-protocol.md` (HTTP-01, HTTP-02)
- This spec focuses on **ActivityStreams structure and semantic validation**

---

## Activity Structure Validation

- `MV-01-001` Incoming payloads MUST conform to ActivityStreams 2.0 structure
  - MUST have a `type` field containing a valid Activity type
  - MUST have an `id` field containing a unique URI
  - MAY have an `actor` field identifying the activity initiator
  - MAY have an `object` field containing the activity target
- `MV-01-005` Pattern-matching implementation MUST be defensive:
  - If a pattern expects an object type (or an actor base class), the match algorithm MUST handle both subclassed object types and URI string references without raising exceptions.
  - When activity data includes string references, the inbox handler SHOULD attempt rehydration prior to pattern matching; if rehydration is not possible, the system MUST log a warning and return MessageSemantics.UNKNOWN (see `specs/semantic-extraction.md`).

## Schema Validation

- `MV-02-001` The system MUST use Pydantic models to validate activities
  - MV-02-001 implements VP-15-001
- `MV-02-002` The system MUST reject activities that fail Pydantic validation with HTTP 422
- `MV-02-003` Validation error responses MUST include detailed error information
- `MV-02-004` The system MUST log validation failures at WARNING level
  - Validation failures are client errors (HTTP 422); see `structured-logging.md` SL-03-001

## Required Field Validation

- `MV-03-001` The system MUST validate required fields based on activity type
  - Create activities MUST have an `object` field
  - Accept/Reject activities MUST have an `object` field referencing a prior activity
  - Add activities MUST have both `object` and `target` fields
  - Remove activities MUST have both `object` and `target` fields

## Object Type Validation

- `MV-04-001` The system MUST validate that object types are recognized Vultron types
  - VulnerabilityReport
  - VulnerabilityCase
  - CaseParticipant
  - EmbargoEvent
  - Standard ActivityStreams types (Person, Organization, Service)
- `MV-04-002` (SHOULD) For Create-style activities that create sub-objects (e.g.,
  `CreateParticipant`), the activity `name` field SHOULD be a descriptive
  human-readable string identifying the actor, created object ID, and context
  (case ID)
  - Example: `"{actor} Create CaseParticipant {participant_id} from {attributed_to} in {case_id}"`

## URI Validation

- `MV-05-001` The system MUST validate that ID and reference fields contain valid URIs
  - MUST use URI validation schemes (http, https, urn, etc.)
  - SHOULD reject obviously malformed URIs
  - MAY validate URI reachability for external references
- `MV-05-002` The system MUST treat ActivityStreams object IDs as opaque URIs
  - IDs MUST be full URIs (e.g., `urn:uuid:...` or `https://...`) — bare UUIDs are NOT allowed in canonical persisted records.
  - Implementation components MUST NOT parse or assume internal structure of IDs (do not split or extract meaningful substrings from IDs).
  - All layers (API, handlers, data layer) MUST consistently store and compare IDs as URI strings; when creating IDs, prefer fully-qualified URIs.
  - The data layer and rehydration logic MUST perform URL-encoding/decoding only for transport concerns and must persist the original URI string as-is.
  
## Outbound Activity Object Integrity

- `MV-09-001` Outbound initiating activities (Create, Offer, Invite, Announce,
  Add, Remove, Update, Join, Ignore, Leave) MUST carry the `object` field as a
  fully inline typed domain object — bare string URIs and `as_Link` references
  are NOT permitted in outbound activities.
  - Rationale: Recipients use the inline object's `type` field for semantic
    pattern matching.  A bare string URI makes the object type opaque, causing
    every pattern that checks `object.type` to match (or fail), leading to
    incorrect handler dispatch.
  - This constraint is enforced at construction time by narrowing Pydantic
    `object_` field types to `DomainObject | None` in initiating activity
    classes.
- `MV-09-002` The outbox handler MUST raise `VultronOutboxObjectIntegrityError`
  and abort delivery if an outbound activity's `object_` field is a bare string
  or `as_Link` after any DataLayer expansion attempt.
  - This acts as a last-resort runtime guard in case a narrowed activity class
    is bypassed.

- `MV-09-003` Vultron activity classes where semantic dispatch depends on the
  `object_` type MUST require `object_` at construction time — no `None`
  default is permitted.  An omitted or `None` `object_` renders the activity
  semantically meaningless because `ActivityPattern._match_field` returns
  `False` for `None`, causing every pattern that inspects `object_.type` to
  fail, which forces dispatch to `UNKNOWN`.

## Duplicate Detection

- `MV-08-001` The system SHOULD detect duplicate activity submissions during validation
  - MV-08-001 depends-on ID-02-001

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

### MV-09-001, MV-09-002 Verification

- Unit test: Constructing an initiating activity class (e.g.,
  `RmCreateReportActivity`) with a bare string `object_` raises
  `pydantic.ValidationError`.
- Unit test: Constructing an initiating activity class with an `as_Link`
  `object_` raises `pydantic.ValidationError`.
- Unit test: Constructing an initiating activity class with the correct inline
  domain object succeeds.
- Unit test: `outbox_handler.handle_outbox_item()` raises
  `VultronOutboxObjectIntegrityError` when `object_` remains a bare string
  after expansion.
- Implementation: `vultron/wire/as2/vocab/activities/` (narrowed Pydantic types)
- Implementation: `vultron/adapters/driving/fastapi/outbox_handler.py`
  (`handle_outbox_item()` integrity check)

### MV-09-003 Verification

- Unit test: Constructing any activity class that has a semantic `ActivityPattern`
  checking `object_` type without providing `object_` raises
  `pydantic.ValidationError`.
- Unit test: Constructing the same class with `object_=None` raises
  `pydantic.ValidationError`.
- Implementation: `vultron/wire/as2/vocab/activities/` (all 37 affected classes
  have `object_: DomainType = Field(...)` with no `None` default)
- Test: `test/wire/as2/vocab/test_actvitities/test_inline_object_required.py`
  `TestNoneObjectRejected`

## Related

- **HTTP Protocol**: `specs/http-protocol.md` (Content-Type validation MV-06-001, size limits MV-07-001 consolidated as HTTP-01, HTTP-02)
- **Idempotency**: `specs/inbox-endpoint.md` IE-10-001, `specs/handler-protocol.md` HP-07-001
- **Implementation**: `vultron/wire/as2/parser.py` (`parse_activity()`)
- **Implementation**: `vultron/wire/as2/vocab/activities/` (Pydantic models)
- **Tests**: `test/adapters/driving/fastapi/routers/test_actors.py`
- **Related Spec**: [inbox-endpoint.md](inbox-endpoint.md)
- **Related Spec**: [error-handling.md](error-handling.md)
