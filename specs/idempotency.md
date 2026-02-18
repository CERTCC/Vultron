# Idempotency Specification

## Overview

The system must handle duplicate activity submissions gracefully, ensuring repeated identical requests produce the same outcome without unintended side effects.

**Source**: ActivityPub specification, distributed systems best practices  
**Consolidates**: `inbox-endpoint.md` IE-10-001, `message-validation.md` MV-08-001, `handler-protocol.md` HP-07-001

**Note**: Idempotency is defense-in-depth across multiple layers: HTTP, validation, and handler business logic.

---

## Activity ID Uniqueness (MUST)

- `ID-01-001` All activities MUST have globally unique `id` field (URI)
- `ID-01-002` Activity IDs MUST remain stable (same activity = same ID)

## Duplicate Detection (MUST)

- `ID-02-001` System MUST detect duplicate activity submissions by ID
- `ID-02-002` System SHOULD track processed activity IDs in DataLayer
- `ID-02-003` Detection MUST occur before handler business logic execution

## Idempotent Response (MUST)

- `ID-03-001` Duplicate submissions MUST return same HTTP status as original
  - First submission: HTTP 202 (queued for processing)
  - Subsequent submissions: HTTP 202 (already processed)
- `ID-03-002` Duplicate detection MUST NOT delay response beyond 100ms
- `ID-03-003` System SHOULD log duplicate submissions at WARNING level
  - **Cross-reference**: `structured-logging.md` SL-03-001 for log level semantics

## Handler Idempotency (SHOULD)

- `ID-04-001` Handlers SHOULD be idempotent (same input → same output)
- `ID-04-002` Handlers SHOULD check existing state before state transitions
  - Example: validate_report checks if report already valid
- `ID-04-003` Handlers SHOULD log attempted re-execution at INFO level

## Implementation Strategy (SHOULD)

- `ID-05-001` Validation layer SHOULD reject exact duplicates (same ID, same content)
- `ID-05-002` HTTP layer MAY implement early duplicate filtering for performance
- `ID-05-003` Handlers provide final idempotency guarantee via state checks

## Verification

### ID-01-001, ID-01-002 Verification

- Unit test: Activities without `id` field rejected
- Unit test: Duplicate IDs from different sources detected

### ID-02-001, ID-02-002, ID-02-003 Verification

- Integration test: Submit activity A → processes successfully
- Integration test: Re-submit activity A → returns 202 without re-processing
- Unit test: Activity ID tracked in processed_activities table/collection

### ID-03-001, ID-03-002 Verification

- Integration test: Duplicate submission returns HTTP 202 within 100ms
- Integration test: Duplicate submission does not trigger handler re-execution

### ID-04-001, ID-04-002 Verification

- Unit test: validate_report called twice → same state transition once
- Unit test: create_report called twice → second call logs "already exists"

## Related

- **HTTP Protocol**: `specs/http-protocol.md` (status codes)
- **Message Validation**: `specs/message-validation.md` (activity structure)
- **Handler Protocol**: `specs/handler-protocol.md` (handler idempotency patterns)
- **Structured Logging**: `specs/structured-logging.md` (duplicate logging)
- **Inbox Endpoint**: `specs/inbox-endpoint.md` (endpoint behavior)

## Implementation

- **Duplicate Tracking**: `vultron/api/v2/datalayer/abc.py` (processed_activities)
- **Validation Layer**: `vultron/api/v2/backend/inbox_handler.py` (duplicate check)
- **Handler Examples**: `vultron/api/v2/backend/handlers.py` (idempotent state checks)
- **Tests**: `test/api/v2/backend/test_idempotency.py` (future)
