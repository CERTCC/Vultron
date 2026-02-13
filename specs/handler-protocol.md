# Handler Protocol Specification

## Overview

Handler functions process DispatchActivity objects and implement protocol business logic. All handlers follow a common contract defined by the HandlerProtocol and enforced by the verify_semantics decorator.

**Source**: Protocol design, dispatcher architecture

---

## Handler Signature (MUST)

- `HP-01-001` All handler functions MUST accept a single DispatchActivity parameter
- `HP-01-002` Handler functions MAY return None or HandlerResult

## Semantic Verification (MUST)

- `HP-02-001` All handlers MUST have semantic type verification before execution
  - **Implementation**: Uses `@verify_semantics` decorator with MessageSemantics enum value
- `HP-02-002` The verification mechanism MUST check that the activity's semantic type matches the handler's expected type
  - **Rationale**: Prevents routing errors where wrong handler processes an activity

## Handler Registration (MUST)

- `HP-03-001` All handlers MUST be discoverable via a handler registry mechanism
  - **Implementation**: Registry map (e.g., `SEMANTIC_HANDLER_MAP`) maps MessageSemantics → handler functions
- `HP-03-002` Registry keys MUST match handler semantic verification types

## Payload Access (MUST)

- `HP-04-001` Handlers MUST access activity data via `dispatchable.payload`
  - **Rationale**: Encapsulation; payload may be validated/transformed by dispatcher
- `HP-04-002` Handlers MUST use schema validation for type-safe payload access
  - **Implementation**: Pydantic models provide validation and type safety

## Error Handling (MUST)

- `HP-05-001` Handlers MUST raise exceptions for unrecoverable errors
- `HP-05-002` Handlers MUST log expected errors without raising exceptions

## Logging (MUST)

- `HP-06-001` Handlers MUST log entry at DEBUG level with handler name
- `HP-06-002` Handlers MUST log state transitions at INFO level with before/after states
- `HP-06-003` Handlers MUST log errors at ERROR level with full context
  - **Cross-reference**: `structured-logging.md` SL-03-001 for log level semantics
  - **Cross-reference**: `structured-logging.md` SL-04-001 for state transition format

## Idempotency (SHOULD)

- `HP-07-001` Handlers SHOULD be idempotent to support retries
  - **Idempotency**: Same input produces same result/state without unintended side effects
- `HP-07-002` Handlers SHOULD check for existing state before mutating
  - **Implementation**: Query data layer for existing records; update rather than create if present
  - **Example**: Before creating a report, check if report ID already exists in data layer

**Note**: Idempotency is a multi-layer concern:
- **Inbox level**: Duplicate activity ID detection (see `inbox-endpoint.md` IE-10-001)
- **Handler level**: State-aware mutations (this section)
- **Response level**: Avoid generating duplicate responses (see `response-format.md` RF-09-001)

## Data Model Persistence (MUST)

- `HP-08-001` Handlers MUST use `object_to_record()` helper when persisting Pydantic models
  - **Rationale**: Converts Pydantic models to dictionaries suitable for data layer storage
- `HP-08-002` Handlers MUST call `DataLayer.update(id, record)` with both ID and record parameters
  - **Anti-pattern**: `dl.update(object)` (single argument)
  - **Correct pattern**: `dl.update(object.as_id, object_to_record(object))`
- `HP-08-003` Pydantic validators with `mode="after"` MUST check if fields are already populated before setting defaults
  - **Rationale**: Validators run on every `model_validate()` call, including when reconstructing from database
  - **Anti-pattern**: `self.field = DefaultValue()` (unconditionally overwrites database values)
  - **Correct pattern**: `if self.field is None: self.field = DefaultValue()` (preserves existing data)
  - **Impact**: Prevents data loss when round-tripping objects through the database

**Critical Architecture Note**: Pydantic validators execute during both object creation AND database deserialization. Validators that initialize default values must be defensive to avoid overwriting persisted data. This particularly affects collection fields (lists, OrderedCollections) that may be populated by handler logic and then lost when the object is re-read from the database.

## Verification

### HP-01-001, HP-01-002 Verification
- Unit test: Handler accepts DispatchActivity parameter
- Unit test: Handler returns None or HandlerResult
- Type check: Handler signature matches HandlerProtocol

### HP-02-001, HP-02-002 Verification
- Unit test: Verify decorator present on all handlers
- Unit test: Decorator validates correct semantic type
- Unit test: Decorator raises error for mismatched semantic type

### HP-03-001, HP-03-002 Verification
- Unit test: All handlers in SEMANTIC_HANDLER_MAP
- Unit test: Registry keys match decorator values
- Unit test: No handlers missing from registry

### HP-04-001, HP-04-002 Verification
- Unit test: Handler accesses payload via dispatchable.payload
- Unit test: Pydantic validation occurs on payload access
- Code review: No direct dictionary access to activity data

### HP-05-001, HP-05-002 Verification
- Unit test: Handler raises exception for unrecoverable error
- Unit test: Handler logs and continues for expected error
- Integration test: Exception propagates to dispatcher

### HP-06-001, HP-06-002, HP-06-003 Verification
- Unit test: Verify DEBUG log entry on handler invocation
- Unit test: Verify INFO log for state transitions
- Unit test: Verify ERROR log for errors

### HP-07-001, HP-07-002 Verification
- Unit test: Handler called twice with same input produces same result
- Unit test: Handler checks existing state before mutation
- Integration test: Retry of failed handler succeeds

### HP-08-001, HP-08-002 Verification
- Code review: All `DataLayer.update()` calls include both ID and record parameters
- Code review: All Pydantic model persistence uses `object_to_record()` helper
- Unit test: Update with single argument raises TypeError
- Unit test: Update with ID and record succeeds

### HP-08-003 Verification
- Unit test: Pydantic model with after validator round-trips through database without data loss
- Unit test: Validator checks field is None before initializing default value
- Integration test: Actor inbox/outbox collections persist correctly after handler updates
- Regression test: Objects with populated collections retain data after `model_validate()`

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: `vultron/api/v2/backend/behavior_dispatcher.py`
- Implementation: `vultron/api/v2/backend/semantic_handler_map.py`
- Tests: `test/api/v2/backend/test_handlers.py`
- Related Spec: [dispatch-routing.md](dispatch-routing.md)
- Related Spec: [semantic-extraction.md](semantic-extraction.md)
